from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

import certifi

from app.config.settings import Settings

TOOL_NAME = "web_search"


@dataclass
class _CacheEntry:
    expires_at: float
    payload: dict[str, Any]


class WebSearchTool:
    name = TOOL_NAME

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._cache: dict[str, _CacheEntry] = {}

    @property
    def enabled(self) -> bool:
        return self.settings.web_search_enabled

    def run(self, query: str, count: int = 6) -> dict[str, Any]:
        """Execute a search and return a compact, model-friendly result.

        Always returns a dict with a ``status`` field so the agent loop can
        feed errors back to the model instead of crashing.
        """
        query = (query or "").strip()
        if not query:
            return {"status": "error", "error": "query 不能为空", "hint": "请提供商品名和关注维度。"}

        count = max(1, min(int(count or 6), 10))
        cache_key = f"{query}::{count}"

        cached = self._cache.get(cache_key)
        if cached and cached.expires_at > time.monotonic():
            return {**cached.payload, "cached": True}

        try:
            raw = self._call_bocha(query, count)
        except Exception as exc:  # noqa: BLE001 - surface as structured error to the model
            return {
                "status": "error",
                "error": f"联网搜索失败：{type(exc).__name__}",
                "hint": "可以换个关键词重试，或先基于已有信息回答并说明未拿到联网证据。",
            }

        payload = self._summarize(query, raw)
        self._cache[cache_key] = _CacheEntry(
            expires_at=time.monotonic() + self.settings.web_search_cache_ttl_seconds,
            payload=payload,
        )
        return {**payload, "cached": False}

    def _call_bocha(self, query: str, count: int) -> dict[str, Any]:
        if not self.settings.bocha_api_key:
            raise RuntimeError("BOCHA_API_KEY is not configured.")

        url = self.settings.bocha_base_url.rstrip("/") + "/v1/web-search"
        body = json.dumps(
            {"query": query, "summary": True, "count": count, "freshness": "noLimit"},
            ensure_ascii=False,
        ).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {self.settings.bocha_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            with urllib.request.urlopen(
                request, timeout=self.settings.web_search_timeout_seconds, context=ssl_context
            ) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Bocha API error {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Bocha network error: {exc.reason}") from exc

        return json.loads(raw)

    def _summarize(self, query: str, raw: dict[str, Any]) -> dict[str, Any]:
        pages = self._extract_pages(raw)
        results = []
        for page in pages:
            text = page.get("summary") or page.get("snippet") or ""
            results.append(
                {
                    "title": page.get("name"),
                    "site": page.get("siteName"),
                    "url": page.get("url"),
                    "published": page.get("datePublished"),
                    "summary": _truncate(text, 400),
                }
            )

        return {
            "status": "ok",
            "query": query,
            "result_count": len(results),
            "results": results,
        }

    @staticmethod
    def _extract_pages(raw: dict[str, Any]) -> list[dict[str, Any]]:
        # Bocha 的响应在不同接入下可能是 {data:{webPages:...}} 或 {webPages:...}
        container = raw.get("data") if isinstance(raw.get("data"), dict) else raw
        web_pages = (container or {}).get("webPages") or {}
        value = web_pages.get("value")
        return value if isinstance(value, list) else []


def _truncate(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"
