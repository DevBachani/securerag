"""Phase 16 unit tests: pseudonymisation, graceful no-op, latency stats."""

from __future__ import annotations

from securerag import observability
from securerag.config import get_settings


def test_pseudonymize_is_stable_and_hidden():
    a = observability.pseudonymize("u_int")
    b = observability.pseudonymize("u_int")
    assert a == b  # stable
    assert a != "u_int"  # not the raw id
    assert len(a) == 16


def test_tracing_is_noop_without_keys(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "")
    get_settings.cache_clear()
    observability.get_callback_handler.cache_clear()

    assert observability.get_callback_handler() is None
    assert observability.trace_config("u_int", "t1", "trace-1") == {}
    get_settings.cache_clear()
    observability.get_callback_handler.cache_clear()


def test_latency_stats():
    assert observability.latency_stats([]) == {"count": 0, "median_ms": 0, "p95_ms": 0}
    stats = observability.latency_stats([100, 200, 300])
    assert stats["count"] == 3
    assert stats["median_ms"] == 200
    assert stats["p95_ms"] == 300
