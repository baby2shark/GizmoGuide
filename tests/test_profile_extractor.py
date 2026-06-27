from app.orchestrator.profile_extractor import build_clarification_questions, extract_profile
from app.schemas.user_profile import Scenario


def test_extract_profile_from_chinese_message():
    profile = extract_profile("预算5000，主要拍照和日常用，想用三年，也在意维修")
    assert profile.budget == 5000
    assert Scenario.photo in profile.primary_scenarios
    assert Scenario.daily in profile.primary_scenarios
    assert profile.usage_years == 3
    assert profile.repair_sensitivity == "high"


def test_clarification_questions_when_profile_missing_core_fields():
    profile = extract_profile("帮我看看 iPhone 15 和 vivo X100")
    questions = build_clarification_questions(profile)
    fields = {item["field"] for item in questions}
    assert {"budget", "primary_scenarios", "usage_years"}.issubset(fields)
