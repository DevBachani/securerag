"""Ticket routes: a user sees only their own tickets."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import select

from ..db.models import Ticket
from ..db.session import get_session
from ..retrieval.permissions import Principal
from .auth import get_current_user

router = APIRouter(tags=["tickets"])


@router.get("/tickets")
def my_tickets(user: Principal = Depends(get_current_user)) -> list[dict]:
    """List the tickets created by the current user."""
    with get_session() as session:
        rows = session.exec(select(Ticket).where(Ticket.created_by == user.id)).all()
        return [row.model_dump() for row in rows]
