from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.connectors.mock_product_spec import load_products
from app.schemas.intent import IntentName, IntentResult, RetrievalTarget, RouteName
from app.tracing import trace_span

FOCUS_KEYWORDS: dict[str, tuple[str, ...]] = {
    "thermal": ("散热", "发热", "烫", "温控", "降频"),
    "after_sales": ("售后", "维修", "保修", "网点", "修"),
    "camera": ("拍照", "摄影", "影像", "相机", "人像", "视频", "vlog"),
    "battery": ("续航", "电池", "充电", "快充"),
    "performance": ("性能", "游戏", "芯片", "处理器", "跑分", "原神", "王者"),
    "price": ("价格", "预算", "性价比", "便宜", "贵", "划算"),
    "durability": ("耐用", "稳定", "用久", "寿命", "翻车"),
    "screen": ("屏幕", "护眼", "亮度", "刷新率"),
    "portability": ("重量", "轻", "手感", "便携", "小屏"),
    "storage": ("内存", "存储", "容量", "128g", "256g", "512g", "1t"),
}

REALTIME_KEYWORDS = (
    "现在",
    "最近",
    "目前",
    "今天",
    "今年",
    "618",
    "双11",
    "双十一",
    "降价",
    "涨价",
    "价格",
    "多少钱",
    "还值得",
    "翻车",
    "口碑",
)

COMPARE_KEYWORDS = ("对比", "比较", "哪个", "哪款", "谁", "差别", "区别", "更", "vs", "还是")
CONSULT_KEYWORDS = ("怎么样", "优缺点", "缺点", "优点", "值得买吗", "能买吗", "适合", "介绍")
RECOMMEND_KEYWORDS = ("推荐", "有哪些", "几款", "帮我选", "买什么", "怎么选", "求推荐", "还有别的")
PROFILE_KEYWORDS = (
    "预算",
    "主要",
    "日常",
    "拍照",
    "游戏",
    "办公",
    "学生",
    "长辈",
    "老人",
    "用三年",
    "用两年",
    "用几年",
    "不要",
    "喜欢",
    "在意",
    "担心",
)
PROFILE_UPDATE_PREFIXES = ("我主要", "主要用", "预算", "想用", "不要", "喜欢", "在意", "担心")
SHORT_FOLLOWUP_TERMS = ("那", "这个", "它", "这款", "还有吗", "还有别的吗")


@dataclass
class IntentContext:
    candidate_products: list[str] = field(default_factory=list)
    recent_messages: list[dict[str, str]] = field(default_factory=list)
    last_intent: IntentResult | None = None


@dataclass
class IntentSignals:
    text: str
    products: list[str]
    focus: list[str]
    needs_realtime: bool
    compare_hits: list[str]
    consult_hits: list[str]
    recommend_hits: list[str]
    profile_hits: list[str]
    is_short_followup: bool

    @property
    def has_candidates(self) -> bool:
        return bool(self.products)

    @property
    def has_multiple_products(self) -> bool:
        return len(self.products) >= 2


