from __future__ import annotations

from app.config.settings import Settings
from app.tools.web_search_tool import WebSearchTool


def _settings(**overrides) -> Settings:
    base = dict(
        deepseek_api_key=None,
        deepseek_base_url="https://api.deepseek.com",
        deepseek_model="deepseek-chat",
        llm_timeout_seconds=1,
        bocha_api_key="test-key",
        bocha_base_url="https://api.bochaai.com",
        web_search_timeout_seconds=5,
        web_search_cache_ttl_seconds=3600,
        agent_max_tool_rounds=4,
    )
    base.update(overrides)
    return Settings(**base)


_FAKE_RESPONSE = {
    "data": {
        "webPages": {
            "value": [
                {
                    "name": "iPhone 15 用一年真实体验",
                    "siteName": "小红书",
                    "url": "https://example.com/a",
                    "datePublished": "2025-01-01T00:00:00+08:00",
                    "summary": "续航日常够用，发热在游戏时明显。" * 30,
                    "snippet": "snippet fallback",
                }
            ]
        }
    }
}


def test_web_search_summarizes_and_caches(monkeypatch):
    tool = WebSearchTool(_settings())
    calls = {"n": 0}

    def fake_call(query, count):
        calls["n"] += 1
        return _FAKE_RESPONSE

    monkeypatch.setattr(tool, "_call_bocha", fake_call)

    first = tool.run("iPhone 15 续航", count=3)
    assert first["status"] == "ok"
    assert first["result_count"] == 1
    assert first["cached"] is False
    result = first["results"][0]
    assert result["site"] == "小红书"
    assert result["url"] == "https://example.com/a"
    assert len(result["summary"]) <= 401  # truncated with ellipsis

    second = tool.run("iPhone 15 续航", count=3)
    assert second["cached"] is True
    assert calls["n"] == 1  # served from cache, no second network call


def test_web_search_empty_query_is_structured_error():
    tool = WebSearchTool(_settings())
    result = tool.run("  ")
    assert result["status"] == "error"
    assert "query" in result["error"]


def test_web_search_network_failure_is_structured_error(monkeypatch):
    tool = WebSearchTool(_settings())

    def boom(query, count):
        raise RuntimeError("Bocha network error: timeout")

    monkeypatch.setattr(tool, "_call_bocha", boom)
    result = tool.run("vivo X100 拍照")
    assert result["status"] == "error"
    assert "hint" in result
