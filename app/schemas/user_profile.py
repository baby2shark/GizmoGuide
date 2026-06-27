from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Scenario(str, Enum):
    photo = "photo"
    gaming = "gaming"
    daily = "daily"
    business = "business"
    elder = "elder"
    student = "student"
    travel = "travel"


class UserProfile(BaseModel):
    category: Literal["phone"] = "phone"
    budget: int | None = Field(default=None, ge=0)
    budget_flexibility: Literal["low", "medium", "high"] = "medium"
    primary_scenarios: list[Scenario] = Field(default_factory=list)
    usage_years: int | None = Field(default=None, ge=1, le=8)
    brand_preference: str | None = None
    os_preference: Literal["ios", "android"] | None = None
    risk_tolerance: Literal["low", "medium", "high"] = "medium"
    repair_sensitivity: Literal["low", "medium", "high"] = "medium"
    min_storage_gb: int | None = Field(default=None, ge=0)
    max_weight_g: int | None = Field(default=None, ge=0)
    notes: list[str] = Field(default_factory=list)

    @property
    def is_budget_sensitive(self) -> bool:
        return self.budget_flexibility == "low" or self.risk_tolerance == "low"
