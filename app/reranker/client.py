"""DashScope gte-rerank cross-encoder client (urllib, no extra deps)."""
from __future__ import annotations

import json
import logging
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

_client: RerankerClient | None = None


class RerankerClient:
    """Wraps DashScope gte-rerank for cross-encoder relevance scoring."""

    DASHSCOPE_RERANK_URL = "https://dashscope.aliyuncs.com/api/v1/services/rerank"

    def __init__(self, api_key: str, model: str = "gte-rerank", top_n: int = 5, timeout: float = 15.0):
        self.api_key = api_key
        self.model = model
        self.top_n = top_n
        self.timeout = timeout

    def rerank(self, query: str, documents: list[str]) -> list[dict[str, Any]]:
        """Rerank documents by relevance to query.

        Returns list of {"index": int, "relevance_score": float, "document": str}
        sorted by relevance_score descending.
        """
        if not documents:
            return []
        if not self.api_key:
            logger.warning("DASHSCOPE_API_KEY not set, returning original order")
            return [{"index": i, "relevance_score": 1.0 - i * 0.01, "document": d} for i, d in enumerate(documents)]

        payload = {
            "model": self.model,
            "input": {"query": query, "documents": documents},
            "parameters": {"top_n": self.top_n, "return_documents": True},
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            self.DASHSCOPE_RERANK_URL,
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            logger.error("DashScope rerank API call failed: %s", exc)
            raise

        results = body.get("output", {}).get("results", [])
        results.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

        # Attach original document text
        for r in results:
            idx = r.get("index", 0)
            if 0 <= idx < len(documents):
                r["document"] = documents[idx]

        return results


def get_reranker_client(api_key: str | None = None, **kwargs: Any) -> RerankerClient | None:
    """Get or create the singleton reranker client."""
    global _client
    if _client is not None:
        return _client
    if not api_key:
        return None
    _client = RerankerClient(api_key, **kwargs)
    return _client
