"""Phase 11 unit tests: the graph compiles with the expected shape (no LLM)."""

from __future__ import annotations

from securerag.agent.graph import _after_grade, _after_grounding, build_graph
from securerag.agent.state import RouteDecision


def test_graph_has_expected_nodes():
    compiled = build_graph().compile()
    node_ids = set(compiled.get_graph().nodes)
    for name in [
        "condense", "route", "retrieve", "grade_context", "rewrite",
        "generate", "check_grounding", "refuse", "decline",
        "draft_ticket", "approval", "create_ticket", "cancelled",
    ]:
        assert name in node_ids


def test_route_decision_accepts_valid_routes():
    assert RouteDecision(route="knowledge").route == "knowledge"
    assert RouteDecision(route="action").route == "action"
    assert RouteDecision(route="out_of_scope").route == "out_of_scope"


def test_after_grade_routes_generate_rewrite_refuse():
    assert _after_grade({"retrieved": [{"doc_id": "x"}]}) == "generate"
    assert _after_grade({"retrieved": [], "rewrites": 0}) == "rewrite"
    assert _after_grade({"retrieved": [], "rewrites": 2}) == "refuse"


def test_after_grounding_routes_end_regenerate_refuse():
    assert _after_grounding({"grounded": True}) == "end"
    assert _after_grounding({"grounded": False, "generations": 1}) == "generate"
    assert _after_grounding({"grounded": False, "generations": 2}) == "refuse"
