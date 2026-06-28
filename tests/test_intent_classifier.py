from app.agent.intent_classifier import IntentClassifier
from app.agent.purchase_agent import PurchaseDecisionAgent
from app.config.settings import Settings
from app.schemas.chat import ChatRequest


def test_classifies_single_product_consultation():
    result = IntentClassifier().classify("iPhone 15 有什么优缺点？")

    assert result.intent == "consult"
    assert result.products == ["iphone_15"]


def test_classifies_dimension_comparison():
    result = IntentClassifier().classify(
        "这两款谁散热更好？",
        ["iphone_15", "vivo_x100"],
    )

    assert result.intent == "compare"
    assert "thermal" in result.focus


def test_classifies_open_recommendation():
    result = IntentClassifier().classify("预算4000，推荐几款拍照好的安卓机")

    assert result.intent == "recommend"
    assert "camera" in result.focus


def test_classifies_profile_update_with_existing_candidates():
    result = IntentClassifier().classify(
        "我主要拍照，预算5000",
        ["iphone_15", "vivo_x100"],
    )

    assert result.intent == "profile_update"
    assert "camera" in result.focus
    assert "price" in result.focus


def test_classifies_other():
    result = IntentClassifier().classify("你好")

    assert result.intent == "other"


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
