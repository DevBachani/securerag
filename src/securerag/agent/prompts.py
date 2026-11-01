"""Prompts for SecureRAG. All model instructions live in this one module.

Each prompt has a short comment saying what it is for. The answer prompt is a
strict grounding prompt: it forbids outside knowledge, requires numbered
citations, and gives one exact refusal sentence so refusals are detectable.
"""

from __future__ import annotations

import re
from typing import Protocol

# The exact sentence the model must use when the context cannot answer. Kept as a
# constant so the pipeline can detect a refusal reliably.
REFUSAL = "I don't have enough information to answer that."


class _Chunk(Protocol):
    """The fields the answer prompt needs from a retrieved chunk (duck-typed)."""

    title: str
    section: str
    page: int | None
    text: str


# Answer prompt: strict retrieve-then-generate grounding. Numbered context in,
# cited answer out.
ANSWER_PROMPT_TEMPLATE = """You are SecureRAG, an assistant that answers questions \
using ONLY the numbered context below.

Rules:
- Use only facts found in the context. Do not use outside knowledge.
- After each claim, cite the context item it came from, like [1] or [2].
- If the context does not contain the answer, reply with exactly:
  "{refusal}"
- Be concise and specific. Quote exact numbers, dates and names from the context.

Context:
{context}

Question: {question}

Answer:"""


def _location(chunk: _Chunk) -> str:
    """Short 'where in the document' label for a chunk."""
    if chunk.section:
        return chunk.section
    if chunk.page is not None:
        return f"Page {chunk.page}"
    return ""


def format_context(chunks: list[_Chunk]) -> str:
    """Render chunks as a numbered list the model can cite by index."""
    lines: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        location = _location(chunk)
        header = f"[{index}] ({chunk.title}" + (f" - {location}" if location else "") + ")"
        lines.append(f"{header}: {chunk.text}")
    return "\n\n".join(lines)


def build_answer_prompt(question: str, chunks: list[_Chunk]) -> str:
    """Build the full grounding prompt for a question and its retrieved chunks."""
    return ANSWER_PROMPT_TEMPLATE.format(
        refusal=REFUSAL,
        context=format_context(chunks),
        question=question,
    )


# Accept ASCII [1] and full-width 【1】 brackets: some models (e.g. gpt-oss) emit
# the CJK brackets for citations.
_CITATION_RE = re.compile(r"[\[【](\d+)[\]】]")


def extract_citation_numbers(answer: str) -> list[int]:
    """Return the citation numbers used in an answer, in first-seen order."""
    seen: list[int] = []
    for match in _CITATION_RE.findall(answer):
        number = int(match)
        if number not in seen:
            seen.append(number)
    return seen


# Condense a follow-up into a standalone question using the prior conversation.
CONDENSE_PROMPT = """Given the conversation so far and a follow-up message, rewrite the \
follow-up as a standalone question that makes sense without the conversation. If it is \
already standalone, return it unchanged. Return ONLY the rewritten question.

Conversation:
{history}

Follow-up: {question}
Standalone question:"""

# Route a user message to one of three paths.
ROUTE_PROMPT = """Classify the user's message into exactly one route:
- "knowledge": a question that should be answered from company documents.
- "action": a request to perform an action, such as creating/raising a ticket.
- "out_of_scope": greetings, chit-chat, or anything unrelated to the above.

Message: {question}"""

# Shown when the router decides a message is out of scope.
DECLINE_MESSAGE = (
    "I can only help with questions about Acme's documents or with creating a ticket. "
    "Could you rephrase your request?"
)
