"""Phase 3 unit tests: chunking preserves ACLs and is deterministic (no Qdrant)."""

from __future__ import annotations

from securerag.ingestion.chunker import chunk_documents, section_of
from securerag.ingestion.loader import load_documents


def test_every_chunk_carries_acl_metadata():
    nodes = chunk_documents(load_documents())
    assert nodes, "expected at least one chunk"
    for node in nodes:
        assert node.metadata.get("doc_id"), "chunk missing doc_id"
        assert node.metadata.get("allowed_groups"), "chunk missing allowed_groups"


def test_chunk_count_is_stable_across_runs():
    first = chunk_documents(load_documents())
    second = chunk_documents(load_documents())
    assert len(first) == len(second)


def test_pdf_pages_get_page_sections():
    # The salary-bands PDF should produce at least one chunk labelled "Page N".
    nodes = chunk_documents(load_documents())
    pdf_sections = [
        section_of(n) for n in nodes if n.metadata.get("doc_id") == "hr-salary-bands"
    ]
    assert pdf_sections, "no chunks for the salary-bands PDF"
    assert any(s.startswith("Page ") for s in pdf_sections)
