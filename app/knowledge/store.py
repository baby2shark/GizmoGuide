"""Knowledge base PostgreSQL store — BM25 via tsvector + Python cosine for vectors."""
from __future__ import annotations

import json
import logging
import math
from typing import Any

import psycopg

from app.knowledge.models import KnowledgeChunk, RetrievedChunk

logger = logging.getLogger(__name__)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class KnowledgeStore:
    """PostgreSQL-backed knowledge base.

    - BM25 keyword search: Postgres tsvector + jieba pre-tokenization
    - Vector search: embeddings stored as JSONB, cosine similarity in Python
    """

    def __init__(self, database_url: str):
        self.database_url = database_url

    def _get_connection(self) -> psycopg.Connection:
        return psycopg.connect(self.database_url)

    def ensure_schema(self) -> None:
        """Create tables and indexes if they don't exist (idempotent)."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_base (
                    id SERIAL PRIMARY KEY,
                    chunk_id TEXT UNIQUE NOT NULL,
                    category TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tokenized TEXT NOT NULL DEFAULT '',
                    tags TEXT[] NOT NULL DEFAULT '{}',
                    source TEXT NOT NULL DEFAULT 'mock',
                    embedding JSONB,
                    content_tsv tsvector,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_kb_tsv ON knowledge_base USING gin(content_tsv);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_kb_category ON knowledge_base(category);")
            conn.commit()
        logger.info("Knowledge base schema ensured")

    def upsert_chunks(self, chunks: list[KnowledgeChunk]) -> int:
        """Insert or update knowledge chunks."""
        if not chunks:
            return 0
        count = 0
        with self._get_connection() as conn:
            for chunk in chunks:
                embedding_json = json.dumps(chunk.embedding) if chunk.embedding else None
                conn.execute(
                    """
                    INSERT INTO knowledge_base (chunk_id, category, title, content, tokenized, tags, source, embedding, content_tsv)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, to_tsvector('simple', %s))
                    ON CONFLICT (chunk_id) DO UPDATE SET
                        category = EXCLUDED.category,
                        title = EXCLUDED.title,
                        content = EXCLUDED.content,
                        tokenized = EXCLUDED.tokenized,
                        tags = EXCLUDED.tags,
                        source = EXCLUDED.source,
                        embedding = EXCLUDED.embedding,
                        content_tsv = EXCLUDED.content_tsv,
                        updated_at = NOW()
                    """,
                    (
                        chunk.chunk_id, chunk.category, chunk.title, chunk.content,
                        chunk.tokenized, chunk.tags, chunk.source,
                        embedding_json, chunk.tokenized,
                    ),
                )
                count += 1
            conn.commit()
        logger.info("Upserted %d knowledge chunks", count)
        return count

    def count(self) -> int:
        with self._get_connection() as conn:
            row = conn.execute("SELECT COUNT(*) FROM knowledge_base").fetchone()
            return row[0] if row else 0

    def vector_search(self, query_embedding: list[float], top_k: int = 10) -> list[RetrievedChunk]:
        """Dense vector similarity search — cosine similarity computed in Python.

        Loads all embeddings from DB (fine for <10k chunks), ranks by cosine similarity.
        """
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT chunk_id, category, title, content, tags, source, embedding FROM knowledge_base WHERE embedding IS NOT NULL",
            ).fetchall()

        scored: list[tuple[float, tuple]] = []
        for row in rows:
            emb = row[6]
            if emb is None:
                continue
            if isinstance(emb, str):
                emb = json.loads(emb)
            sim = _cosine_similarity(query_embedding, emb)
            scored.append((sim, row))

        scored.sort(key=lambda x: x[0], reverse=True)

        return [
            RetrievedChunk(
                chunk_id=r[0], category=r[1], title=r[2], content=r[3],
                tags=r[4], source=r[5], score=sim, retrieval_path="vector",
            )
            for sim, r in scored[:top_k]
        ]

    def keyword_search(self, query_text: str, top_k: int = 10) -> list[RetrievedChunk]:
        """BM25-style keyword search using tsvector + jieba-tokenized query.

        Uses OR logic (any token can match) for better recall.
        """
        # Convert "跑步 蓝牙 耳机" to "跑步 | 蓝牙 | 耳机" for OR matching
        tokens = [t.strip() for t in query_text.split() if t.strip()]
        if not tokens:
            return []
        or_query = " | ".join(tokens)

        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT chunk_id, category, title, content, tags, source,
                       ts_rank(content_tsv, to_tsquery('simple', %s)) AS rank
                FROM knowledge_base
                WHERE content_tsv @@ to_tsquery('simple', %s)
                ORDER BY rank DESC
                LIMIT %s
                """,
                (or_query, or_query, top_k),
            ).fetchall()

        return [
            RetrievedChunk(
                chunk_id=r[0], category=r[1], title=r[2], content=r[3],
                tags=r[4], source=r[5], score=float(r[6]), retrieval_path="bm25",
            )
            for r in rows
        ]

    def get_chunks_by_ids(self, chunk_ids: list[str]) -> list[RetrievedChunk]:
        if not chunk_ids:
            return []
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT chunk_id, category, title, content, tags, source FROM knowledge_base WHERE chunk_id = ANY(%s)",
                (chunk_ids,),
            ).fetchall()
        return [
            RetrievedChunk(
                chunk_id=r[0], category=r[1], title=r[2], content=r[3],
                tags=r[4], source=r[5],
            )
            for r in rows
        ]
