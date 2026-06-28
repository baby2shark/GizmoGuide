"""Seed the knowledge base from mock data on first startup."""
from __future__ import annotations

import json
import logging
from pathlib import Path

import jieba

from app.embedding.client import EmbeddingClient
from app.knowledge.models import KnowledgeChunk
from app.knowledge.store import KnowledgeStore

logger = logging.getLogger(__name__)

MOCK_DATA_PATH = Path(__file__).parent / "data" / "mock_knowledge.json"


def tokenize_chinese(text: str) -> str:
    """Tokenize Chinese text using jieba."""
    tokens = jieba.lcut(text)
    return " ".join(t.strip() for t in tokens if t.strip())


def load_mock_knowledge() -> list[dict]:
    """Load mock knowledge data from JSON file."""
    if not MOCK_DATA_PATH.exists():
        logger.warning("Mock knowledge data not found at %s", MOCK_DATA_PATH)
        return []
    with open(MOCK_DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def seed_knowledge(store: KnowledgeStore, embedder: EmbeddingClient) -> int:
    """Seed the knowledge base with mock data if it's empty.

    Returns the number of chunks seeded.
    """
    existing_count = store.count()
    if existing_count > 0:
        logger.info("Knowledge base already has %d chunks, skipping seed", existing_count)
        return 0

    mock_data = load_mock_knowledge()
    if not mock_data:
        logger.warning("No mock knowledge data to seed")
        return 0

    logger.info("Seeding %d knowledge chunks...", len(mock_data))

    # Generate embeddings in batches
    batch_size = 5
    chunks: list[KnowledgeChunk] = []

    for i in range(0, len(mock_data), batch_size):
        batch = mock_data[i : i + batch_size]
        texts = [f"{item['title']}\n{item['content']}" for item in batch]

        try:
            embeddings = embedder.embed(texts)
        except Exception as exc:
            logger.error("Embedding generation failed for batch %d: %s", i // batch_size, exc)
            embeddings = [[0.0] * 1024] * len(batch)

        for item, embedding in zip(batch, embeddings):
            content_text = f"{item['title']} {item['content']}"
            tokenized = tokenize_chinese(content_text)
            chunk = KnowledgeChunk(
                chunk_id=item["chunk_id"],
                category=item["category"],
                title=item["title"],
                content=item["content"],
                tokenized=tokenized,
                tags=item.get("tags", []),
                source=item.get("source", "mock"),
                embedding=embedding,
            )
            chunks.append(chunk)

    count = store.upsert_chunks(chunks)
    logger.info("Seeded %d knowledge chunks into the knowledge base", count)
    return count
