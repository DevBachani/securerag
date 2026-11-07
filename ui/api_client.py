"""Thin HTTP client the Streamlit UI uses to talk to the FastAPI backend.

The UI never touches the database or Qdrant directly -- everything goes through the
API, so all permission and audit logic stays server-side.
"""

from __future__ import annotations

import json
from collections.abc import Iterator

import httpx

TIMEOUT = 120.0


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def login(base: str, email: str, password: str) -> str | None:
    """Return a JWT for the credentials, or None if login failed."""
    resp = httpx.post(f"{base}/auth/login", json={"email": email, "password": password}, timeout=30)
    if resp.status_code == 200:
        return resp.json()["access_token"]
    return None


def chat_stream(
    base: str, token: str, message: str, thread_id: str | None
) -> Iterator[tuple[str, str]]:
    """Yield (event, data) pairs from the SSE chat stream ('token' then 'done')."""
    payload = {"message": message, "thread_id": thread_id}
    with httpx.stream(
        "POST", f"{base}/chat", headers=_auth(token), json=payload, timeout=TIMEOUT
    ) as resp:
        resp.raise_for_status()
        event = "message"
        for line in resp.iter_lines():
            if line.startswith("event:"):
                event = line[len("event:") :].strip()
            elif line.startswith("data:"):
                yield event, line[len("data:") :].strip()


def approve(
    base: str, token: str, thread_id: str, approve_it: bool, edited_title: str | None
) -> dict:
    """Approve or reject a pending ticket on a thread."""
    resp = httpx.post(
        f"{base}/chat/{thread_id}/approve",
        headers=_auth(token),
        json={"approve": approve_it, "edited_title": edited_title},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def get_tickets(base: str, token: str) -> list[dict]:
    resp = httpx.get(f"{base}/tickets", headers=_auth(token), timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_audit(base: str, token: str, limit: int = 100) -> list[dict]:
    resp = httpx.get(f"{base}/admin/audit?limit={limit}", headers=_auth(token), timeout=30)
    resp.raise_for_status()
    return resp.json()


def reingest(base: str, token: str) -> dict:
    resp = httpx.post(f"{base}/admin/reingest", headers=_auth(token), timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def parse_done(data: str) -> dict:
    """Parse the JSON payload of the final 'done' SSE event."""
    return json.loads(data)
