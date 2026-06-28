"""DashScope text-embedding-v3 client (urllib, no extra deps)."""
from __future__ import annotations

import json
import logging
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

_client: EmbeddingClient | None = None


class EmbeddingClient:
    """Wraps DashScope text-embedding-v3 for generating dense vectors."""

    DASHSCOPE_EMBED_URL = "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding"

    def __init__(self, api_key: str, model: str = "text-embedding-v3", dimensions: int = 1024, timeout: float = 15.0):
        self.api_key = api_key
        self.model = model
        self.dimensions = dimensions
        self.timeout = timeout

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed one or more texts. Returns a list of vectors (one per text)."""
        if not texts:
            return []
        if not self.api_key:
            logger.warning("DASHSCOPE_API_KEY not set, returning zero vectors")
            return [[0.0] * self.dimensions for _ in texts]

        payload = {
            "model": self.model,
            "input": {"texts": texts},
            "parameters": {"dimension": self.dimensions, "text_type": "document"},
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            self.DASHSCOPE_EMBED_URL,
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
            logger.error("DashScope embedding API call failed: %s", exc)
            raise

        embeddings = body.get("output", {}).get("embeddings", [])
        sorted_emb = sorted(embeddings, key=lambda x: x.get("text_index", 0))
        return [e["embedding"] for e in sorted_emb]

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query text (uses document type; works for queries too with v3)."""
        results = self.embed([text])
        return results[0] if results else [0.0] * self.dimensions


def get_embedding_client(api_key: str | None = None, **kwargs: Any) -> EmbeddingClient | None:
    """Get or create the singleton embedding client."""
    global _client
    if _client is not None:
        return _client
    if not api_key:
        return None
    _client = EmbeddingClient(api_key, **kwargs)
    return _client
