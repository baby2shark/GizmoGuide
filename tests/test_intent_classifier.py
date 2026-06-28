from app.agent.intent_classifier import IntentClassifier
from app.agent.purchase_agent import PurchaseDecisionAgent
from app.config.settings import Settings
from app.schemas.chat import ChatRequest


def test_classifies_single_product_consultation():
    result = IntentClassifier().classify("iPhone 15 有什么优缺点？")

    assert result.intent == "consult"
    assert result.products == ["iphone_15"]
    assert result.route == "consult_agent"
    assert "product_profile_kb" in result.retrieval_plan
    assert result.confidence >= 0.7


def test_classifies_dimension_comparison():
    result = IntentClassifier().classify(
        "这两款谁散热更好？",
        ["iphone_15", "vivo_x100"],
    )

    assert result.intent == "compare"
    assert "thermal" in result.focus
    assert result.route == "compare_agent"
    assert "comparison_kb" in result.retrieval_plan


def test_classifies_open_recommendation():
    result = IntentClassifier().classify("预算4000，推荐几款拍照好的安卓机")

    assert result.intent == "recommend"
    assert "camera" in result.focus
    assert result.route == "recommend_agent"
    assert "candidate_recall_kb" in result.retrieval_plan


def test_classifies_profile_update_with_existing_candidates():
    result = IntentClassifier().classify(
        "我主要拍照，预算5000",
        ["iphone_15", "vivo_x100"],
    )

    assert result.intent == "profile_update"
    assert "camera" in result.focus
    assert "price" in result.focus
    assert result.context_action == "update_profile"


def test_classifies_other():
    result = IntentClassifier().classify("你好")

    assert result.intent == "other"
    assert result.route == "fallback_agent"


def test_short_followup_uses_previous_context():
    previous = IntentClassifier().classify(
        "iPhone 15 和 vivo X100 哪个更适合拍照？",
        ["iphone_15", "vivo_x100"],
    )

    result = IntentClassifier().classify(
        "那售后呢？",
        ["iphone_15", "vivo_x100"],
        last_intent=previous,
        recent_messages=[{"role": "user", "content": "iPhone 15 和 vivo X100 哪个更适合拍照？"}],
    )

    assert result.intent == "compare"
    assert result.context_action == "continue_previous_task"
    assert "after_sales" in result.focus
    assert "after_sales_kb" in result.retrieval_plan


def test_realtime_query_adds_web_search_plan_and_risk_flag():
    result = IntentClassifier().classify("iPhone 15 现在还值得买吗？")

    assert result.intent == "consult"
    assert result.needs_realtime is True
    assert "web_search" in result.retrieval_plan
    assert "needs_realtime_evidence" in result.risk_flags


def test_chat_response_includes_intent(monkeypatch):
    monkeypatch.setattr(
        "app.agent.purchase_agent.get_settings",
        lambda: Settings(
            deepseek_api_key=None,
            deepseek_base_url="https://api.deepseek.com",
            deepseek_model="deepseek-chat",
            llm_timeout_seconds=1,
        ),
    )

    response = PurchaseDecisionAgent().chat(
        ChatRequest(
            session_id="test-intent-response",
            message="这两款谁售后更稳？",
            candidate_products=["iphone_15", "vivo_x100"],
        )
    )

    assert response.intent is not None
    assert response.intent.intent == "compare"
    assert response.agent_trace[0] == "intent:compare"
