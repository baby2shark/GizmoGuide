from app.agent.state import session_store
from app.config.settings import Settings
from app.agent.purchase_agent import PurchaseDecisionAgent
from app.schemas.chat import ChatRequest


def disable_llm(monkeypatch):
    monkeypatch.setattr(
        "app.agent.purchase_agent.get_settings",
        lambda: Settings(
            deepseek_api_key=None,
            deepseek_base_url="https://api.deepseek.com",
            deepseek_model="deepseek-chat",
            llm_timeout_seconds=1,
        ),
    )


def test_chat_agent_asks_naturally_when_budget_missing(monkeypatch):
    disable_llm(monkeypatch)
    agent = PurchaseDecisionAgent()
    response = agent.chat(
        ChatRequest(
            session_id="test-chat-missing",
            message="我想买一台",
            candidate_products=["iphone_15", "vivo_x100"],
        )
    )
    assert response.mode == "chat"
    assert response.recommendation is None
    assert "预算" in response.assistant_message


def test_chat_agent_recommends_when_signal_is_enough(monkeypatch):
    disable_llm(monkeypatch)
    agent = PurchaseDecisionAgent()
    response = agent.chat(
        ChatRequest(
            session_id="test-chat-recommend",
            message="预算5000，主要拍照和日常用，想用三年，也在意维修",
            candidate_products=["iphone_15", "vivo_x100"],
        )
    )
    assert response.mode == "recommendation"
    assert response.recommendation is not None
    assert response.answer_source == "fallback"