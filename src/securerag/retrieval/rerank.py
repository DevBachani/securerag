"""Cross-encoder reranking: re-score wide retrieval and keep the best few.

Bi-encoder retrieval (dense/BM25) is fast but approximate -- it embeds the query
and documents separately. A cross-encoder reads the query and each candidate
together, so it judges relevance far more precisely, at the cost of one model pass
per candidate. The recall-then-precision pattern: retrieve wide (top_k), rerank,
keep top_n for the LLM.
"""

from __future__ import annotations

from typing import TypeVar

from ..providers import get_reranker

# Works on any object with a `.text` str and a writable `.score` (e.g. Retrieved).
T = TypeVar("T")


def rerank(query: str, items: list[T], top_n: int) -> list[T]:
    """Re-score `items` against `query` with the cross-encoder; keep the top_n."""
    if not items:
        return items
    scores = list(get_reranker().rerank(query, [item.text for item in items]))
    ranked = sorted(zip(items, scores, strict=True), key=lambda pair: pair[1], reverse=True)
    kept: list[T] = []
    for item, score in ranked[:top_n]:
        item.score = float(score)  # replace retrieval score with the rerank score
        kept.append(item)
    return kept
