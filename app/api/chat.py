from __future__ import annotations

from fastapi import APIRouter

from app.agent.purchase_agent import PurchaseDecisionAgent
from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    return PurchaseDecisionAgent().chat(request)