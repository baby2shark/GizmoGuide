from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.user_profile import UserProfile


MemoryEventType = Literal[
    "user_message",
    "assistant_message",
    "intent_detected",
    "profile_updated",
    "tool_evidence",
    "recommendation_decision",
    "fallback_used",
]


class MemoryEvent(BaseModel):
    """Append-only memory event used to rebuild session state."""

    event_type: MemoryEventType
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SessionSummary(BaseModel):
    """Compressed working memory injected into the agent context."""

    active_goal: str | None = None
    known_constraints: list[str] = Field(default_factory=list)
    candidate_products: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    evidence_summary: list[str] = Field(default_factory=list)
    last_intent: str | None = None
    message_count: int = 0


class MemoryContext(BaseModel):
    """Shared context exposed to intent, retrieval, search, and decision agents."""

    session_id: str
    profile: UserProfile
    summary: SessionSummary
    recent_events: list[MemoryEvent] = Field(default_factory=list)

