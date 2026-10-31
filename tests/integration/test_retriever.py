"""Phase 4 integration test: dense retrieval surfaces the right document.

Requires Qdrant populated with the main collection (run scripts/ingest.py).
Skipped if Qdrant is unreachable.
"""

from __future__ import annotations

import pytest

from securerag.ingestion.pipeline import get_qdrant_client
from securerag.retrieval.permissions import Principal
from securerag.retrieval.retriever import retrieve

# CEO can read everything, so retrieval-quality tests aren't skewed by the filter.
CEO = Principal("u_ceo", ["leadership", "hr", "finance", "engineering", "all"])


def _qdrant_up() -> bool:
    try:
        get_qdrant_client().get_collections()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _qdrant_up(), reason="Qdrant not reachable")


def test_retrieves_relevant_document_in_top_k():
    results = retrieve("How many earned leaves do employees get each year?", CEO, top_k=12)
    assert results, "retrieval returned nothing (is the corpus ingested?)"
    doc_ids = {r.doc_id for r in results}
    assert "pub-leave-policy" in doc_ids


def test_scores_are_descending():
    results = retrieve("deployment windows and rollback", CEO, top_k=8)
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)
