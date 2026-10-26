"""Split Documents into chunks that are heading-aware and size-bounded.

Two passes: MarkdownNodeParser first splits on Markdown headings so a chunk
never straddles two sections, then SentenceSplitter breaks any still-too-long
section into overlapping windows of CHUNK_SIZE tokens. Metadata (doc_id, ACLs,
page, header_path) propagates from Document to every child node automatically.
"""

from __future__ import annotations

from llama_index.core.node_parser import MarkdownNodeParser, SentenceSplitter
from llama_index.core.schema import BaseNode, Document

from ..config import get_settings


def chunk_documents(documents: list[Document]) -> list[BaseNode]:
    """Chunk Documents heading-first, then by size, returning text nodes."""
    settings = get_settings()
    heading_parser = MarkdownNodeParser()
    size_splitter = SentenceSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )

    # Pass 1: split on headings. Pass 2: split long sections by size.
    heading_nodes = heading_parser.get_nodes_from_documents(documents)
    return size_splitter.get_nodes_from_documents(heading_nodes)


def section_of(node: BaseNode) -> str:
    """Build a human-readable section label for a chunk.

    PDFs get "Page N"; Markdown gets the header path plus the chunk's own
    leading heading, e.g. "Leave Policy > Earned leave".
    """
    meta = node.metadata
    if meta.get("page") is not None:
        return f"Page {meta['page']}"

    parts: list[str] = []
    header_path = meta.get("header_path")  # e.g. "/Leave Policy/"
    if header_path:
        parts.extend(p for p in header_path.strip("/").split("/") if p)

    stripped = node.get_content().lstrip()
    first_line = stripped.splitlines()[0] if stripped else ""
    if first_line.startswith("#"):
        heading = first_line.lstrip("#").strip()
        if heading and heading not in parts:
            parts.append(heading)

    return " > ".join(parts) if parts else "body"
