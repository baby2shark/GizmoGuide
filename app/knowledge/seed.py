"""Seed the knowledge base from local JSON data on first startup."""
from __future__ import annotations

import json
import logging
from pathlib import Path

import jieba

from app.embedding.client import EmbeddingClient
from app.knowledge.models import KnowledgeChunk
from app.knowledge.store import KnowledgeStore

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "data"


def tokenize_chinese(text: str) -> str:
    """Tokenize Chinese text using jieba."""
    tokens = jieba.lcut(text)
    return " ".join(t.strip() for t in tokens if t.strip())


def load_seed_knowledge() -> list[dict]:
    """Load seed knowledge from all JSON files in the data directory."""
    if not DATA_DIR.exists():
        logger.warning("Knowledge data directory not found at %s", DATA_DIR)
        return []

    documents: list[dict] = []
    for file_path in sorted(DATA_DIR.glob("*.json")):
        with open(file_path, "r", encoding="utf-8") as f:
            file_documents = json.load(f)
        if not isinstance(file_documents, list):
            logger.warning("Skipping non-list knowledge file: %s", file_path)
            continue
        documents.extend(file_documents)
        logger.info("Loaded %d knowledge chunks from %s", len(file_documents), file_path.name)

    return documents


def seed_knowledge(store: KnowledgeStore, embedder: EmbeddingClient) -> int:
    """Seed the knowledge base with local JSON data if it's empty.

    Returns the number of chunks seeded.
    """
    existing_count = store.count()
    if existing_count > 0:
        logger.info("Knowledge base already has %d chunks, skipping seed", existing_count)
        return 0

    seed_data = load_seed_knowledge()
    if not seed_data:
        logger.warning("No knowledge data to seed")
        return 0

    logger.info("Seeding %d knowledge chunks...", len(seed_data))

    # Generate embeddings in batches
    batch_size = 5
    chunks: list[KnowledgeChunk] = []

    for i in range(0, len(seed_data), batch_size):
        batch = seed_data[i : i + batch_size]
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
