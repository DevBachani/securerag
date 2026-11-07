"""Phase 13 unit tests: ticket creation rules (DB only, no LLM).

Covers: approve creates exactly one, reject creates none, double-approve creates
one (idempotent), and a non-owner cannot approve someone else's ticket.
"""

from __future__ import annotations

import pytest
from sqlmodel import select

from securerag.agent import nodes
from securerag.agent.tools import create_ticket
from securerag.config import get_settings
from securerag.db import session as db_session
from securerag.db.models import Ticket

DRAFT = {
    "title": "Laptop screen broken",
    "description": "Cracked screen",
    "department": "IT",
    "priority": "high",
}


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'tickets.db'}")
    get_settings.cache_clear()
    db_session.get_engine.cache_clear()
    db_session.init_db()
    yield
    get_settings.cache_clear()
    db_session.get_engine.cache_clear()


def _ticket_count() -> int:
    with db_session.get_session() as session:
        return len(session.exec(select(Ticket)).all())


def test_create_ticket_is_idempotent_per_thread(temp_db):
    t1 = create_ticket(DRAFT, "u_eng", "thread-1")
    t2 = create_ticket(DRAFT, "u_eng", "thread-1")
    assert t1.id == t2.id
    assert _ticket_count() == 1


def test_owner_approval_creates_one_ticket(temp_db):
    state = {
        "pending_ticket": DRAFT,
        "user_id": "u_eng",
        "thread_id": "thread-2",
        "approval_decision": {"approve": True, "acting_user_id": "u_eng"},
    }
    out = nodes.create_ticket_node(state)
    assert out["ticket_id"] is not None
    assert _ticket_count() == 1


def test_double_approval_creates_one_ticket(temp_db):
    state = {
        "pending_ticket": DRAFT,
        "user_id": "u_eng",
        "thread_id": "thread-3",
        "approval_decision": {"approve": True, "acting_user_id": "u_eng"},
    }
    nodes.create_ticket_node(state)
    nodes.create_ticket_node(state)  # resume twice
    assert _ticket_count() == 1


def test_non_owner_cannot_approve(temp_db):
    state = {
        "pending_ticket": DRAFT,
        "user_id": "u_eng",
        "thread_id": "thread-4",
        "approval_decision": {"approve": True, "acting_user_id": "u_int"},
    }
    out = nodes.create_ticket_node(state)
    assert "ticket_id" not in out
    assert _ticket_count() == 0


def test_rejection_creates_nothing(temp_db):
    out = nodes.cancelled_node({})
    assert "won't create" in out["answer"].lower()
    assert _ticket_count() == 0
