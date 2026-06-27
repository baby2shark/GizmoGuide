from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ProductSpec(BaseModel):
    id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    category: Literal["phone"] = "phone"
    brand: str
    os: Literal["ios", "android"]
    price: int = Field(ge=0)
    release_year: int
    chip_tier: int = Field(ge=1, le=10)
    camera_tier: int = Field(ge=1, le=10)
    battery_tier: int = Field(ge=1, le=10)
    screen_tier: int = Field(ge=1, le=10)
    portability_tier: int = Field(ge=1, le=10)
    stability_tier: int = Field(ge=1, le=10)
    storage_gb: int = Field(ge=0)
    weight_g: int = Field(ge=0)
    repair_risk: Literal["low", "medium", "high"] = "medium"
    notes: list[str] = Field(default_factory=list)
