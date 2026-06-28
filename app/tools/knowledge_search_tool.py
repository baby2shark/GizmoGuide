"""Knowledge search tool — RAG retrieval for the agent."""
from __future__ import annotations

import logging
from typing import Any

from app.config.settings import Settings
from app.embedding.client import EmbeddingClient, get_embedding_client
from app.knowledge.retrieval.pipeline import RAGPipeline
from app.knowledge.store import KnowledgeStore
from app.reranker.client import RerankerClient, get_reranker_client
from app.tracing import trace_span

logger = logging.getLogger(__name__)


class KnowledgeSearchTool:
    """RAG-powered knowledge search tool for the purchase agent.

    Wraps the full RAG pipeline: dual recall → RRF → rerank.
    """

    name = "knowledge_search"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.enabled = bool(settings.dashscope_api_key and settings.rag_database_url)
        self._pipeline: RAGPipeline | None = None

    def _get_pipeline(self) -> RAGPipeline | None:
        if self._pipeline is not None:
            return self._pipeline
        if not self.enabled:
            return None

        embedder = get_embedding_client(self.settings.dashscope_api_key)
        reranker = get_reranker_client(self.settings.dashscope_api_key)
        store = KnowledgeStore(self.settings.rag_database_url)

        self._pipeline = RAGPipeline(
            store=store,
            embedder=embedder,
            reranker=reranker,
            recall_top_k=self.settings.rag_recall_top_k,
            rerank_top_n=self.settings.rag_rerank_top_n,
        )
        return self._pipeline

    def search(self, query: str, category: str | None = None, top_k: int = 5) -> dict[str, Any]:
        """Search the private knowledge base for domain expertise.

        Args:
            query: Natural language query about product selection, brands, or buying advice.
            category: Optional category filter (e.g., "蓝牙耳机", "机械键盘").
            top_k: Number of results to return.

        Returns:
            dict with status, result_count, and results (list of knowledge chunks).
        """
        with trace_span(
            "knowledge_search",
            input_data={"query": query, "category": category, "top_k": top_k},
        ) as (span, end_span):
            pipeline = self._get_pipeline()
            if pipeline is None:
                result = {
                    "status": "disabled",
                    "error": "Knowledge base not configured (DASHSCOPE_API_KEY or RAG_DATABASE_URL missing)",
                    "result_count": 0,
                    "results": [],
                }
                end_span(output=result, level="WARNING")
                return result

            try:
                chunks = pipeline.search(query, category=category, top_k=top_k)
                results = [chunk.to_dict() for chunk in chunks]
                result = {
                    "status": "ok",
                    "result_count": len(results),
                    "results": results,
                }
                end_span(
                    output={
                        "status": "ok",
                        "result_count": len(results),
                        "top_results": results[:3],
                    },
                )
                return result
            except Exception as exc:
                logger.error("Knowledge search failed: %s", exc)
                result = {
                    "status": "error",
                    "error": str(exc),
                    "result_count": 0,
                    "results": [],
                }
                end_span(output=result, level="ERROR")
                return result
