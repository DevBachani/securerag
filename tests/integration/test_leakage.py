"""Phase 6 integration tests: permission-filtered retrieval blocks leaks.

Requires Qdrant populated (scripts/ingest.py). Principals are built directly, so
no app DB is needed. Retrieval-only -> no LLM calls.
"""

from __future__ import annotations

import pytest

from securerag.ingestion.pipeline import get_qdrant_client
from securerag.retrieval.permissions import Principal
from securerag.retrieval.retriever import retrieve


def _qdrant_up() -> bool:
    try:
        get_qdrant_client().get_collections()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _qdrant_up(), reason="Qdrant not reachable")

INTERN = Principal("u_int", ["all"])
CEO = Principal("u_ceo", ["leadership", "hr", "finance", "engineering", "all"])


def test_intern_retrieves_only_public_docs():
    results = retrieve("What are the salary bands for each level?", INTERN, top_k=12)
    assert results, "intern should still retrieve public chunks"
    assert all(r.path.startswith("public/") for r in results)
    assert all(r.doc_id != "hr-salary-bands" for r in results)


def test_ceo_can_retrieve_confidential():
    results = retrieve("What are the salary bands for each level?", CEO, top_k=12)
    assert any(r.doc_id == "hr-salary-bands" for r in results)


def test_same_question_differs_by_user():
    question = "How many redundant roles are in the restructuring plan?"
    intern_docs = {r.doc_id for r in retrieve(question, INTERN, top_k=12)}
    ceo_docs = {r.doc_id for r in retrieve(question, CEO, top_k=12)}
    assert "lead-restructuring" in ceo_docs
    assert "lead-restructuring" not in intern_docs
