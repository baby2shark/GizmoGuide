"""LLM-based query rewriter for RAG retrieval optimization.

Rewrites conversational user queries into optimized search queries that
improve BM25 and vector recall quality. For example:
  "帮我找个降噪好一点的耳机，预算 500"
  → search_query: "降噪耳机 500元 推荐", category: "蓝牙耳机"
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.tracing import trace_generation

logger = logging.getLogger(__name__)

_REWRITE_SYSTEM_PROMPT = """你是一个搜索查询优化专家。把用户的口语化问题转化为精准的搜索查询。

输出要求（严格 JSON，不要多余字段）：
{
  "search_query": "提取核心商品关键词 + 关注维度，用空格分隔。去掉'帮我'、'推荐'、'哪个'等口语词。保留品牌名、型号、价格数字。",
  "category": "从以下品类中选一个最匹配的，不确定就填 null：蓝牙耳机、机械键盘、投影仪、显示器"
}

示例：
用户："帮我找个降噪好一点的蓝牙耳机，预算500左右"
输出：{"search_query": "降噪蓝牙耳机 500元 推荐", "category": "蓝牙耳机"}

用户："索尼和华为的耳机哪个好"
输出：{"search_query": "索尼 华为 耳机 对比", "category": "蓝牙耳机"}

用户："打游戏用什么轴体的键盘好"
输出：{"search_query": "游戏机械键盘 轴体推荐", "category": "机械键盘"}

用户："4K投影仪家用推荐"
输出：{"search_query": "4K投影仪 家用 推荐", "category": "投影仪"}
""".strip()


class QueryRewriter:
    """LLM-powered query rewriter that converts conversational queries
    into optimized search queries for better RAG retrieval."""

    def __init__(self, llm_client: Any):
        self.llm_client = llm_client

    def rewrite(self, query: str) -> tuple[str, str | None]:
        """Rewrite a conversational query into an optimized search query.

        Returns:
            (rewritten_query, category) — category may be None if not detectable.
            Falls back to the original query if rewriting fails.
        """
        with trace_generation(
            "query_rewriter",
            model=getattr(self.llm_client.settings, "deepseek_model", "unknown"),
            input_data={"query": query},
        ) as (gen, end_gen):
            try:
                from app.agent.llm_client import ChatMessage

                data = self.llm_client.chat_json(
                    [
                        ChatMessage(role="system", content=_REWRITE_SYSTEM_PROMPT),
                        ChatMessage(role="user", content=f'用户："{query}"'),
                    ],
                    temperature=0.0,
                )
                search_query = data.get("search_query", query)
                category = data.get("category")

                # Validate output
                if not search_query or not isinstance(search_query, str):
                    search_query = query
                if category is not None and not isinstance(category, str):
                    category = None

                end_gen(output={"search_query": search_query, "category": category})
                return search_query, category

            except Exception as exc:
                logger.warning("Query rewriting failed, using original query: %s", exc)
                end_gen(output={"fallback": True, "reason": str(exc)})
                return query, None
