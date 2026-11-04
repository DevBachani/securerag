"""Write one audit row per chat request (doc ids + status, never the raw answer)."""

from __future__ import annotations

import json

from ..db.models import AuditLog
from ..db.session import get_session


def write_audit(
    user_id: str,
    question: str,
    route: str,
    retrieved_doc_ids: list[str],
    cited_doc_ids: list[str],
    refused: bool,
    latency_ms: int,
    trace_id: str | None = None,
) -> None:
    """Record who asked what, which docs were involved, and the outcome."""
    with get_session() as session:
        session.add(
            AuditLog(
                user_id=user_id,
                question=question,
                route=route,
                retrieved_doc_ids=json.dumps(retrieved_doc_ids),
                cited_doc_ids=json.dumps(cited_doc_ids),
                refused=refused,
                latency_ms=latency_ms,
                trace_id=trace_id,
            )
        )
        session.commit()
