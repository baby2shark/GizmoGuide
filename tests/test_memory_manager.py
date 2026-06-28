from app.memory.manager import MemoryManager
from app.schemas.intent import IntentResult
from app.schemas.product import ProductSpec
from app.schemas.user_profile import Scenario, UserProfile


def _phone(product_id: str, name: str) -> ProductSpec:
    return ProductSpec(
        id=product_id,
        name=name,
        brand=name.split()[0],
        os="ios" if "iPhone" in name else "android",
        price=4999,
        release_year=2024,
        chip_tier=8,
        camera_tier=8,
        battery_tier=8,
        screen_tier=8,
        portability_tier=8,
        stability_tier=8,
        storage_gb=256,
        weight_g=190,
    )


def test_memory_manager_projects_profile_and_compressed_summary():
    manager = MemoryManager()
    session_id = "memory-test"
    profile = UserProfile(
        budget=5000,
        primary_scenarios=[Scenario.photo, Scenario.daily],
        usage_years=3,
        repair_sensitivity="high",
    )
    intent = IntentResult(
        intent="compare",
        confidence=0.9,
        products=["iphone_15", "vivo_x100"],
        focus=["camera"],
        needs_realtime=True,
        needs_clarification=False,
        route="compare_agent",
        retrieval_plan=["comparison_kb", "web_search"],
        context_action="new_task",
        risk_flags=[],
        evidence={},
        reason="test",
    )

    manager.remember_user_message(session_id, "预算5000，主要拍照和日常用，也在意维修")
    manager.remember_intent(session_id, intent)
    manager.remember_profile(session_id, profile)
    manager.remember_tool_evidence(session_id, "web_search", "found recent repair-risk reviews")

    summary = manager.compress(
        session_id,
        profile=profile,
        candidates=[_phone("iphone_15", "iPhone 15"), _phone("vivo_x100", "vivo X100")],
        intent=intent,
    )
    context = manager.get_context(session_id)

    assert summary.active_goal == "compare: iPhone 15 vs vivo X100"
    assert "budget <= 5000" in summary.known_constraints
    assert "repair risk sensitive" in summary.known_constraints
    assert summary.last_intent == "compare"
    assert context.profile.budget == 5000
    assert context.summary.evidence_summary == ["web_search: found recent repair-risk reviews"]
