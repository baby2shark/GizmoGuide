from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.schemas.long_term_memory import LongTermMemory
from app.schemas.product import ProductSpec
from app.schemas.user_profile import UserProfile


@dataclass
class ConversationState:
    session_id: str
    user_id: str | None = None
    candidate_products: list[ProductSpec] = field(default_factory=list)
    profile: UserProfile = field(default_factory=UserProfile)
    messages: list[dict[str, str]] = field(default_factory=list)
    agent_messages: list[Any] = field(default_factory=list)


class InMemorySessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, ConversationState] = {}

    def get(self, session_id: str) -> ConversationState:
        if session_id not in self._sessions:
            self._sessions[session_id] = ConversationState(session_id=session_id)
        return self._sessions[session_id]


class InMemoryLongTermMemoryStore:
    def __init__(self) -> None:
        self._memories: dict[str, LongTermMemory] = {}

    def get(self, user_id: str) -> LongTermMemory:
        if user_id not in self._memories:
            self._memories[user_id] = LongTermMemory(user_id=user_id)
        return self._memories[user_id]


session_store = InMemorySessionStore()
long_term_memory_store = InMemoryLongTermMemoryStore()
