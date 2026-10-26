"""Baseline retrieve-then-generate pipeline with citations.

`answer()` ties the pieces together: dense retrieval, the grounding prompt, one
LLM call, and mapping the [n] citations in the answer back to their source
chunks. This is the Phase 4 baseline; the LangGraph agent replaces it in Phase 11
and the permission filter is added in Phase 6.
"""

from __future__ import annotations

from typing import Any

from .agent.prompts import REFUSAL, build_answer_prompt, extract_citation_numbers
from .config import get_settings
from .providers import complete_with_retry, get_llm
from .retrieval.retriever import Retrieved, retrieve

# Substring used to detect the model's refusal, robust to minor wording drift.
_REFUSAL_MARKER = "don't have enough information"


def _citations_from_answer(text: str, retrieved: list[Retrieved]) -> list[dict[str, Any]]:
    """Map each [n] in the answer to the source chunk it points at."""
    citations: list[dict[str, Any]] = []
    for number in extract_citation_numbers(text):
        if 1 <= number <= len(retrieved):
            chunk = retrieved[number - 1]
            citations.append(
                {
                    "n": number,
                    "doc_id": chunk.doc_id,
                    "title": chunk.title,
                    "section": chunk.section,
                    "page": chunk.page,
                }
            )
    return citations


def answer(question: str, top_k: int | None = None) -> dict[str, Any]:
    """Answer a question from the corpus, returning the answer and its citations."""
    retrieved = retrieve(question, top_k=top_k)
    if not retrieved:
        return {"answer": REFUSAL, "citations": [], "retrieved": [], "refused": True}

    # Only the top few chunks go to the generator (keeps the prompt compact); the
    # full retrieved list is still returned for eval/metrics. Citation numbers map
    # to this sent list.
    context_chunks = retrieved[: get_settings().answer_context_chunks]
    prompt = build_answer_prompt(question, context_chunks)
    response = complete_with_retry(get_llm(), prompt)
    text = str(response).strip()

    refused = _REFUSAL_MARKER in text.lower()
    citations = _citations_from_answer(text, context_chunks)
    return {
        "answer": text,
        "citations": citations,
        "retrieved": retrieved,
        "refused": refused,
    }
