"""Knowledge base data models."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class KnowledgeChunk:
    """A single chunk of domain knowledge."""

    chunk_id: str
    category: str
    title: str
    content: str
    tokenized: str
    tags: list[str]
    source: str
    embedding: list[float] | None = None

    def to_insert_params(self) -> tuple:
        return (self.chunk_id, self.category, self.title, self.content, self.tokenized, self.tags, self.source, self.embedding)


@dataclass
class RetrievedChunk:
    """A chunk retrieved from the knowledge base with relevance metadata."""

    chunk_id: str
    category: str
    title: str
    content: str
    tags: list[str]
    source: str
    score: float = 0.0
    retrieval_path: str = "unknown"  # "bm25", "vector", "rrf", "rerank"

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "category": self.category,
            "title": self.title,
            "content": self.content,
            "tags": self.tags,
            "source": self.source,
            "score": round(self.score, 4),
            "retrieval_path": self.retrieval_path,
        }
