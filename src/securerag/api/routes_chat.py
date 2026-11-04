"""Chat routes: streaming answers, ticket approval, and per-thread history.

Answers stream over Server-Sent Events: the agent runs to completion (so a grounding
refusal can't be streamed as if it were an answer), then the final text is streamed as
`token` events followed by a `done` event carrying citations and any pending ticket.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from sse_starlette.sse import EventSourceResponse

from ..agent.graph import get_compiled_graph, resume_ticket, run_agent
from ..config import get_settings
from ..retrieval.permissions import Principal
from .audit import write_audit
from .auth import get_current_user
from .limiter import limiter
from .schemas import ApproveRequest, ChatRequest

router = APIRouter(tags=["chat"])


def _doc_id(item: Any) -> str:
    return item["doc_id"] if isinstance(item, dict) else item.doc_id


def _thread_state(thread_id: str) -> dict:
    """Return the saved state values for a thread (empty if none)."""
    snapshot = get_compiled_graph().get_state({"configurable": {"thread_id": thread_id}})
    return snapshot.values or {}


@router.post("/chat")
@limiter.limit(f"{get_settings().rate_limit_per_minute}/minute")
async def chat(
    request: Request, body: ChatRequest, user: Principal = Depends(get_current_user)
) -> EventSourceResponse:
    """Run one turn of the agent and stream the answer over SSE."""
    thread_id = body.thread_id or uuid.uuid4().hex
    start = time.perf_counter()
    result = await run_in_threadpool(run_agent, body.message, user, thread_id)
    latency_ms = int((time.perf_counter() - start) * 1000)

    retrieved_ids = [_doc_id(d) for d in result["retrieved"]]
    cited_ids = [c["doc_id"] for c in result["citations"]]
    write_audit(user.id, body.message, result["route"], retrieved_ids, cited_ids,
                result["refused"], latency_ms)

    async def event_stream():
        for word in result["answer"].split():
            yield {"event": "token", "data": word + " "}
        final = {
            "thread_id": thread_id,
            "route": result["route"],
            "refused": result["refused"],
            "citations": result["citations"],
            "pending_ticket": result["pending_ticket"],
            "interrupted": result["interrupted"],
            "ticket_id": result.get("ticket_id"),
        }
        yield {"event": "done", "data": json.dumps(final)}

    return EventSourceResponse(event_stream())


@router.post("/chat/{thread_id}/approve")
async def approve(
    thread_id: str, body: ApproveRequest, user: Principal = Depends(get_current_user)
) -> dict:
    """Resume a paused ticket approval (only the thread's owner may approve)."""
    owner = _thread_state(thread_id).get("user_id")
    if owner and owner != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your conversation")
    result = await run_in_threadpool(
        resume_ticket, thread_id, body.approve, body.edited_title, user.id
    )
    return {
        "answer": result["answer"],
        "ticket_id": result.get("ticket_id"),
        "refused": result["refused"],
    }


@router.get("/chat/{thread_id}")
def history(thread_id: str, user: Principal = Depends(get_current_user)) -> dict:
    """Return a thread's history; a user may only read their own threads."""
    values = _thread_state(thread_id)
    if not values:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such conversation")
    if values.get("user_id") != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your conversation")
    messages = [
        {"role": "user" if m.type == "human" else "assistant", "content": m.content}
        for m in values.get("messages", [])
    ]
    return {"thread_id": thread_id, "messages": messages}
