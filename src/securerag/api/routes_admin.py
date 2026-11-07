"""Admin routes: read the audit log and trigger re-ingestion (admin group only).

The admin can manage the system but, by design, is not in any document's ACL -- so
admin endpoints never expose confidential document content, only metadata.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import select

from ..db.models import AuditLog
from ..db.session import get_session
from ..retrieval.permissions import Principal
from .auth import require_admin

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/audit")
def audit(limit: int = 100, _: Principal = Depends(require_admin)) -> list[dict]:
    """Return the most recent audit rows."""
    with get_session() as session:
        rows = session.exec(select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)).all()
        return [row.model_dump() for row in rows]


@router.post("/reingest")
def reingest(_: Principal = Depends(require_admin)) -> dict:
    """Trigger an incremental corpus sync and return the change counts."""
    from ..ingestion.sync import sync

    return sync()
