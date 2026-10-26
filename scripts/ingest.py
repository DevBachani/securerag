"""CLI to ingest the corpus into Qdrant.

Usage:
  uv run python scripts/ingest.py           # upsert (idempotent)
  uv run python scripts/ingest.py --reset   # drop and rebuild the collection
"""

from __future__ import annotations

import argparse
import time

from securerag.config import get_settings
from securerag.ingestion.pipeline import ingest


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest the Acme corpus into Qdrant.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop the collection and rebuild it from scratch.",
    )
    args = parser.parse_args()

    settings = get_settings()
    start = time.perf_counter()
    stats = ingest(reset=args.reset)
    elapsed = time.perf_counter() - start

    print(f"Collection : {settings.qdrant_collection}")
    print(f"Files      : {stats['files']}")
    print(f"Chunks     : {stats['chunks']}")
    print(f"Points     : {stats['points']}")
    print(f"Time       : {elapsed:.1f}s")


if __name__ == "__main__":
    main()
