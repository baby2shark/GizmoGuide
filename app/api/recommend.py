from __future__ import annotations

from fastapi import APIRouter

from app.orchestrator.conversation import handle_recommendation
from app.schemas.recommendation import RecommendationRequest, RecommendationResponse

router = APIRouter(tags=["recommendation"])


@router.post("/recommend", response_model=RecommendationResponse)
def create_recommendation(request: RecommendationRequest) -> RecommendationResponse:
    return handle_recommendation(request)
