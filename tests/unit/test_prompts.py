"""Phase 4 unit tests: context formatting and citation parsing (no LLM)."""

from __future__ import annotations

from dataclasses import dataclass

from securerag.agent.prompts import (
    build_answer_prompt,
    extract_citation_numbers,
    format_context,
)


@dataclass
class _Chunk:
    title: str
    section: str
    page: int | None
    text: str


def test_format_context_numbers_each_chunk():
    chunks = [
        _Chunk("Leave Policy", "Earned leave", None, "24 earned leaves per year"),
        _Chunk("Q2 Budget", "", 2, "Total budget is INR 36 crore"),
    ]
    context = format_context(chunks)

    assert "[1] (Leave Policy - Earned leave):" in context
    assert "[2] (Q2 Budget - Page 2):" in context
    assert "24 earned leaves" in context


def test_extract_citations_unique_and_ordered():
    assert extract_citation_numbers("foo [2] bar [1] baz [2] qux [3]") == [2, 1, 3]
    assert extract_citation_numbers("no citations here") == []


def test_extract_citations_handles_fullwidth_brackets():
    # gpt-oss and some models cite with CJK full-width brackets 【1】.
    assert extract_citation_numbers("The budget is 36 crore 【1】.") == [1]
    assert extract_citation_numbers("mix [1] and 【2】") == [1, 2]


def test_build_answer_prompt_includes_question_and_rules():
    prompt = build_answer_prompt(
        "How many earned leaves?",
        [_Chunk("Leave Policy", "Earned leave", None, "24 per year")],
    )
    assert "How many earned leaves?" in prompt
    assert "ONLY the numbered context" in prompt
    assert "[1] (Leave Policy - Earned leave):" in prompt
