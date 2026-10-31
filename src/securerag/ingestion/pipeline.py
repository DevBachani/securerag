"""Embed chunks and upsert them into Qdrant with their full ACL payload.

The collection holds dense vectors only (hybrid/sparse arrives in Phase 7).
Point ids are deterministic UUID5s derived from (doc_id, chunk_index), so
re-running ingestion overwrites the same points instead of creating duplicates
-- the pipeline is idempotent for unchanged content.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

from llama_index.core.schema import BaseNode, MetadataMode
from qdrant_client import QdrantClient, models

from ..config import get_settings
from ..providers import get_embed_model, get_sparse_embed_model
from .chunker import chunk_documents, section_of
from .loader import load_documents

# bge-small-en-v1.5 output width.
EMBED_DIM = 384
# Named vectors in the collection: a dense semantic vector and a sparse BM25 vector.
DENSE_VECTOR = "dense"
SPARSE_VECTOR = "sparse"
# Fixed namespace so UUID5 chunk ids are stable across machines and runs.
_NAMESPACE = uuid.UUID("5f2b1c4a-6d3e-4a1b-9c7d-8e0f1a2b3c4d")
# Payload fields that get an index so filtering on them is fast (Phase 6).
_INDEXED_KEYWORDS = ("doc_id", "allowed_groups", "allowed_users")


def get_qdrant_client() -> QdrantClient:
    """Build a Qdrant client from settings (api_key optional for local)."""
    settings = get_settings()
    return QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)


def ensure_collection(client: QdrantClient, collection: str, reset: bool) -> None:
    """Create the collection and payload indexes if missing; optionally reset."""
    if reset and client.collection_exists(collection):
        client.delete_collection(collection)

    if not client.collection_exists(collection):
        client.create_collection(
            collection_name=collection,
            vectors_config={
                DENSE_VECTOR: models.VectorParams(size=EMBED_DIM, distance=models.Distance.COSINE),
            },
            # BM25 sparse vectors; IDF is applied by Qdrant at query time.
            sparse_vectors_config={
                SPARSE_VECTOR: models.SparseVectorParams(modifier=models.Modifier.IDF),
            },
        )
        for field in _INDEXED_KEYWORDS:
            client.create_payload_index(
                collection_name=collection,
                field_name=field,
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
        client.create_payload_index(
            collection_name=collection,
            field_name="is_current",
            field_schema=models.PayloadSchemaType.BOOL,
        )


def _point_id(doc_id: str, chunk_index: int) -> str:
    """Deterministic point id for a chunk, so re-ingesting overwrites it."""
    return str(uuid.uuid5(_NAMESPACE, f"{doc_id}:{chunk_index}"))


def _build_payload(node: BaseNode, text: str, point_id: str, chunk_index: int, now: str) -> dict:
    """Assemble the Qdrant payload for one chunk, per SPEC section 4."""
    meta = node.metadata
    return {
        "doc_id": meta["doc_id"],
        "chunk_id": point_id,
        "chunk_index": chunk_index,
        "title": meta["title"],
        "path": meta["path"],
        "department": meta["department"],
        "allowed_groups": meta["allowed_groups"],
        "allowed_users": meta["allowed_users"],
        "sensitivity": meta["sensitivity"],
        "version": meta["version"],
        "effective_date": meta["effective_date"],
        "is_current": meta.get("is_current", True),
        "content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "section": section_of(node),
        "page": meta.get("page"),
        "pii_redacted": meta.get("pii_redacted", False),  # Phase 10 may set True
        "ingested_at": now,
        "text": text,
    }


def _batched(items: list[Any], size: int) -> Iterator[list[Any]]:
    """Yield successive lists of at most `size` items."""
    for start in range(0, len(items), size):
        yield items[start : start + size]


def ingest(reset: bool = False, manifest_path: str | None = None) -> dict[str, int]:
    """Run the full pipeline and return counts of files, chunks and points."""
    settings = get_settings()
    client = get_qdrant_client()
    ensure_collection(client, settings.qdrant_collection, reset)

    embed_model = get_embed_model()
    sparse_model = get_sparse_embed_model()
    documents = load_documents(manifest_path)
    nodes = chunk_documents(documents)
    now = datetime.now(UTC).isoformat()

    per_doc_counter: dict[str, int] = {}
    points: list[models.PointStruct] = []
    for node in nodes:
        doc_id = node.metadata["doc_id"]
        chunk_index = per_doc_counter.get(doc_id, 0)
        per_doc_counter[doc_id] = chunk_index + 1

        text = node.get_content(metadata_mode=MetadataMode.NONE)
        dense = embed_model.get_text_embedding(text)
        sparse = next(sparse_model.embed([text]))
        point_id = _point_id(doc_id, chunk_index)
        points.append(
            models.PointStruct(
                id=point_id,
                vector={
                    DENSE_VECTOR: dense,
                    SPARSE_VECTOR: models.SparseVector(
                        indices=sparse.indices.tolist(), values=sparse.values.tolist()
                    ),
                },
                payload=_build_payload(node, text, point_id, chunk_index, now),
            )
        )

    for batch in _batched(points, 64):
        client.upsert(collection_name=settings.qdrant_collection, points=batch)

    point_count = client.count(collection_name=settings.qdrant_collection, exact=True).count
    # "files" counts source documents, not PDF pages, so count distinct doc_ids.
    file_count = len({d.metadata["doc_id"] for d in documents})
    return {"files": file_count, "chunks": len(nodes), "points": point_count}
