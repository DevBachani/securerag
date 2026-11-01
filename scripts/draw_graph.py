"""Render the agent graph to docs/graph.mmd (always) and docs/graph.png (if possible).

Usage:  uv run python scripts/draw_graph.py
"""

from __future__ import annotations

from pathlib import Path

from securerag.agent.graph import build_graph


def main() -> None:
    docs = Path(__file__).resolve().parents[1] / "docs"
    docs.mkdir(exist_ok=True)
    graph = build_graph().compile().get_graph()

    (docs / "graph.mmd").write_text(graph.draw_mermaid(), encoding="utf-8")
    print("wrote docs/graph.mmd")

    try:
        (docs / "graph.png").write_bytes(graph.draw_mermaid_png())
        print("wrote docs/graph.png")
    except Exception as exc:  # noqa: BLE001 - PNG needs network/mermaid; mmd is the fallback
        print(f"graph.png skipped (needs network): {str(exc)[:80]}")


if __name__ == "__main__":
    main()
