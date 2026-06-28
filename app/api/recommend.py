from __future__ import annotations

import contextvars

from fastapi import APIRouter

from app.agent.purchase_agent import PurchaseDecisionAgent
from app.orchestrator.conversation import handle_recommendation
from app.schemas.recommendation import RecommendationRequest, RecommendationResponse
from app.tracing import trace_request

router = APIRouter(tags=["recommendation"])


@router.post("/recommend", response_model=RecommendationResponse)
def create_recommendation(request: RecommendationRequest) -> RecommendationResponse:
    with trace_request(
        session_id=f"recommend-{request.user_message[:20]}",
        input_data=request.model_dump(mode="json"),
        metadata={"endpoint": "/recommend"},
    ) as trace:
        agent = PurchaseDecisionAgent()
        ctx = contextvars.copy_context()
        response = ctx.run(agent.handle, request)
        if trace:
            trace.update(output={"answer_source": response.answer_source})
        return response
