"""Print latency and usage stats from the audit log.

Reads the local audit_log table (populated by every /chat request), so it works
without Langfuse. Token counts / cost require Langfuse instrumentation and are
reported as n/a here.

Usage:  uv run python scripts/latency_report.py [--limit N]
"""

from __future__ import annotations

import argparse
from collections import Counter

from sqlmodel import select

from securerag.db.models import AuditLog
from securerag.db.session import get_session
from securerag.observability import latency_stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Latency report from the audit log.")
    parser.add_argument("--limit", type=int, default=200, help="Most recent N rows.")
    args = parser.parse_args()

    with get_session() as session:
        rows = session.exec(select(AuditLog).order_by(AuditLog.id.desc()).limit(args.limit)).all()

    if not rows:
        print("No audit rows yet. Make some /chat requests first.")
        return

    stats = latency_stats([r.latency_ms for r in rows])
    refusals = sum(1 for r in rows if r.refused)
    by_route = Counter(r.route for r in rows)

    print(f"Requests analysed : {stats['count']}")
    print(f"Latency median    : {stats['median_ms']} ms")
    print(f"Latency p95       : {stats['p95_ms']} ms")
    print(f"Refusal rate      : {refusals / len(rows):.0%}")
    print("By route          : " + ", ".join(f"{k}={v}" for k, v in by_route.items()))
    print("Tokens / cost     : n/a locally (requires Langfuse token instrumentation)")


if __name__ == "__main__":
    main()
