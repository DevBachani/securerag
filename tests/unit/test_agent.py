"""Phase 11 unit tests: the graph compiles with the expected shape (no LLM)."""

from __future__ import annotations

from securerag.agent.graph import build_graph
from securerag.agent.state import RouteDecision


def test_graph_has_expected_nodes():
    compiled = build_graph().compile()
    node_ids = set(compiled.get_graph().nodes)
    for name in ["condense", "route", "retrieve", "generate", "decline", "action"]:
        assert name in node_ids


def test_route_decision_accepts_valid_routes():
    assert RouteDecision(route="knowledge").route == "knowledge"
    assert RouteDecision(route="action").route == "action"
    assert RouteDecision(route="out_of_scope").route == "out_of_scope"
