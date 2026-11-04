"""Assemble and run the LangGraph agent.

Wiring: condense -> route -> {knowledge: retrieve -> generate, action: action_stub,
out_of_scope: decline}. A SQLite checkpointer persists each conversation under its
thread_id so chats survive restarts.
"""

from __future__ import annotations

import sqlite3
import uuid
from functools import lru_cache
from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph

from .. import observability
from ..config import get_settings
from ..retrieval.permissions import Principal
from . import nodes
from .state import AgentState


def _after_grade(state: AgentState) -> str:
    """Route after grading: answer if relevant context, else rewrite or refuse."""
    if state.get("retrieved"):
        return "generate"
    if state.get("rewrites", 0) < get_settings().max_rewrites:
        return "rewrite"
    return "refuse"


def _after_grounding(state: AgentState) -> str:
    """Route after grounding: finish if grounded, else regenerate once, then refuse."""
    if state.get("grounded", True):
        return "end"
    if state.get("generations", 0) < get_settings().max_generations:
        return "generate"
    return "refuse"


def _after_approval(state: AgentState) -> str:
    """Route after the human decision: create the ticket or cancel."""
    decision = state.get("approval_decision") or {}
    return "create" if decision.get("approve") else "cancelled"


def build_graph() -> StateGraph:
    """Build the (uncompiled) self-correcting agent graph."""
    graph = StateGraph(AgentState)
    graph.add_node("condense", nodes.condense)
    graph.add_node("route", nodes.route)
    graph.add_node("retrieve", nodes.retrieve_node)
    graph.add_node("grade_context", nodes.grade_context)
    graph.add_node("rewrite", nodes.rewrite_query)
    graph.add_node("generate", nodes.generate)
    graph.add_node("check_grounding", nodes.check_grounding)
    graph.add_node("refuse", nodes.refuse)
    graph.add_node("decline", nodes.decline)
    graph.add_node("draft_ticket", nodes.draft_ticket_node)
    graph.add_node("approval", nodes.approval_node)
    graph.add_node("create_ticket", nodes.create_ticket_node)
    graph.add_node("cancelled", nodes.cancelled_node)

    graph.add_edge(START, "condense")
    graph.add_edge("condense", "route")
    graph.add_conditional_edges(
        "route",
        lambda state: state["route"],
        {"knowledge": "retrieve", "action": "draft_ticket", "out_of_scope": "decline"},
    )
    graph.add_edge("retrieve", "grade_context")
    graph.add_conditional_edges(
        "grade_context",
        _after_grade,
        {"generate": "generate", "rewrite": "rewrite", "refuse": "refuse"},
    )
    graph.add_edge("rewrite", "retrieve")
    graph.add_edge("generate", "check_grounding")
    graph.add_conditional_edges(
        "check_grounding",
        _after_grounding,
        {"end": END, "generate": "generate", "refuse": "refuse"},
    )
    graph.add_edge("refuse", END)
    graph.add_edge("decline", END)
    # Action path: draft -> wait for human approval -> create or cancel.
    graph.add_edge("draft_ticket", "approval")
    graph.add_conditional_edges(
        "approval",
        _after_approval,
        {"create": "create_ticket", "cancelled": "cancelled"},
    )
    graph.add_edge("create_ticket", END)
    graph.add_edge("cancelled", END)
    return graph


@lru_cache
def get_compiled_graph():
    """Compile the graph once, with a persistent SQLite checkpointer."""
    from langgraph.checkpoint.sqlite import SqliteSaver

    conn = sqlite3.connect(get_settings().agent_checkpoint_db, check_same_thread=False)
    return build_graph().compile(checkpointer=SqliteSaver(conn))


def _result(state: dict[str, Any]) -> dict[str, Any]:
    """Normalise a graph result, flagging whether it paused for approval."""
    return {
        "answer": state.get("answer", ""),
        "citations": state.get("citations", []),
        "retrieved": state.get("retrieved", []),
        "refused": state.get("refused", False),
        "route": state.get("route", ""),
        "pending_ticket": state.get("pending_ticket"),
        "ticket_id": state.get("ticket_id"),
        "interrupted": bool(state.get("__interrupt__")),
    }


def run_agent(
    question: str, principal: Principal, thread_id: str, trace_id: str | None = None
) -> dict[str, Any]:
    """Run one turn of the agent; may pause (interrupted) awaiting ticket approval."""
    trace_id = trace_id or uuid.uuid4().hex
    config: dict[str, Any] = {"configurable": {"thread_id": thread_id}}
    config.update(observability.trace_config(principal.id, thread_id, trace_id))
    result = get_compiled_graph().invoke(
        {
            "messages": [HumanMessage(question)],
            "question": question,
            "user_id": principal.id,
            "user_groups": principal.groups,
            "thread_id": thread_id,
            "trace_id": trace_id,
        },
        config=config,
    )
    out = _result(result)
    out["trace_id"] = trace_id
    return out


def resume_ticket(
    thread_id: str,
    approve: bool,
    edited_title: str | None = None,
    acting_user_id: str | None = None,
) -> dict[str, Any]:
    """Resume a paused approval with the human's decision (approve/reject)."""
    from langgraph.types import Command

    decision: dict[str, Any] = {"approve": approve}
    if edited_title:
        decision["edited_title"] = edited_title
    if acting_user_id:
        decision["acting_user_id"] = acting_user_id
    result = get_compiled_graph().invoke(
        Command(resume=decision), config={"configurable": {"thread_id": thread_id}}
    )
    return _result(result)
