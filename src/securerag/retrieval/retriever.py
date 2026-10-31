"""Dense top-k retrieval from Qdrant.

This is the baseline retriever: embed the question, find the nearest chunks by
cosine similarity, and return them with their payload. There is deliberately no
permission filter here yet -- that is added in Phase 6, inside the query.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ..config import get_settings
from ..ingestion.pipeline import get_qdrant_client
from ..providers import get_embed_model
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


def retrieve(question: str, principal: Principal, top_k: int | None = None) -> list[Retrieved]:
    """Return the top-k chunks `principal` may read, nearest to `question`.

    The permission filter is applied inside the Qdrant query (pre-filtering); an
    independent allow-check afterwards is defense in depth and should never drop
    anything if the filter is correct.
    """
    settings = get_settings()
    limit = top_k if top_k is not None else settings.retrieval_top_k

    query_vector = get_embed_model().get_query_embedding(question)
    client = get_qdrant_client()
    response = client.query_points(
        collection_name=settings.qdrant_collection,
        query=query_vector,
        query_filter=build_filter(principal),
        limit=limit,
        with_payload=True,
    )

    results: list[Retrieved] = []
    for point in response.points:
        payload = point.payload or {}
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
                score=point.score,
            )
        )
    return results
