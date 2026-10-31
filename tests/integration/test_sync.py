"""Phase 9 integration tests: incremental sync, versioning, ACL sync.

Requires Qdrant populated and ingest_state seeded (run `scripts/ingest.py --reset`).
The ACL test uses a temp manifest and reverts, so it leaves the collection as found.
"""

from __future__ import annotations

import json

import pytest
from qdrant_client import models

from securerag.config import get_settings
from securerag.ingestion.loader import load_manifest
from securerag.ingestion.pipeline import get_qdrant_client
from securerag.ingestion.sync import sync
from securerag.retrieval.permissions import Principal
from securerag.retrieval.retriever import retrieve


def _qdrant_up() -> bool:
    try:
        get_qdrant_client().get_collections()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _qdrant_up(), reason="Qdrant not reachable")

CEO = Principal("u_ceo", ["leadership", "hr", "finance", "engineering", "all"])


def _benefits_groups() -> list[str]:
    client = get_qdrant_client()
    flt = models.Filter(
        must=[models.FieldCondition(key="doc_id", match=models.MatchValue(value="pub-benefits"))]
    )
    points, _ = client.scroll(
        get_settings().qdrant_collection, scroll_filter=flt, limit=1, with_payload=True
    )
    return points[0].payload["allowed_groups"]


def test_sync_is_idempotent():
    counts = sync()
    assert counts["added"] == 0
    assert counts["updated"] == 0
    assert counts["deleted"] == 0


def test_superseded_version_is_never_retrieved():
    results = retrieve("What is the domestic travel per diem?", CEO, top_k=20)
    doc_ids = {r.doc_id for r in results}
    assert "pub-travel-policy-v1" not in doc_ids  # old version filtered by is_current
    assert "pub-travel-policy" in doc_ids  # current version is available


def test_acl_change_updates_payload_in_place(tmp_path):
    assert _benefits_groups() == ["all"]  # starting state

    manifest = load_manifest()
    for entry in manifest["documents"]:
        if entry["doc_id"] == "pub-benefits":
            entry["allowed_groups"] = ["hr"]
    temp_manifest = tmp_path / "manifest.json"
    temp_manifest.write_text(json.dumps(manifest), encoding="utf-8")

    try:
        counts = sync(manifest_path=str(temp_manifest))
        assert counts["acl_updated"] >= 1
        assert counts["updated"] == 0  # content unchanged -> no re-embed
        assert _benefits_groups() == ["hr"]
    finally:
        sync()  # revert to the real manifest
    assert _benefits_groups() == ["all"]
