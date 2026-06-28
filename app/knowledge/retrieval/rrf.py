"""Reciprocal Rank Fusion (RRF) for combining multiple ranked retrieval lists."""
from __future__ import annotations

from app.knowledge.models import RetrievedChunk


def reciprocal_rank_fusion(
    *result_lists: list[RetrievedChunk],
    k: int = 60,
    top_n: int = 10,
) -> list[RetrievedChunk]:
    """Merge multiple ranked lists using RRF.

    RRF formula: score(d) = sum(1 / (k + rank_i(d))) for each list i.
    This is rank-based (not score-based), so it works even when different
    retrievers produce incomparable score scales.

    Args:
        result_lists: Two or more ranked lists of RetrievedChunk.
        k: RRF constant (default 60, from Cormack et al. 2009).
        top_n: Maximum number of results to return.

    Returns:
        A single merged list sorted by RRF score descending.
    """
    scores: dict[str, float] = {}
    chunk_map: dict[str, RetrievedChunk] = {}

    for results in result_lists:
        for rank, chunk in enumerate(results, start=1):
            rrf_score = 1.0 / (k + rank)
            scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + rrf_score
            chunk_map[chunk.chunk_id] = chunk

    # Sort by RRF score descending
    sorted_ids = sorted(scores.keys(), key=lambda cid: scores[cid], reverse=True)

    fused: list[RetrievedChunk] = []
    for cid in sorted_ids[:top_n]:
        chunk = chunk_map[cid]
        # Update score and retrieval path
        chunk.score = scores[cid]
        chunk.retrieval_path = "rrf"
        fused.append(chunk)

    return fused
