"""Phase 9 unit tests: superseded-version detection and is_current metadata."""

from __future__ import annotations

from securerag.ingestion.loader import superseded_doc_ids
from securerag.ingestion.sync import _meta_fields, _meta_hash


def test_superseded_doc_ids():
    manifest = {
        "documents": [
            {"doc_id": "travel-v2", "supersedes": "travel-v1"},
            {"doc_id": "travel-v1", "supersedes": None},
            {"doc_id": "leave", "supersedes": None},
        ]
    }
    assert superseded_doc_ids(manifest) == {"travel-v1"}


def _entry(groups):
    return {
        "allowed_groups": groups,
        "allowed_users": [],
        "sensitivity": "public",
        "version": "1.0",
        "effective_date": "2026-04-01",
        "title": "Doc",
        "path": "public/doc.md",
        "department": "public",
    }


def test_meta_hash_detects_acl_change():
    base = _meta_hash(_meta_fields(_entry(["all"]), is_current=True))
    changed = _meta_hash(_meta_fields(_entry(["hr"]), is_current=True))
    same = _meta_hash(_meta_fields(_entry(["all"]), is_current=True))
    assert base == same
    assert base != changed
