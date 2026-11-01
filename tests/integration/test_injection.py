"""Phase 14 integration test: injection cannot leak forbidden data (retrieval-only).

The permission filter makes data leakage structurally impossible regardless of the
prompt wording, so attack_success_rate (forbidden doc retrieved) must be 0. Needs
Qdrant; no LLM calls.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from securerag.db.session import load_principal
from securerag.evaluation import leakage
from securerag.ingestion.pipeline import get_qdrant_client
from securerag.retrieval.retriever import retrieve

INJECTION = Path(__file__).resolve().parents[2] / "eval" / "injection_set.jsonl"


def _qdrant_up() -> bool:
    try:
        get_qdrant_client().get_collections()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _qdrant_up(), reason="Qdrant not reachable")


def test_no_injection_leaks_forbidden_data():
    lines = INJECTION.read_text(encoding="utf-8").splitlines()
    rows = [json.loads(line) for line in lines if line.strip()]
    assert rows, "injection set is empty"
    for row in rows:
        principal = load_principal(row["user_id"])
        retrieved_ids = [r.doc_id for r in retrieve(row["question"], principal)]
        assert leakage(retrieved_ids, [], row["forbidden_doc_ids"]) == 0.0, (
            f"attack {row['id']} leaked a forbidden doc: {retrieved_ids}"
        )
