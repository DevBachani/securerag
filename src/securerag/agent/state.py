"""The agent's typed state and the router's structured output.

The state is the single object that flows through the graph; each node returns a
partial update. The user's permission context (user_id, user_groups) lives here and
is set by the caller from the authenticated session -- the LLM can never change it,
which is what keeps permission enforcement outside the model's control.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


class RouteDecision(BaseModel):
    """Structured output of the router node."""

    route: Literal["knowledge", "action", "out_of_scope"] = Field(
        description="Which path handles this message."
    )


class ContextGrade(BaseModel):
    """Structured output of grade_context: which numbered contexts are relevant."""

    relevant_indices: list[int] = Field(
        default_factory=list,
        description="1-based indices of the context items relevant to the question.",
    )


class GroundingCheck(BaseModel):
    """Structured output of check_grounding: whether every claim is supported."""

    grounded: bool = Field(description="True if every claim in the answer is supported.")


class AgentState(TypedDict, total=False):
    """State threaded through the LangGraph agent (partial updates per node)."""

    messages: Annotated[list, add_messages]  # chat history (for memory/condense)
    question: str  # the raw latest user message
    standalone_question: str  # condensed, context-free question
    user_id: str  # permission context from the session, never from the LLM
    user_groups: list[str]
    route: str  # knowledge | action | out_of_scope
    retrieved: list[dict[str, Any]]  # retrieved chunks (as dicts, checkpoint-safe)
    search_query: str  # Phase 12: rewritten query used for retrieval
    rewrites: int  # Phase 12: query-rewrite retry count
    generations: int  # Phase 12: number of answer attempts (grounding retries)
    grounded: bool  # Phase 12: did the grounding check pass
    answer: str
    citations: list[dict[str, Any]]
    refused: bool
    pending_ticket: dict[str, Any] | None  # Phase 13: drafted, awaiting approval
    approval_decision: dict[str, Any]  # Phase 13: {approve, edited_title?, acting_user_id?}
    ticket_id: int | None  # Phase 13: created ticket id
    thread_id: str  # Phase 13: conversation id (ticket idempotency key)
    trace_id: str  # Phase 16
