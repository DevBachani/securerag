"""Langfuse tracing, wired to degrade gracefully.

If Langfuse keys are set it attaches a LangChain callback handler to agent runs; if
not (or if Langfuse can't be reached), tracing is a no-op and the rest of the system
is unaffected. User ids are pseudonymised (hashed) before they reach Langfuse, and
`trace_content=False` redacts inputs/outputs.

Trace linkage: we generate our own `trace_id` (uuid), store it in the audit_log row,
and attach it to the Langfuse trace metadata so audit and trace can be cross-referenced.
"""

from __future__ import annotations

import hashlib
import logging
import math
import statistics
from functools import lru_cache
from typing import Any

from .config import get_settings

logger = logging.getLogger(__name__)


def pseudonymize(user_id: str) -> str:
    """Return a short stable hash of a user id (never send the raw id to telemetry)."""
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:16]


def _mask(**_: Any) -> str:
    """Redact value sent to Langfuse when trace_content is off."""
    return "[REDACTED]"


@lru_cache
def get_callback_handler():
    """Return a Langfuse LangChain CallbackHandler, or None if disabled/unavailable."""
    settings = get_settings()
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        return None
    try:
        from langfuse import Langfuse
        from langfuse.langchain import CallbackHandler

        Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
            mask=None if settings.trace_content else _mask,
        )
        return CallbackHandler()
    except Exception as exc:  # noqa: BLE001 - tracing must never break the request
        logger.warning("Langfuse tracing disabled: %s", exc)
        return None


def trace_config(
    user_id: str,
    thread_id: str,
    trace_id: str,
    route: str | None = None,
    config_name: str | None = None,
) -> dict[str, Any]:
    """Build the LangGraph `config` extras for tracing (empty dict if disabled)."""
    handler = get_callback_handler()
    if handler is None:
        return {}
    metadata: dict[str, Any] = {
        "langfuse_user_id": pseudonymize(user_id),
        "langfuse_session_id": thread_id,
        "trace_id": trace_id,
    }
    tags = [t for t in (route, config_name) if t]
    if tags:
        metadata["langfuse_tags"] = tags
    return {"callbacks": [handler], "metadata": metadata}


def latency_stats(latencies_ms: list[int]) -> dict[str, float | int]:
    """Compute count, median and p95 from a list of latencies (ms)."""
    if not latencies_ms:
        return {"count": 0, "median_ms": 0, "p95_ms": 0}
    ordered = sorted(latencies_ms)
    p95_index = max(0, math.ceil(0.95 * len(ordered)) - 1)
    return {
        "count": len(ordered),
        "median_ms": int(statistics.median(ordered)),
        "p95_ms": int(ordered[p95_index]),
    }
