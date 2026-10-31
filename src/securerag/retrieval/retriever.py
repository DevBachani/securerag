"""Permission-filtered retrieval: dense, or hybrid (dense + BM25) with RRF.

Which path runs is controlled by HYBRID_ENABLED. Both paths apply the user's
permission filter inside the Qdrant query (pre-filtering) and then re-check every
returned chunk with is_allowed() as defense in depth.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from qdrant_client import models

from ..config import get_settings
from ..ingestion.pipeline import DENSE_VECTOR, get_qdrant_client
from ..providers import get_embed_model, get_sparse_embed_model
from .hybrid import hybrid_search
from .permissions import Principal, build_filter, is_allowed

logger = logging.getLogger(__name__)


@dataclass
class Retrieved:
    """One retrieved chunk: its text plus the provenance a citation needs."""

    doc_id: str
    title: str
    section: str
    page: int | None
    path: str
    sensitivity: str
    text: str
    score: float


def _sparse_query_vector(question: str) -> models.SparseVector:
    """Embed the question as a BM25 sparse query vector."""
    sparse = next(get_sparse_embed_model().query_embed(question))
    return models.SparseVector(indices=sparse.indices.tolist(), values=sparse.values.tolist())


def retrieve(question: str, principal: Principal, top_k: int | None = None) -> list[Retrieved]:
    """Return the top-k chunks `principal` may read, nearest to `question`.

    Uses hybrid (dense + BM25 fused by RRF) when HYBRID_ENABLED, else dense only.
    The permission filter is applied inside the query; is_allowed() is a second,
    independent check (defense in depth) that should never drop anything.
    """
    settings = get_settings()
    limit = top_k if top_k is not None else settings.retrieval_top_k
    query_filter = build_filter(principal)
    client = get_qdrant_client()
    dense_vector = get_embed_model().get_query_embedding(question)

    # Each path yields (payload, score) pairs.
    if settings.hybrid_enabled:
        hits = hybrid_search(
            client,
            settings.qdrant_collection,
            dense_vector,
            _sparse_query_vector(question),
            query_filter,
            limit,
        )
        pairs = [(hit.payload, hit.score) for hit in hits]
    else:
        response = client.query_points(
            collection_name=settings.qdrant_collection,
            query=dense_vector,
            using=DENSE_VECTOR,
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
        )
        pairs = [(point.payload or {}, point.score) for point in response.points]

    results: list[Retrieved] = []
    for payload, score in pairs:
        if not is_allowed(payload, principal):
            # Should never happen: the query filter already excluded this. Log and drop.
            logger.error(
                "permission filter leak detected: doc_id=%s user=%s",
                payload.get("doc_id"),
                principal.id,
            )
            continue
        results.append(
            Retrieved(
                doc_id=payload["doc_id"],
                title=payload["title"],
                section=payload.get("section", ""),
                page=payload.get("page"),
                path=payload["path"],
                sensitivity=payload.get("sensitivity", ""),
                text=payload["text"],
                score=score,
            )
        )
    return results
