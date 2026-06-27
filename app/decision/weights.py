from __future__ import annotations

from app.schemas.user_profile import Scenario, UserProfile

BASE_WEIGHTS: dict[str, float] = {
    "price": 1.0,
    "performance": 1.0,
    "camera": 1.0,
    "battery": 1.0,
    "screen": 0.8,
    "portability": 0.7,
    "storage": 0.6,
    "stability": 0.8,
    "repair": 0.5,
}


def build_weights(profile: UserProfile) -> dict[str, float]:
    weights = BASE_WEIGHTS.copy()
    scenarios = set(profile.primary_scenarios)

    if Scenario.photo in scenarios:
        weights["camera"] += 1.4
        weights["screen"] += 0.4
    if Scenario.gaming in scenarios:
        weights["performance"] += 1.3
        weights["battery"] += 0.6
        weights["screen"] += 0.4
    if Scenario.elder in scenarios:
        weights["battery"] += 0.8
        weights["screen"] += 0.6
        weights["stability"] += 0.8
        weights["repair"] += 0.4
    if Scenario.student in scenarios:
        weights["price"] += 1.2
        weights["battery"] += 0.4
        weights["repair"] += 0.3
    if Scenario.business in scenarios:
        weights["battery"] += 0.7
        weights["portability"] += 0.6
        weights["stability"] += 0.7
    if Scenario.travel in scenarios:
        weights["battery"] += 0.9
        weights["camera"] += 0.4
        weights["portability"] += 0.3

    if profile.is_budget_sensitive:
        weights["price"] += 0.8
    if profile.repair_sensitivity == "high":
        weights["repair"] += 1.0
    if profile.usage_years and profile.usage_years >= 3:
        weights["stability"] += 0.4
        weights["repair"] += 0.4

    return weights
