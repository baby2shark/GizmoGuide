from __future__ import annotations

from app.connectors.mock_product_spec import load_products
from app.schemas.intent import IntentResult
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
RECOMMEND_KEYWORDS = ("推荐", "有哪些", "几款", "帮我选", "买什么", "怎么选", "求推荐")
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


class IntentClassifier:
    """Small deterministic classifier for the five core routing intents."""

    def classify(self, message: str, candidate_products: list[str] | None = None) -> IntentResult:
        with trace_span(
            "intent_classification",
            input_data={"message": message[:200], "candidate_products": candidate_products or []},
        ) as (span, end_span):
            result = self._classify(message, candidate_products or [])
            end_span(output=result.model_dump(mode="json"))
            return result

    def _classify(self, message: str, candidate_products: list[str]) -> IntentResult:
        text = message.lower().strip()
        products = self._extract_products(text, candidate_products)
        focus = self._extract_focus(text)
        needs_realtime = any(keyword in text for keyword in REALTIME_KEYWORDS)

        if self._is_explicit_compare(text, products, candidate_products):
            return IntentResult(
                intent="compare",
                confidence=0.86,
                products=products,
                focus=focus,
                needs_realtime=needs_realtime,
                reason="用户在比较多个候选或询问某个维度谁更好",
            )

        if self._is_open_recommendation(text, products, candidate_products):
            return IntentResult(
                intent="recommend",
                confidence=0.84,
                products=products,
                focus=focus,
                needs_realtime=needs_realtime,
                reason="用户希望系统给出候选机型",
            )

        if self._is_profile_update(text, products, candidate_products):
            return IntentResult(
                intent="profile_update",
                confidence=0.78,
                products=products,
                focus=focus,
                needs_realtime=needs_realtime,
                reason="用户在补充预算、用途或偏好",
            )

        if self._is_dimension_followup(text, products, candidate_products, focus):
            return IntentResult(
                intent="compare",
                confidence=0.76,
                products=products,
                focus=focus,
                needs_realtime=needs_realtime,
                reason="用户在已有候选上追问某个对比维度",
            )

        if self._is_consult(text, products):
            return IntentResult(
                intent="consult",
                confidence=0.82,
                products=products,
                focus=focus,
                needs_realtime=needs_realtime,
                reason="用户在咨询单品表现、优缺点或是否值得买",
            )

        return IntentResult(
            intent="other",
            confidence=0.55,
            products=products,
            focus=focus,
            needs_realtime=needs_realtime,
            reason="未命中核心购买任务意图",
        )

    def _extract_products(self, text: str, candidate_products: list[str]) -> list[str]:
        products: list[str] = []
        seen: set[str] = set()

        for candidate in candidate_products:
            if candidate and candidate not in seen:
                products.append(candidate)
                seen.add(candidate)

        for product in load_products():
            names = [product.id, product.name, *product.aliases]
            if any(self._normalize(name) in self._normalize(text) for name in names):
                if product.id not in seen:
                    products.append(product.id)
                    seen.add(product.id)

        return products

    def _extract_focus(self, text: str) -> list[str]:
        focus: list[str] = []
        for name, keywords in FOCUS_KEYWORDS.items():
            if any(keyword in text for keyword in keywords):
                focus.append(name)
        return focus

    def _is_explicit_compare(self, text: str, products: list[str], candidate_products: list[str]) -> bool:
        has_multiple_products = len(products) >= 2 or len(candidate_products) >= 2
        has_compare_word = any(keyword in text for keyword in COMPARE_KEYWORDS)
        has_consult_word = any(keyword in text for keyword in CONSULT_KEYWORDS)
        return has_multiple_products and (has_compare_word or has_consult_word)

    def _is_dimension_followup(
        self,
        text: str,
        products: list[str],
        candidate_products: list[str],
        focus: list[str],
    ) -> bool:
        if len(products) < 2 and len(candidate_products) < 2:
            return False
        if not focus:
            return False
        if any(keyword in text for keyword in ("我主要", "主要用", "预算", "想用", "不要", "喜欢")):
            return False
        return True

    def _is_open_recommendation(self, text: str, products: list[str], candidate_products: list[str]) -> bool:
        if candidate_products or len(products) >= 2:
            return False
        return any(keyword in text for keyword in RECOMMEND_KEYWORDS)

    def _is_profile_update(self, text: str, products: list[str], candidate_products: list[str]) -> bool:
        if products and any(keyword in text for keyword in CONSULT_KEYWORDS + COMPARE_KEYWORDS + RECOMMEND_KEYWORDS):
            return False
        if not candidate_products and not products:
            return False
        return any(keyword in text for keyword in PROFILE_KEYWORDS)

    def _is_consult(self, text: str, products: list[str]) -> bool:
        if len(products) == 1:
            return True
        return any(keyword in text for keyword in CONSULT_KEYWORDS)

    def _normalize(self, value: str) -> str:
        return "".join(value.lower().split())
