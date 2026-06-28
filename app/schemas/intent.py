from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

IntentName = Literal["consult", "compare", "recommend", "profile_update", "other"]
RouteName = Literal[
    "consult_agent",
    "compare_agent",
    "recommend_agent",
    "profile_agent",
    "fallback_agent",
]
ContextAction = Literal["new_task", "continue_previous_task", "update_profile", "clarify"]
RetrievalTarget = Literal[
    "product_profile_kb",
    "comparison_kb",
    "candidate_recall_kb",
    "after_sales_kb",
    "review_kb",
    "web_search",
]


class IntentResult(BaseModel):
    """Structured routing decision for the purchase conversation.

    ``intent`` is kept as a compact backward-compatible primary intent. The
    remaining fields make the decision usable by an enterprise-style
    orchestrator: route selection, retrieval planning, risk flags and evidence.
    """

    intent: IntentName
    secondary_intents: list[IntentName] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    products: list[str] = Field(default_factory=list)
    focus: list[str] = Field(default_factory=list)
    needs_realtime: bool = False
    needs_clarification: bool = False
    route: RouteName = "fallback_agent"
    retrieval_plan: list[RetrievalTarget] = Field(default_factory=list)
    context_action: ContextAction = "new_task"
    risk_flags: list[str] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)
    reason: str = ""
