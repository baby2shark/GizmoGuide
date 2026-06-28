"""End-to-end RAG pipeline: query → dual recall → RRF → rerank → results."""
from __future__ import annotations

import logging
from typing import Any

from app.embedding.client import EmbeddingClient
from app.knowledge.models import RetrievedChunk
from app.knowledge.retrieval.dual_recall import dual_recall
from app.knowledge.retrieval.rrf import reciprocal_rank_fusion
from app.knowledge.store import KnowledgeStore
from app.reranker.client import RerankerClient
from app.tracing import trace_span

logger = logging.getLogger(__name__)


class RAGPipeline:
    """Enterprise-grade RAG pipeline with query rewriting, dual recall, RRF fusion, and reranking."""

    def __init__(
        self,
        store: KnowledgeStore,
        embedder: EmbeddingClient,
        reranker: RerankerClient | None = None,
        query_rewriter: Any | None = None,
        recall_top_k: int = 10,
        rerank_top_n: int = 5,
        rrf_k: int = 60,
    ):
        self.store = store
        self.embedder = embedder
        self.reranker = reranker
        self.query_rewriter = query_rewriter
        self.recall_top_k = recall_top_k
        self.rerank_top_n = rerank_top_n
        self.rrf_k = rrf_k

    def search(self, query: str, category: str | None = None, top_k: int | None = None) -> list[RetrievedChunk]:
        """Full RAG pipeline: query rewrite → dual recall → RRF → rerank.

        Returns the top-k most relevant knowledge chunks.
        """
        effective_top_k = top_k or self.rerank_top_n

        with trace_span(
            "rag_pipeline",
            input_data={"query": query, "category": category, "top_k": effective_top_k},
        ) as (span, end_span):
            # Step 0: Query rewriting (optional)
            original_query = query
            if self.query_rewriter is not None:
                rewritten_query, detected_category = self.query_rewriter.rewrite(query)
                query = rewritten_query
                if category is None and detected_category:
                    category = detected_category
                logger.info(
                    "Query rewritten: '%s' → '%s' (category=%s)",
                    original_query, rewritten_query, category,
                )

            # Step 1: Dual recall
            bm25_results, vector_results = dual_recall(
                self.store, self.embedder, query,
                top_k=self.recall_top_k, category=category,
            )

            if not bm25_results and not vector_results:
                end_span(output={"result_count": 0, "stages": "dual_recall_empty"})
                return []

            # Step 2: RRF fusion
            fused = reciprocal_rank_fusion(
                bm25_results, vector_results,
                k=self.rrf_k, top_n=self.recall_top_k,
            )

            if not fused:
                end_span(output={"result_count": 0, "stages": "rrf_empty"})
                return []

            # Step 3: Reranking (if reranker is available)
            if self.reranker and len(fused) > 1:
                reranked = self._rerank(query, fused)
                final = reranked[:effective_top_k]
                stage = "dual_recall → rrf → rerank"
            else:
                final = fused[:effective_top_k]
                stage = "dual_recall → rrf"

            end_span(
                output={
                    "result_count": len(final),
                    "stages": stage,
                    "query_rewritten": original_query != query,
                    "original_query": original_query,
                    "search_query": query,
                    "category": category,
                    "results": [
                        {"id": r.chunk_id, "title": r.title, "score": round(r.score, 4), "path": r.retrieval_path}
                        for r in final
                    ],
                },
            )

            return final

    def _rerank(self, query: str, candidates: list[RetrievedChunk]) -> list[RetrievedChunk]:
        """Apply cross-encoder reranking to the fused candidate list."""
        with trace_span(
            "reranker",
            input_data={"query": query, "candidate_count": len(candidates)},
        ) as (span, end_span):
            documents = [f"{c.title}\n{c.content}" for c in candidates]

            try:
                rerank_results = self.reranker.rerank(query, documents)
            except Exception as exc:
                logger.warning("Reranker failed, using RRF order: %s", exc)
                end_span(output={"status": "fallback", "reason": str(exc)}, level="WARNING")
                return candidates

            reranked: list[RetrievedChunk] = []
            for r in rerank_results:
                idx = r.get("index", 0)
                if 0 <= idx < len(candidates):
                    chunk = candidates[idx]
                    chunk.score = r.get("relevance_score", chunk.score)
                    chunk.retrieval_path = "rerank"
                    reranked.append(chunk)

            end_span(
                output={
                    "status": "ok",
                    "reranked_count": len(reranked),
                    "top_scores": [round(r.score, 4) for r in reranked[:3]],
                },
            )

            return reranked
