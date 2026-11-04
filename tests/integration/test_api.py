"""Phase 15 API tests (httpx TestClient; the agent is mocked so no LLM/Qdrant).

Covers: login works, bad password 401, no token 401, intern -> /admin/audit 403,
admin -> 200, thread ownership is enforced, and one /chat request writes one audit row.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from securerag.config import get_settings
from securerag.db import session as db_session
from securerag.db.models import AuditLog, Group, User, UserGroup

_USERS = {
    "u_int": ("sneha.rao@acme.example", ["all"]),
    "u_admin": ("admin@acme.example", ["admin", "all"]),
    "u_ceo": ("vikram.shah@acme.example", ["leadership", "all"]),
    "u_eng": ("rahul.verma@acme.example", ["engineering", "all"]),
}
_GROUPS = ["all", "admin", "leadership", "engineering"]
_PASSWORD = "demo1234"


def _seed() -> None:
    db_session.init_db()
    with db_session.get_session() as s:
        name_to_id = {}
        for name in _GROUPS:
            g = Group(name=name)
            s.add(g)
            s.commit()
            s.refresh(g)
            name_to_id[name] = g.id
        pw = db_session.hash_password(_PASSWORD)
        for uid, (email, groups) in _USERS.items():
            s.add(User(id=uid, name=uid, email=email, role=uid, password_hash=pw))
            s.commit()
            for gname in groups:
                s.add(UserGroup(user_id=uid, group_id=name_to_id[gname]))
            s.commit()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'api.db'}")
    get_settings.cache_clear()
    db_session.get_engine.cache_clear()
    _seed()
    from securerag.api.main import create_app

    yield TestClient(create_app())
    get_settings.cache_clear()
    db_session.get_engine.cache_clear()


def _token(client: TestClient, email: str) -> str:
    resp = client.post("/auth/login", json={"email": email, "password": _PASSWORD})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_login_success_and_bad_password(client):
    assert client.post(
        "/auth/login", json={"email": "sneha.rao@acme.example", "password": _PASSWORD}
    ).status_code == 200
    assert client.post(
        "/auth/login", json={"email": "sneha.rao@acme.example", "password": "nope"}
    ).status_code == 401


def test_chat_requires_a_token(client):
    assert client.post("/chat", json={"message": "hi"}).status_code == 401


def test_intern_forbidden_from_admin_audit(client):
    token = _token(client, "sneha.rao@acme.example")
    assert client.get("/admin/audit", headers=_auth(token)).status_code == 403


def test_admin_can_read_audit(client):
    token = _token(client, "admin@acme.example")
    assert client.get("/admin/audit", headers=_auth(token)).status_code == 200


def test_thread_ownership_enforced(client, monkeypatch):
    # Pretend a saved thread is owned by u_ceo; u_eng must not read it.
    monkeypatch.setattr(
        "securerag.api.routes_chat._thread_state", lambda tid: {"user_id": "u_ceo", "messages": []}
    )
    eng = _token(client, "rahul.verma@acme.example")
    ceo = _token(client, "vikram.shah@acme.example")
    assert client.get("/chat/t1", headers=_auth(eng)).status_code == 403
    assert client.get("/chat/t1", headers=_auth(ceo)).status_code == 200


def test_one_chat_request_writes_one_audit_row(client, monkeypatch):
    fake = {
        "answer": "You get 24 earned leaves per year [1].",
        "citations": [{"n": 1, "doc_id": "pub-leave-policy", "title": "Leave Policy"}],
        "retrieved": [{"doc_id": "pub-leave-policy", "text": "24 leaves"}],
        "refused": False,
        "route": "knowledge",
        "pending_ticket": None,
        "interrupted": False,
        "ticket_id": None,
    }
    monkeypatch.setattr("securerag.api.routes_chat.run_agent", lambda *a, **k: fake)
    token = _token(client, "sneha.rao@acme.example")

    resp = client.post("/chat", json={"message": "how many leaves?"}, headers=_auth(token))
    assert resp.status_code == 200

    with db_session.get_session() as s:
        rows = s.exec(select(AuditLog)).all()
    assert len(rows) == 1
    assert rows[0].user_id == "u_int"
    assert rows[0].route == "knowledge"
