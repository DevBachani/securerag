"""Incremental sync: only re-process what changed since the last ingest.

Change detection uses two hashes stored per document in ingest_state:
- content_hash (sha256 of the file bytes): a changed file -> delete its chunks and
  re-embed. Hashing content, not mtime, means a touched-but-identical file is skipped
  and an edited file is caught regardless of timestamps.
- meta_hash (sha256 of the permission/version fields): a changed manifest entry
  (e.g. an ACL change) with identical content -> update the chunk payload in place,
  no re-embedding. Keeping ACLs in sync matters for security, not just freshness.

Deleted documents (in state but not in the manifest) have their chunks removed.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient, models
from sqlmodel import Session, select

from ..config import get_settings
from ..db.models import IngestState
from ..db.session import get_session, init_db
from .chunker import chunk_documents
from .loader import _repo_root, load_documents, load_manifest, superseded_doc_ids
from .pipeline import build_points, ensure_collection, get_qdrant_client, upsert_points

# Manifest-derived payload fields that can change without the file changing.
_META_FIELDS = (
    "allowed_groups",
    "allowed_users",
    "sensitivity",
    "version",
    "effective_date",
    "title",
    "path",
    "department",
)


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _meta_fields(entry: dict[str, Any], is_current: bool) -> dict[str, Any]:
    """Return the payload fields derived from the manifest entry (incl. is_current)."""
    fields = {key: entry[key] for key in _META_FIELDS}
    fields["is_current"] = is_current
    return fields


def _meta_hash(fields: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(fields, sort_keys=True, default=str).encode()).hexdigest()


def _doc_filter(doc_id: str) -> models.Filter:
    return models.Filter(
        must=[models.FieldCondition(key="doc_id", match=models.MatchValue(value=doc_id))]
    )


def _delete_doc_chunks(client: QdrantClient, collection: str, doc_id: str) -> None:
    client.delete(
        collection_name=collection,
        points_selector=models.FilterSelector(filter=_doc_filter(doc_id)),
    )


def _set_doc_payload(client: QdrantClient, collection: str, doc_id: str, fields: dict) -> None:
    client.set_payload(collection_name=collection, payload=fields, points=_doc_filter(doc_id))


def _chunk_counts(nodes: list) -> dict[str, int]:
    counts: dict[str, int] = {}
    for node in nodes:
        doc_id = node.metadata["doc_id"]
        counts[doc_id] = counts.get(doc_id, 0) + 1
    return counts


def _write_state(
    session: Session,
    doc_ids: set[str],
    entries: dict[str, dict],
    superseded: set[str],
    corpus: Path,
    chunk_counts: dict[str, int],
) -> None:
    """Create/update ingest_state rows for the given doc_ids."""
    for doc_id in doc_ids:
        entry = entries[doc_id]
        fields = _meta_fields(entry, is_current=doc_id not in superseded)
        state = session.get(IngestState, doc_id) or IngestState(
            doc_id=doc_id, path=entry["path"], content_hash="", meta_hash="", chunk_count=0
        )
        state.path = entry["path"]
        state.content_hash = _file_hash(corpus / entry["path"])
        state.meta_hash = _meta_hash(fields)
        state.chunk_count = chunk_counts.get(doc_id, 0)
        state.last_ingested_at = datetime.now(UTC)
        session.add(state)


def sync(manifest_path: str | None = None) -> dict[str, int]:
    """Incrementally bring Qdrant in line with the manifest; return change counts."""
    settings = get_settings()
    init_db()
    client = get_qdrant_client()
    ensure_collection(client, settings.qdrant_collection, reset=False)
    collection = settings.qdrant_collection

    manifest = load_manifest(manifest_path)
    corpus = _repo_root() / manifest.get("corpus_root", "data/corpus")
    superseded = superseded_doc_ids(manifest)
    entries = {e["doc_id"]: e for e in manifest["documents"]}

    counts = {"added": 0, "updated": 0, "acl_updated": 0, "unchanged": 0, "deleted": 0}
    to_embed: set[str] = set()

    with get_session() as session:
        states = {s.doc_id: s for s in session.exec(select(IngestState)).all()}

        # Deletions: present in state but no longer in the manifest.
        for doc_id in set(states) - set(entries):
            _delete_doc_chunks(client, collection, doc_id)
            session.delete(states[doc_id])
            counts["deleted"] += 1

        for doc_id, entry in entries.items():
            content_hash = _file_hash(corpus / entry["path"])
            fields = _meta_fields(entry, is_current=doc_id not in superseded)
            meta_hash = _meta_hash(fields)
            state = states.get(doc_id)

            if state is None:
                to_embed.add(doc_id)
                counts["added"] += 1
            elif state.content_hash != content_hash:
                _delete_doc_chunks(client, collection, doc_id)
                to_embed.add(doc_id)
                counts["updated"] += 1
            elif state.meta_hash != meta_hash:
                _set_doc_payload(client, collection, doc_id, fields)
                counts["acl_updated"] += 1
            else:
                counts["unchanged"] += 1

        # Re-embed the new/changed docs in one batch.
        if to_embed:
            nodes = chunk_documents(load_documents(manifest_path, only_doc_ids=to_embed))
            upsert_points(client, collection, build_points(nodes))
            _write_state(session, to_embed, entries, superseded, corpus, _chunk_counts(nodes))

        # Refresh meta_hash for acl-only updates (no re-embed path above).
        for doc_id, entry in entries.items():
            if doc_id in to_embed:
                continue
            state = states.get(doc_id)
            if state is not None:
                fields = _meta_fields(entry, is_current=doc_id not in superseded)
                state.meta_hash = _meta_hash(fields)
                session.add(state)

        session.commit()

    return counts


def reset_state(manifest_path: str | None = None) -> None:
    """Rewrite ingest_state for every manifest doc (after a full --reset rebuild).

    Chunks the corpus (no embedding) just to count chunks per doc, then records
    fresh hashes so a subsequent sync sees everything as unchanged.
    """
    init_db()
    manifest = load_manifest(manifest_path)
    corpus = _repo_root() / manifest.get("corpus_root", "data/corpus")
    superseded = superseded_doc_ids(manifest)
    entries = {e["doc_id"]: e for e in manifest["documents"]}
    counts = _chunk_counts(chunk_documents(load_documents(manifest_path)))

    with get_session() as session:
        for state in session.exec(select(IngestState)).all():
            session.delete(state)
        session.commit()
        _write_state(session, set(entries), entries, superseded, corpus, counts)
        session.commit()
