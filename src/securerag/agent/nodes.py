"""The agent's nodes. Each takes the state and returns a partial update.

condense -> route -> (knowledge) retrieve -> generate
                  -> (action) action_stub          [real tool arrives in Phase 13]
                  -> (out_of_scope) decline
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage

from ..config import get_settings
from ..providers import get_langchain_llm
from ..retrieval.permissions import Principal
from ..retrieval.retriever import retrieve
from .prompts import (
    CONDENSE_PROMPT,
    DECLINE_MESSAGE,
    REFUSAL,
    ROUTE_PROMPT,
    build_answer_prompt,
    extract_citation_numbers,
)
from .state import AgentState, RouteDecision

# Placeholder answer for action requests until the ticket tool lands in Phase 13.
ACTION_COMING_SOON = "Creating tickets isn't available yet - it's coming soon."


def _history_text(messages: list) -> str:
    """Render all but the latest message as 'Role: text' lines."""
    lines = []
    for message in messages[:-1]:
        role = "User" if isinstance(message, HumanMessage) else "Assistant"
        lines.append(f"{role}: {message.content}")
    return "\n".join(lines)


def condense(state: AgentState) -> dict[str, Any]:
    """Rewrite a follow-up into a standalone question using the chat history."""
    question = state["question"]
    history = _history_text(state.get("messages", []))
    if not history.strip():
        return {"standalone_question": question}
    response = get_langchain_llm().invoke(
        CONDENSE_PROMPT.format(history=history, question=question)
    )
    return {"standalone_question": response.content.strip()}


def route(state: AgentState) -> dict[str, Any]:
    """Classify the question into knowledge / action / out_of_scope."""
    llm = get_langchain_llm().with_structured_output(RouteDecision)
    decision = llm.invoke(ROUTE_PROMPT.format(question=state["standalone_question"]))
    return {"route": decision.route}


def retrieve_node(state: AgentState) -> dict[str, Any]:
    """Retrieve permission-filtered chunks for the standalone question."""
    principal = Principal(id=state["user_id"], groups=state["user_groups"])
    hits = retrieve(state["standalone_question"], principal)
    retrieved = [
        {
            "doc_id": h.doc_id,
            "title": h.title,
            "section": h.section,
            "page": h.page,
            "path": h.path,
            "sensitivity": h.sensitivity,
            "text": h.text,
            "score": h.score,
        }
        for h in hits
    ]
    return {"retrieved": retrieved}


def generate(state: AgentState) -> dict[str, Any]:
    """Write a cited answer from the retrieved chunks, or refuse if none."""
    retrieved = state.get("retrieved", [])
    if not retrieved:
        return {
            "answer": REFUSAL,
            "citations": [],
            "refused": True,
            "messages": [AIMessage(REFUSAL)],
        }

    limit = get_settings().answer_context_chunks
    chunks = [SimpleNamespace(**d) for d in retrieved[:limit]]
    response = get_langchain_llm().invoke(build_answer_prompt(state["standalone_question"], chunks))
    text = response.content.strip()

    citations = []
    for number in extract_citation_numbers(text):
        if 1 <= number <= len(chunks):
            chunk = chunks[number - 1]
            citations.append(
                {
                    "n": number,
                    "doc_id": chunk.doc_id,
                    "title": chunk.title,
                    "section": chunk.section,
                    "page": chunk.page,
                }
            )
    refused = "don't have enough information" in text.lower()
    return {
        "answer": text,
        "citations": citations,
        "refused": refused,
        "messages": [AIMessage(text)],
    }


def decline(state: AgentState) -> dict[str, Any]:
    """Politely decline an out-of-scope message."""
    return {"answer": DECLINE_MESSAGE, "refused": False, "messages": [AIMessage(DECLINE_MESSAGE)]}


def action_stub(state: AgentState) -> dict[str, Any]:
    """Stand in for the ticket action until the real tool arrives in Phase 13."""
    return {
        "answer": ACTION_COMING_SOON,
        "pending_ticket": None,
        "messages": [AIMessage(ACTION_COMING_SOON)],
    }
