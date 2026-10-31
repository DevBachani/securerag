"""CLI to ingest / sync the corpus into Qdrant.

Usage:
  uv run python scripts/ingest.py            # incremental sync (only what changed)
  uv run python scripts/ingest.py --reset    # drop and rebuild the whole collection
"""

from __future__ import annotations

import argparse
import time

from securerag.config import get_settings
from securerag.ingestion.pipeline import ingest
from securerag.ingestion.sync import reset_state, sync


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest or sync the Acme corpus into Qdrant.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop the collection and rebuild it from scratch (also resets ingest_state).",
    )
    args = parser.parse_args()

    settings = get_settings()
    start = time.perf_counter()

    if args.reset:
        stats = ingest(reset=True)
        reset_state()
        elapsed = time.perf_counter() - start
        print(f"Collection : {settings.qdrant_collection}  (full rebuild)")
        print(f"Files      : {stats['files']}")
        print(f"Chunks     : {stats['chunks']}")
        print(f"Points     : {stats['points']}")
        print(f"Time       : {elapsed:.1f}s")
    else:
        counts = sync()
        elapsed = time.perf_counter() - start
        print(f"Collection : {settings.qdrant_collection}  (incremental sync)")
        print(f"Added      : {counts['added']}")
        print(f"Updated    : {counts['updated']}")
        print(f"ACL-updated: {counts['acl_updated']}")
        print(f"Deleted    : {counts['deleted']}")
        print(f"Unchanged  : {counts['unchanged']}")
        print(f"Time       : {elapsed:.1f}s")


if __name__ == "__main__":
    main()
