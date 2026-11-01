"""Agent tools: draft a support ticket (LLM) and create it (DB).

create_ticket is idempotent on thread_id: resuming the same approval twice returns
the existing ticket instead of inserting a second one. Tickets are always created as
the requesting user -- the agent cannot file a ticket on someone else's behalf.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlmodel import select

from ..db.models import Ticket
from ..db.session import get_session, init_db
from ..providers import get_langchain_llm

# Prompt for drafting a ticket from the user's request.
_DRAFT_PROMPT = """You are a service-desk assistant. Draft a support ticket for the user's \
request. Keep the title short and specific. Choose the most appropriate department \
(e.g. IT, HR, Facilities, Finance) and a priority.

Request: {question}"""


class TicketDraft(BaseModel):
    """Structured draft produced by the LLM before human approval."""

    title: str = Field(description="A short, specific ticket title.")
    description: str = Field(description="A clear description of the issue/request.")
    department: str = Field(description="Owning department, e.g. IT, HR, Facilities.")
    priority: Literal["low", "medium", "high"]


def draft_ticket(question: str, user_id: str) -> dict[str, Any]:
    """Draft a ticket (not yet created) from the user's request."""
    llm = get_langchain_llm().with_structured_output(TicketDraft, method="json_schema")
    draft = llm.invoke(_DRAFT_PROMPT.format(question=question))
    return {
        "title": draft.title,
        "description": draft.description,
        "department": draft.department,
        "priority": draft.priority,
        "created_by": user_id,
    }


def create_ticket(draft: dict[str, Any], user_id: str, thread_id: str) -> Ticket:
    """Create the ticket in the DB, idempotently per thread_id (created as user_id)."""
    init_db()
    with get_session() as session:
        existing = session.exec(select(Ticket).where(Ticket.thread_id == thread_id)).first()
        if existing is not None:
            return existing  # idempotent: one ticket per approval thread
        now = datetime.now(UTC)
        ticket = Ticket(
            created_by=user_id,
            title=draft["title"],
            description=draft["description"],
            department=draft["department"],
            priority=draft["priority"],
            status="created",
            thread_id=thread_id,
            created_at=now,
            approved_at=now,
        )
        session.add(ticket)
        session.commit()
        session.refresh(ticket)
        return ticket
