from __future__ import annotations

from app.decision.engine import recommend
from app.schemas.product import ProductSpec
from app.schemas.recommendation import RecommendationResult
from app.schemas.user_profile import UserProfile


class ScoringTool:
    name = "scoring_guardrail_tool"

    def evaluate(self, products: list[ProductSpec], profile: UserProfile) -> RecommendationResult:
        return recommend(products, profile)