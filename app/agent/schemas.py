from __future__ import annotations

from pydantic import BaseModel, Field


class AgentDecision(BaseModel):
    winner_id: str
    winner_name: str
    confidence: float = Field(ge=0, le=1)
    summary: str
    key_reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    reversal_conditions: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    evidence_used: list[str] = Field(default_factory=list)


class ToolEvidence(BaseModel):
    id: str
    source: str
    claim: str
    confidence: float = Field(ge=0, le=1)