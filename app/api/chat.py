from __future__ import annotations

import contextvars

from fastapi import APIRouter

from app.agent.purchase_agent import PurchaseDecisionAgent
from app.schemas.chat import ChatRequest, ChatResponse
from app.tracing import trace_request

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    with trace_request(
        session_id=request.session_id,
        user_id=request.user_id,
        input_data=request.model_dump(mode="json"),
    ) as trace:
        agent = PurchaseDecisionAgent()
        ctx = contextvars.copy_context()
        response = ctx.run(agent.chat, request)
        if trace:
            trace.update(output={"mode": response.mode, "answer_source": response.answer_source})
        return response
