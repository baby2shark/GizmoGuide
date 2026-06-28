from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.schemas.intent import IntentResult
from app.memory.models import SessionSummary
from app.schemas.product import ProductSpec
from app.schemas.user_profile import UserProfile


@dataclass
class ConversationState:
    session_id: str
    candidate_products: list[ProductSpec] = field(default_factory=list)
    profile: UserProfile = field(default_factory=UserProfile)
    messages: list[dict[str, str]] = field(default_factory=list)
    agent_messages: list[Any] = field(default_factory=list)
    last_intent: IntentResult | None = None
    memory_summary: SessionSummary = field(default_factory=SessionSummary)


class InMemorySessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, ConversationState] = {}

    def get(self, session_id: str) -> ConversationState:
        if session_id not in self._sessions:
            self._sessions[session_id] = ConversationState(session_id=session_id)
        return self._sessions[session_id]


session_store = InMemorySessionStore()
