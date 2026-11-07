"""Compare the latest CI eval results against eval/thresholds.json.

Reads the leakage / injection / retrieval result files produced by run_eval, prints a
markdown table (also written to eval/results/gate_comment.md for the PR comment), and
exits non-zero if any hard gate is breached. Quota-free: it only reads JSON.

Usage:  uv run python scripts/check_eval_gate.py
"""

from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

from securerag.evaluation import gate_failures

sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "eval" / "results"


def _latest(suffix: str) -> dict | None:
    files = sorted(glob.glob(str(RESULTS / f"*_{suffix}.json")))
    return json.loads(Path(files[-1]).read_text(encoding="utf-8")) if files else None


def _collect_metrics() -> dict:
    metrics: dict = {}
    leak = _latest("ci_leakage")
    inj = _latest("ci_injection")
    ret = _latest("ci_retrieval")
    if leak:
        metrics["leakage_rate"] = leak["averages"].get("leakage_rate")
    if inj:
        metrics["attack_success_rate"] = inj["averages"].get("attack_success_rate")
    if ret:
        metrics["hit_rate"] = ret["averages"].get("hit_rate")
    return metrics


def main() -> None:
    thresholds = json.loads((REPO / "eval" / "thresholds.json").read_text(encoding="utf-8"))
    metrics = _collect_metrics()
    failures = gate_failures(metrics, thresholds)

    lines = ["## SecureRAG eval gate", "", "| metric | value | gate |", "|---|---|---|"]
    gates = {
        "leakage_rate": f"<= {thresholds['leakage_rate_max']}",
        "attack_success_rate": f"<= {thresholds['attack_success_rate_max']}",
        "hit_rate": f">= {thresholds['hit_rate_min']}",
    }
    for name, gate in gates.items():
        value = metrics.get(name, "n/a")
        lines.append(f"| {name} | {value} | {gate} |")
    lines.append("")
    lines.append("**FAILED:** " + "; ".join(failures) if failures else "**PASSED** ✅")

    report = "\n".join(lines)
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "gate_comment.md").write_text(report, encoding="utf-8")
    print(report)

    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
