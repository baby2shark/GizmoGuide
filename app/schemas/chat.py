from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.intent import IntentResult
from app.memory.models import SessionSummary
from app.schemas.product import ProductSpec
from app.schemas.recommendation import RecommendationResult
from app.schemas.user_profile import UserProfile


class ChatRequest(BaseModel):
    session_id: str = "default"
    message: str
    candidate_products: list[str] = Field(default_factory=list)


class ChatResponse(BaseModel):
    session_id: str
    mode: Literal["chat", "recommendation"]
    assistant_message: str
    user_profile: UserProfile
    products: list[ProductSpec] = Field(default_factory=list)
    recommendation: RecommendationResult | None = None
    answer_source: str = "fallback"
    agent_trace: list[str] = Field(default_factory=list)
    intent: IntentResult | None = None
    memory_context: SessionSummary | None = None
