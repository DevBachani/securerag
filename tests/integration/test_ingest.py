"""Phase 3 integration tests: ingestion into Qdrant is idempotent and ACL-tagged.

These require a running Qdrant. The whole module is skipped if it is unreachable,
so the unit suite still runs on a machine without Docker. Each test ingests into
its own throwaway collection and deletes it afterwards.
"""

from __future__ import annotations

import uuid

import pytest

from securerag.config import get_settings
from securerag.ingestion.pipeline import get_qdrant_client, ingest


def _qdrant_up() -> bool:
    try:
        get_qdrant_client().get_collections()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _qdrant_up(), reason="Qdrant not reachable")


@pytest.fixture
def test_collection(monkeypatch):
    """Point settings at a unique collection and drop it after the test."""
    name = f"acme_test_{uuid.uuid4().hex[:8]}"
    monkeypatch.setenv("QDRANT_COLLECTION", name)
    get_settings.cache_clear()
    yield name
    client = get_qdrant_client()
    if client.collection_exists(name):
        client.delete_collection(name)
    get_settings.cache_clear()


def test_ingest_is_idempotent(test_collection):
    first = ingest(reset=True)
    assert first["points"] > 0
    # Every chunk maps to exactly one point.
    assert first["points"] == first["chunks"]

    # Re-running without reset must not change the point count.
    second = ingest(reset=False)
    assert second["points"] == first["points"]


def test_points_carry_acl_payload(test_collection):
    ingest(reset=True)
    client = get_qdrant_client()
    points, _ = client.scroll(test_collection, limit=5, with_payload=True)
    assert points, "no points found after ingest"
    for point in points:
        assert point.payload["allowed_groups"], "point missing allowed_groups"
        assert point.payload["doc_id"], "point missing doc_id"
        assert point.payload["text"], "point missing chunk text"
