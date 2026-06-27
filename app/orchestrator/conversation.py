from __future__ import annotations

from app.agent.purchase_agent import PurchaseDecisionAgent
from app.schemas.recommendation import RecommendationRequest, RecommendationResponse


def handle_recommendation(request: RecommendationRequest) -> RecommendationResponse:
    return PurchaseDecisionAgent().handle(request)