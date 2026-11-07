"""Block until Qdrant is reachable (used by the Docker init step before ingest).

Usage:  uv run python scripts/wait_for_qdrant.py
"""

from __future__ import annotations

import sys
import time

import httpx

from securerag.config import get_settings


def main() -> None:
    url = get_settings().qdrant_url.rstrip("/") + "/healthz"
    for _ in range(60):
        try:
            if httpx.get(url, timeout=3).status_code == 200:
                print(f"Qdrant ready at {url}")
                return
        except Exception:
            pass
        time.sleep(2)
    print(f"Qdrant not reachable at {url} after ~120s", file=sys.stderr)
    raise SystemExit(1)


if __name__ == "__main__":
    main()
