"""Hybrid retrieval: run dense and sparse (BM25) search, fuse with RRF.

Dense (semantic) search is great at paraphrase but weak on rare exact tokens like
"ERR-4021"; BM25 keyword search is the opposite. Reciprocal Rank Fusion combines
the two ranked lists using only each document's RANK (not its raw score), which
sidesteps the fact that cosine similarities and BM25 scores aren't comparable.

The permission filter is passed to BOTH branches, so a forbidden chunk can never
enter either candidate list.
"""

from __future__ import annotations

from dataclasses import dataclass

from qdrant_client import QdrantClient, models

from ..ingestion.pipeline import DENSE_VECTOR, SPARSE_VECTOR

# Standard RRF constant; dampens the weight of top ranks so no single list dominates.
RRF_K = 60


@dataclass
class FusedHit:
    """A document after fusion: its id, payload and combined RRF score."""

    id: str
    payload: dict
    score: float


def reciprocal_rank_fusion(result_lists: list[list], rrf_k: int = RRF_K) -> list[FusedHit]:
    """Fuse ranked result lists by RRF: score = sum 1/(rrf_k + rank)."""
    scores: dict[str, float] = {}
    payloads: dict[str, dict] = {}
    for points in result_lists:
        for rank, point in enumerate(points):
            scores[point.id] = scores.get(point.id, 0.0) + 1.0 / (rrf_k + rank + 1)
            payloads[point.id] = point.payload or {}
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    return [FusedHit(id=pid, payload=payloads[pid], score=score) for pid, score in ranked]


def hybrid_search(
    client: QdrantClient,
    collection: str,
    dense_vector: list[float],
    sparse_vector: models.SparseVector,
    query_filter: models.Filter,
    top_k: int,
    candidate_k: int | None = None,
) -> list[FusedHit]:
    """Query dense + sparse branches (both permission-filtered) and RRF-fuse them."""
    # Pull a wider candidate pool from each branch than the final top_k.
    pool = candidate_k or max(top_k * 2, 20)

    dense_hits = client.query_points(
        collection_name=collection,
        query=dense_vector,
        using=DENSE_VECTOR,
        query_filter=query_filter,
        limit=pool,
        with_payload=True,
    ).points
    sparse_hits = client.query_points(
        collection_name=collection,
        query=sparse_vector,
        using=SPARSE_VECTOR,
        query_filter=query_filter,
        limit=pool,
        with_payload=True,
    ).points

    return reciprocal_rank_fusion([dense_hits, sparse_hits])[:top_k]
