from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

IntentName = Literal["consult", "compare", "recommend", "profile_update", "other"]


class IntentResult(BaseModel):
    """Structured intent signal for routing the purchase conversation."""

    intent: IntentName
    confidence: float = Field(ge=0, le=1)
    products: list[str] = Field(default_factory=list)
    focus: list[str] = Field(default_factory=list)
    needs_realtime: bool = False
    reason: str = ""