class IntentClassifier:
    """Enterprise-style deterministic router for the five core intents.

    This is still local and cheap, but it behaves like a real router: extract
    entities, score all candidate intents, calibrate confidence, resolve
    context and produce a route plus retrieval plan.
    """

    def classify(
        self,
        message: str,
        candidate_products: list[str] | None = None,
        *,
        recent_messages: list[dict[str, str]] | None = None,
        last_intent: IntentResult | None = None,
    ) -> IntentResult:
        context = IntentContext(
            candidate_products=candidate_products or [],
            recent_messages=recent_messages or [],
            last_intent=last_intent,
        )
        with trace_span(
            "intent_classification",
            input_data={
                "message": message[:200],
                "candidate_products": context.candidate_products,
                "last_intent": last_intent.intent if last_intent else None,
            },
        ) as (span, end_span):
            result = self._classify(message, context)
            end_span(output=result.model_dump(mode="json"))
            return result

    def _classify(self, message: str, context: IntentContext) -> IntentResult:
        signals = self._extract_signals(message, context)
        scores = self._score_intents(signals, context)
        primary = max(scores, key=scores.get)
        ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        secondary = [intent for intent, score in ordered[1:] if score >= 0.45]
        confidence = self._calibrate_confidence(ordered)
        context_action = self._resolve_context_action(primary, signals, context, confidence)
        route = self._route_for(primary)
        retrieval_plan = self._build_retrieval_plan(primary, signals)
        risk_flags = self._risk_flags(signals, confidence, ordered)
        needs_clarification = self._needs_clarification(primary, signals, confidence, context)

        if needs_clarification:
            context_action = "clarify"

        return IntentResult(
            intent=primary,
            secondary_intents=secondary,
            confidence=confidence,
            products=signals.products,
            focus=signals.focus,
            needs_realtime=signals.needs_realtime,
            needs_clarification=needs_clarification,
            route=route,
            retrieval_plan=retrieval_plan,
            context_action=context_action,
            risk_flags=risk_flags,
            evidence={
                "scores": scores,
                "hits": {
                    "compare": signals.compare_hits,
                    "consult": signals.consult_hits,
                    "recommend": signals.recommend_hits,
                    "profile_update": signals.profile_hits,
                    "focus": signals.focus,
                },
                "last_intent": context.last_intent.intent if context.last_intent else None,
                "recent_message_count": len(context.recent_messages),
            },
            reason=self._reason(primary, signals, context_action, retrieval_plan),
        )

    def _extract_signals(self, message: str, context: IntentContext) -> IntentSignals:
        text = message.lower().strip()
        products = self._extract_products(text, context)
        focus = self._extract_focus(text)
        return IntentSignals(
            text=text,
            products=products,
            focus=focus,
            needs_realtime=any(keyword in text for keyword in REALTIME_KEYWORDS),
            compare_hits=self._hits(text, COMPARE_KEYWORDS),
            consult_hits=self._hits(text, CONSULT_KEYWORDS),
            recommend_hits=self._hits(text, RECOMMEND_KEYWORDS),
            profile_hits=self._hits(text, PROFILE_KEYWORDS),
            is_short_followup=len(text) <= 8 or any(term in text for term in SHORT_FOLLOWUP_TERMS),
        )

    def _score_intents(self, signals: IntentSignals, context: IntentContext) -> dict[IntentName, float]:
        scores: dict[IntentName, float] = {
            "consult": 0.05,
            "compare": 0.05,
            "recommend": 0.05,
            "profile_update": 0.05,
            "other": 0.12,
        }

        if signals.has_multiple_products:
            scores["compare"] += 0.34
        elif len(signals.products) == 1:
            scores["consult"] += 0.28

        if signals.compare_hits:
            scores["compare"] += 0.35
        if signals.consult_hits:
            scores["consult"] += 0.32
            if signals.has_multiple_products:
                scores["compare"] += 0.18
        if signals.recommend_hits:
            scores["recommend"] += 0.42
        if signals.profile_hits:
            scores["profile_update"] += 0.28

        if signals.focus:
            scores["compare"] += 0.12 if signals.has_multiple_products else 0.04
            scores["recommend"] += 0.08 if signals.recommend_hits else 0.0
            scores["consult"] += 0.06 if len(signals.products) == 1 else 0.0

        if self._looks_like_profile_update(signals):
            scores["profile_update"] += 0.34
            scores["compare"] -= 0.12

        if context.last_intent and signals.is_short_followup:
            scores[context.last_intent.intent] += 0.22
            if signals.focus and context.last_intent.intent in {"compare", "consult"}:
                scores["compare"] += 0.22
            if signals.recommend_hits and context.last_intent.intent in {"compare", "consult"}:
                scores["recommend"] += 0.18

        if context.candidate_products and not signals.products:
            scores["profile_update"] += 0.08 if signals.profile_hits else 0.0
            scores["compare"] += 0.08 if signals.focus and not self._looks_like_profile_update(signals) else 0.0

        if not signals.has_candidates and signals.recommend_hits:
            scores["recommend"] += 0.1
        if not signals.has_candidates and not signals.recommend_hits and not signals.profile_hits:
            scores["other"] += 0.18

        if signals.needs_realtime:
            if signals.has_candidates:
                scores["consult"] += 0.08 if len(signals.products) == 1 else 0.0
                scores["compare"] += 0.06 if signals.has_multiple_products else 0.0
            elif signals.recommend_hits:
                scores["recommend"] += 0.04

        return {intent: max(0.0, min(1.0, score)) for intent, score in scores.items()}

    def _calibrate_confidence(self, ordered_scores: list[tuple[IntentName, float]]) -> float:
        top = ordered_scores[0][1]
        second = ordered_scores[1][1]
        margin = top - second
        confidence = 0.42 + top * 0.46 + min(0.12, margin * 0.3)
        if margin < 0.12:
            confidence -= 0.12
        elif margin < 0.22:
            confidence -= 0.05
        return round(max(0.35, min(0.95, confidence)), 2)

    def _resolve_context_action(
        self,
        primary: IntentName,
        signals: IntentSignals,
        context: IntentContext,
        confidence: float,
    ) -> str:
        if primary == "profile_update":
            return "update_profile"
        if confidence < 0.62:
            return "clarify"
        if context.last_intent and signals.is_short_followup:
            return "continue_previous_task"
        if context.last_intent and not signals.has_candidates and signals.focus:
            return "continue_previous_task"
        return "new_task"

    def _route_for(self, intent: IntentName) -> RouteName:
        return {
            "consult": "consult_agent",
            "compare": "compare_agent",
            "recommend": "recommend_agent",
            "profile_update": "profile_agent",
            "other": "fallback_agent",
        }[intent]

    def _build_retrieval_plan(self, intent: IntentName, signals: IntentSignals) -> list[RetrievalTarget]:
        plan: list[RetrievalTarget] = []
        if intent == "consult":
            plan.extend(["product_profile_kb", "review_kb"])
        elif intent == "compare":
            plan.append("comparison_kb")
            if "after_sales" in signals.focus:
                plan.append("after_sales_kb")
            if signals.focus:
                plan.append("product_profile_kb")
        elif intent == "recommend":
            plan.extend(["candidate_recall_kb", "product_profile_kb"])
        elif intent == "profile_update":
            plan.append("product_profile_kb")

        if signals.needs_realtime:
            plan.append("web_search")

        return self._dedupe(plan)

    def _risk_flags(
        self,
        signals: IntentSignals,
        confidence: float,
        ordered_scores: list[tuple[IntentName, float]],
    ) -> list[str]:
        flags: list[str] = []
        if signals.needs_realtime:
            flags.append("needs_realtime_evidence")
        if confidence < 0.65:
            flags.append("low_intent_confidence")
        if ordered_scores[0][1] - ordered_scores[1][1] < 0.12:
            flags.append("ambiguous_intent")
        if not signals.products and ordered_scores[0][0] in {"consult", "compare"}:
            flags.append("missing_product_entity")
        return flags

    def _needs_clarification(
        self,
        primary: IntentName,
        signals: IntentSignals,
        confidence: float,
        context: IntentContext,
    ) -> bool:
        if confidence < 0.58:
            return True
        if primary == "compare" and len(signals.products) < 2 and not context.candidate_products:
            return True
        if primary == "consult" and not signals.products:
            return True
        if primary == "recommend" and not signals.focus and not signals.profile_hits:
            return True
        return False

    def _reason(
        self,
        primary: IntentName,
        signals: IntentSignals,
        context_action: str,
        retrieval_plan: list[RetrievalTarget],
    ) -> str:
        parts = [f"primary={primary}", f"context_action={context_action}"]
        if signals.products:
            parts.append("products=" + ",".join(signals.products))
        if signals.focus:
            parts.append("focus=" + ",".join(signals.focus))
        if retrieval_plan:
            parts.append("retrieval=" + ",".join(retrieval_plan))
        return "；".join(parts)

    def _extract_products(self, text: str, context: IntentContext) -> list[str]:
        products: list[str] = []
        seen: set[str] = set()

        for candidate in context.candidate_products:
            normalized = self._normalize(candidate)
            if candidate and normalized not in seen:
                products.append(candidate)
                seen.add(normalized)

        for product in load_products():
            names = [product.id, product.name, *product.aliases]
            if any(self._normalize(name) in self._normalize(text) for name in names):
                normalized_id = self._normalize(product.id)
                if normalized_id not in seen:
                    products.append(product.id)
                    seen.add(normalized_id)

        return products

    def _extract_focus(self, text: str) -> list[str]:
        focus: list[str] = []
        for name, keywords in FOCUS_KEYWORDS.items():
            if any(keyword in text for keyword in keywords):
                focus.append(name)
        return focus

    def _looks_like_profile_update(self, signals: IntentSignals) -> bool:
        if not signals.profile_hits:
            return False
        if any(keyword in signals.text for keyword in signals.compare_hits + signals.consult_hits + signals.recommend_hits):
            return False
        return any(prefix in signals.text for prefix in PROFILE_UPDATE_PREFIXES) or not signals.has_candidates

    def _hits(self, text: str, keywords: tuple[str, ...]) -> list[str]:
        return [keyword for keyword in keywords if keyword in text]

    def _dedupe(self, values: list[RetrievalTarget]) -> list[RetrievalTarget]:
        result: list[RetrievalTarget] = []
        seen: set[str] = set()
        for value in values:
            if value not in seen:
                result.append(value)
                seen.add(value)
        return result

    def _normalize(self, value: str) -> str:
        return "".join(value.lower().split())
