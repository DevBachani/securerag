"""Phase 1 tests: the manifest and the corpus on disk must agree.

These checks catch the mistakes that would silently break every later phase:
a document with no permissions, a manifest pointing at a missing file, a file
nobody declared, or an ACL group that does not exist.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "data" / "manifest.json"
CORPUS_DIR = REPO_ROOT / "data" / "corpus"


def load_manifest() -> dict:
    """Read and parse data/manifest.json."""
    with MANIFEST_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


MANIFEST = load_manifest()
DOCUMENTS = MANIFEST["documents"]
KNOWN_GROUPS = set(MANIFEST["known_groups"])


def corpus_files() -> set[str]:
    """Every .md/.pdf file under the corpus, as POSIX paths relative to it."""
    return {
        p.relative_to(CORPUS_DIR).as_posix()
        for p in CORPUS_DIR.rglob("*")
        if p.is_file() and p.suffix in {".md", ".pdf"}
    }


def test_doc_ids_are_unique() -> None:
    ids = [d["doc_id"] for d in DOCUMENTS]
    assert len(ids) == len(set(ids)), "duplicate doc_id in manifest"


@pytest.mark.parametrize("doc", DOCUMENTS, ids=lambda d: d["doc_id"])
def test_manifest_entry_points_to_existing_file(doc: dict) -> None:
    """Every manifest entry must point at a file that exists on disk."""
    target = CORPUS_DIR / doc["path"]
    assert target.is_file(), f"{doc['doc_id']}: file not found at {doc['path']}"


@pytest.mark.parametrize("doc", DOCUMENTS, ids=lambda d: d["doc_id"])
def test_every_doc_has_known_allowed_groups(doc: dict) -> None:
    """allowed_groups must be non-empty and use only known groups."""
    groups = doc["allowed_groups"]
    assert groups, f"{doc['doc_id']}: allowed_groups is empty"
    unknown = set(groups) - KNOWN_GROUPS
    assert not unknown, f"{doc['doc_id']}: unknown group(s) {unknown}"


def test_every_corpus_file_has_a_manifest_entry() -> None:
    """No file may sit in the corpus without a declared permission entry."""
    declared = {d["path"] for d in DOCUMENTS}
    on_disk = corpus_files()
    undeclared = on_disk - declared
    assert not undeclared, f"corpus files missing from manifest: {sorted(undeclared)}"


def test_sensitivity_values_are_valid() -> None:
    """sensitivity is a display label; it must be one of the four allowed values."""
    allowed = {"public", "internal", "confidential", "restricted"}
    bad = [(d["doc_id"], d["sensitivity"]) for d in DOCUMENTS if d["sensitivity"] not in allowed]
    assert not bad, f"invalid sensitivity values: {bad}"
