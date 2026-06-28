from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from app.memory.models import MemoryContext, MemoryEvent, SessionSummary
from app.schemas.intent import IntentResult
from app.schemas.product import ProductSpec
from app.schemas.recommendation import RecommendationResult
from app.schemas.user_profile import Scenario, UserProfile
from app.tracing import trace_span


class MemoryManager:
    """Lightweight Memory & Context Harness for multi-agent routing.

    The manager keeps an append-only event log and projects it into a compact
    session summary. Agents consume the summary instead of raw unbounded chat
    history, which keeps context focused and auditable.
    """

    def __init__(self, *, recent_event_limit: int = 12) -> None:
        self.recent_event_limit = recent_event_limit
        self._events: dict[str, list[MemoryEvent]] = defaultdict(list)
        self._profiles: dict[str, UserProfile] = {}
        self._summaries: dict[str, SessionSummary] = {}

    def get_context(self, session_id: str, fallback_profile: UserProfile | None = None) -> MemoryContext:
        profile = self._profiles.get(session_id) or fallback_profile or UserProfile()
        summary = self._summaries.get(session_id) or SessionSummary()
        return MemoryContext(
            session_id=session_id,
            profile=profile.model_copy(deep=True),
            summary=summary.model_copy(deep=True),
            recent_events=list(self._events.get(session_id, []))[-self.recent_event_limit :],
        )

    def remember_user_message(self, session_id: str, message: str) -> None:
        self._append(session_id, MemoryEvent(event_type="user_message", payload={"message": message}))

    def remember_intent(self, session_id: str, intent: IntentResult) -> None:
        self._append(
            session_id,
            MemoryEvent(
                event_type="intent_detected",
                payload={
                    "intent": intent.intent,
                    "route": intent.route,
                    "needs_realtime": intent.needs_realtime,
                    "focus": intent.focus,
                    "retrieval_plan": intent.retrieval_plan,
                    "confidence": intent.confidence,
                },
            ),
        )
        self._summaries.setdefault(session_id, SessionSummary()).last_intent = intent.intent

    def remember_profile(self, session_id: str, profile: UserProfile) -> None:
        previous = self._profiles.get(session_id)
        self._profiles[session_id] = profile.model_copy(deep=True)
        self._append(
            session_id,
            MemoryEvent(
                event_type="profile_updated",
                payload={
                    "profile": profile.model_dump(mode="json"),
                    "changed_fields": _changed_profile_fields(previous, profile),
                },
            ),
        )

    def remember_tool_evidence(self, session_id: str, source: str, evidence: str) -> None:
        evidence = evidence.strip()
        if not evidence:
            return
        self._append(session_id, MemoryEvent(event_type="tool_evidence", payload={"source": source, "evidence": evidence}))
        summary = self._summaries.setdefault(session_id, SessionSummary())
        _append_unique(summary.evidence_summary, f"{source}: {evidence}", limit=6)

    def remember_assistant_message(self, session_id: str, message: str, source: str) -> None:
        self._append(
            session_id,
            MemoryEvent(event_type="assistant_message", payload={"message": message, "answer_source": source}),
        )

    def remember_recommendation(self, session_id: str, result: RecommendationResult | None) -> None:
        if result is None:
            return
        self._append(
            session_id,
            MemoryEvent(
                event_type="recommendation_decision",
                payload={
                    "winner_id": result.winner_id,
                    "winner_name": result.winner_name,
                    "confidence": result.confidence,
                    "key_reasons": result.key_reasons,
                    "risks": result.risks,
                },
            ),
        )
        summary = self._summaries.setdefault(session_id, SessionSummary())
        _append_unique(summary.decisions, f"recommended {result.winner_name} ({result.confidence:.2f})", limit=6)

    def remember_fallback(self, session_id: str, reason: str) -> None:
        self._append(session_id, MemoryEvent(event_type="fallback_used", payload={"reason": reason}))

    def compress(
        self,
        session_id: str,
        *,
        profile: UserProfile,
        candidates: Iterable[ProductSpec],
        intent: IntentResult | None = None,
    ) -> SessionSummary:
        with trace_span("memory_compression", input_data={"session_id": session_id}) as (span, end_span):
            events = self._events.get(session_id, [])
            summary = self._summaries.setdefault(session_id, SessionSummary())
            summary.message_count = sum(1 for event in events if event.event_type in {"user_message", "assistant_message"})
            summary.candidate_products = [product.name for product in candidates]
            if intent is not None:
                summary.last_intent = intent.intent
            summary.active_goal = _build_active_goal(summary.candidate_products, intent)
            summary.known_constraints = _profile_constraints(profile)
            summary.open_questions = _open_questions(profile, summary.candidate_products)
            self._summaries[session_id] = summary
            end_span(output=summary.model_dump(mode="json"))
            return summary.model_copy(deep=True)

    def _append(self, session_id: str, event: MemoryEvent) -> None:
        self._events[session_id].append(event)


def _changed_profile_fields(previous: UserProfile | None, current: UserProfile) -> list[str]:
    if previous is None:
        return [key for key, value in current.model_dump().items() if value not in (None, [], "medium")]
    before = previous.model_dump()
    after = current.model_dump()
    return [key for key, value in after.items() if before.get(key) != value]


def _profile_constraints(profile: UserProfile) -> list[str]:
    constraints: list[str] = []
    if profile.budget is not None:
        constraints.append(f"budget <= {profile.budget}")
    if profile.primary_scenarios:
        labels = [_scenario_label(item) for item in profile.primary_scenarios]
        constraints.append("scenarios: " + ", ".join(labels))
    if profile.usage_years is not None:
        constraints.append(f"usage_years >= {profile.usage_years}")
    if profile.os_preference:
        constraints.append(f"os_preference: {profile.os_preference}")
    if profile.repair_sensitivity == "high":
        constraints.append("repair risk sensitive")
    if profile.risk_tolerance == "low":
        constraints.append("low risk tolerance")
    if profile.min_storage_gb is not None:
        constraints.append(f"storage >= {profile.min_storage_gb}GB")
    if profile.max_weight_g is not None:
        constraints.append(f"weight <= {profile.max_weight_g}g")
    constraints.extend(profile.notes[:3])
    return constraints[:10]


def _open_questions(profile: UserProfile, candidate_names: list[str]) -> list[str]:
    questions: list[str] = []
    if len(candidate_names) < 2:
        questions.append("need at least two candidate products")
    if profile.budget is None:
        questions.append("budget upper bound")
    if not profile.primary_scenarios:
        questions.append("primary usage scenarios")
    if profile.usage_years is None:
        questions.append("expected usage years")
    return questions[:5]


def _build_active_goal(candidate_names: list[str], intent: IntentResult | None) -> str | None:
    if not candidate_names:
        return None
    action = intent.intent if intent else "recommend"
    return f"{action}: " + " vs ".join(candidate_names[:3])


def _append_unique(items: list[str], value: str, *, limit: int) -> None:
    if value in items:
        return
    items.append(value)
    del items[:-limit]


def _scenario_label(scenario: Scenario | str) -> str:
    return scenario.value if isinstance(scenario, Scenario) else str(scenario)


memory_manager = MemoryManager()
