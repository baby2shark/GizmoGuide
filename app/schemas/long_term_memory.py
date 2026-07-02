from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.user_profile import UserProfile


class UserPreferenceMemory(BaseModel):
    category: Literal["phone"] = "phone"
    os_preference: Literal["ios", "android"] | None = None
    preferred_brands: list[str] = Field(default_factory=list)
    avoided_brands: list[str] = Field(default_factory=list)
    preferred_features: list[str] = Field(default_factory=list)
    disliked_features: list[str] = Field(default_factory=list)
    budget_flexibility: Literal["low", "medium", "high"] = "medium"
    risk_tolerance: Literal["low", "medium", "high"] = "medium"
    repair_sensitivity: Literal["low", "medium", "high"] = "medium"
    notes: list[str] = Field(default_factory=list)


class LongTermMemory(BaseModel):
    user_id: str
    preference_memory: UserPreferenceMemory = Field(default_factory=UserPreferenceMemory)
    profile_memory: UserProfile = Field(default_factory=UserProfile)
