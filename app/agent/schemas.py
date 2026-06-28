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


class AgentResponse(BaseModel):
    """Structured output from the agent loop.

    The agent always returns this model. ``reply`` is the user-facing natural
    language message. The remaining fields carry the structured decision
    metadata that the downstream scoring engine and tracing consume.
    """

    reply: str = Field(description="给用户看的自然语言回复，口语化、有观点。")
    winner_id: str | None = Field(
        default=None,
        description="推荐的商品 id。没有足够信息推荐时填 null。",
    )
    winner_name: str | None = Field(
        default=None,
        description="推荐的商品名称。没有足够信息推荐时填 null。",
    )
    confidence: float = Field(
        default=0.0,
        ge=0,
        le=1,
        description="推荐置信度。0.0 表示还在聊天/收集信息阶段，无法给出推荐。",
    )
    key_reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)