"""Phase 10 integration test: PII never reaches the vector store.

Requires Qdrant populated (scripts/ingest.py). Checks the disciplinary-log chunks
hold no raw PII and are flagged pii_redacted, while real budget numbers survive.
"""

from __future__ import annotations

import pytest
from qdrant_client import models

from securerag.config import get_settings
from securerag.ingestion.pipeline import get_qdrant_client


def _qdrant_up() -> bool:
    try:
        get_qdrant_client().get_collections()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _qdrant_up(), reason="Qdrant not reachable")


def _chunks_for(doc_id: str) -> list:
    client = get_qdrant_client()
    flt = models.Filter(
        must=[models.FieldCondition(key="doc_id", match=models.MatchValue(value=doc_id))]
    )
    points, _ = client.scroll(
        get_settings().qdrant_collection, scroll_filter=flt, limit=50, with_payload=True
    )
    return points


def test_no_pii_in_disciplinary_log_payloads():
    points = _chunks_for("hr-disciplinary-log")
    assert points, "disciplinary log not ingested"
    blob = "\n".join(p.payload["text"] for p in points)

    assert "@acme.example" not in blob  # emails redacted
    assert "ABCDE1234F" not in blob  # PAN redacted
    assert "1234 5678 9012" not in blob  # Aadhaar redacted
    assert "+91" not in blob  # phones redacted
    assert all(p.payload["pii_redacted"] for p in points)
    # labels present -> redaction actually ran
    assert "<PAN>" in blob or "<EMAIL>" in blob


def test_budget_numbers_survive_redaction():
    points = _chunks_for("fin-q2-budget")
    blob = "\n".join(p.payload["text"] for p in points)
    assert "36" in blob  # total Q2 budget figure intact
