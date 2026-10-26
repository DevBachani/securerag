"""Load corpus files into LlamaIndex Documents with their ACL metadata.

Markdown files load as a single Document. PDFs load one Document per page via
pymupdf4llm, which renders tables as Markdown tables so the numbers survive into
the chunks. Every Document carries the permission metadata from manifest.json,
which travels with it all the way into the Qdrant payload.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pymupdf4llm
from llama_index.core import Document


def _repo_root() -> Path:
    """Return the repository root (…/securerag)."""
    # src/securerag/ingestion/loader.py -> parents[3] is the repo root.
    return Path(__file__).resolve().parents[3]


def load_manifest(manifest_path: str | Path | None = None) -> dict[str, Any]:
    """Read and parse data/manifest.json (or a given path)."""
    path = Path(manifest_path) if manifest_path else _repo_root() / "data" / "manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _base_metadata(entry: dict[str, Any]) -> dict[str, Any]:
    """Copy the permission/provenance fields that every chunk must carry."""
    return {
        "doc_id": entry["doc_id"],
        "title": entry["title"],
        "path": entry["path"],
        "department": entry["department"],
        "allowed_groups": entry["allowed_groups"],
        "allowed_users": entry["allowed_users"],
        "sensitivity": entry["sensitivity"],
        "version": entry["version"],
        "effective_date": entry["effective_date"],
        "owner": entry["owner"],
        "supersedes": entry.get("supersedes"),
        # Phase 9 flips this to False for superseded document versions.
        "is_current": True,
    }


def _load_markdown(fpath: Path, meta: dict[str, Any]) -> Document:
    """Load one Markdown file as a single Document."""
    text = fpath.read_text(encoding="utf-8")
    md = dict(meta, source_type="markdown")
    return Document(text=text, metadata=md)


def _load_pdf(fpath: Path, meta: dict[str, Any]) -> list[Document]:
    """Load a PDF as one Document per page, tables rendered as Markdown."""
    pages = pymupdf4llm.to_markdown(str(fpath), page_chunks=True, show_progress=False)
    documents: list[Document] = []
    for page in pages:
        md = dict(meta, source_type="pdf", page=page["metadata"].get("page"))
        documents.append(Document(text=page["text"], metadata=md))
    return documents


def load_documents(manifest_path: str | Path | None = None) -> list[Document]:
    """Load every file listed in the manifest into Documents with ACL metadata."""
    manifest = load_manifest(manifest_path)
    corpus = _repo_root() / manifest.get("corpus_root", "data/corpus")

    documents: list[Document] = []
    for entry in manifest["documents"]:
        fpath = corpus / entry["path"]
        meta = _base_metadata(entry)
        if fpath.suffix.lower() == ".pdf":
            documents.extend(_load_pdf(fpath, meta))
        else:
            documents.append(_load_markdown(fpath, meta))
    return documents
