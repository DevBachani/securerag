"""Phase 11 integration test: a two-turn conversation with a follow-up.

Uses the real LLM (Groq), so it is opt-in: set RUN_LLM_TESTS=1 to run it. This keeps
routine test runs from consuming the free-tier token budget. Also needs Qdrant.
"""

from __future__ import annotations

import os
import uuid

import pytest

from securerag.agent.graph import resume_ticket, run_agent
from securerag.ingestion.pipeline import get_qdrant_client
from securerag.retrieval.permissions import Principal


def _ready() -> bool:
    if os.environ.get("RUN_LLM_TESTS") != "1":
        return False
    try:
        get_qdrant_client().get_collections()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _ready(), reason="set RUN_LLM_TESTS=1 and run Qdrant")

CEO = Principal("u_ceo", ["leadership", "hr", "finance", "engineering", "all"])


def test_followup_is_condensed_and_answered():
    thread = f"test-{uuid.uuid4().hex[:8]}"
    first = run_agent("How many earned leaves do employees get per year?", CEO, thread)
    assert first["route"] == "knowledge"
    assert "24" in first["answer"]

    # Follow-up relies on condense turning "and casual?" into a standalone question.
    second = run_agent("and casual leaves?", CEO, thread)
    assert second["route"] == "knowledge"
    assert "7" in second["answer"]


def test_out_of_scope_is_declined():
    result = run_agent("hello, how is your day going?", CEO, f"test-{uuid.uuid4().hex[:8]}")
    assert result["route"] == "out_of_scope"


def test_ticket_approve_flow_creates_ticket():
    thread = f"tkt-{uuid.uuid4().hex[:8]}"
    first = run_agent("My laptop screen is broken, please raise a ticket", CEO, thread)
    assert first["route"] == "action"
    assert first["interrupted"] is True
    assert first["pending_ticket"] is not None

    final = resume_ticket(thread, approve=True, acting_user_id="u_ceo")
    assert final["ticket_id"] is not None


def test_ticket_reject_flow_creates_nothing():
    thread = f"tkt-{uuid.uuid4().hex[:8]}"
    first = run_agent("Please raise a ticket for a new monitor", CEO, thread)
    assert first["interrupted"] is True

    final = resume_ticket(thread, approve=False, acting_user_id="u_ceo")
    assert final["ticket_id"] is None
