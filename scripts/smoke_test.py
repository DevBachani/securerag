"""Phase 0 smoke test: prove the three external dependencies work.

Checks, in order:
  1. LLM   - one chat call to the configured provider ("Reply with OK").
  2. Embed - embed one sentence and print the vector length (expect 384).
  3. Qdrant- ping the vector DB and report its status.

This is intentionally a standalone script that reads env vars directly and
calls each SDK itself. The reusable `config.py` Settings and `providers.py`
factories belong to Phase 2 and are deliberately NOT built here.

Run:  uv run python scripts/smoke_test.py
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

# Expected embedding width for BAAI/bge-small-en-v1.5. The whole retrieval
# design (Qdrant collection size) depends on this number.
EXPECTED_EMBED_DIM = 384


def check_llm() -> bool:
    """Send one tiny prompt to the configured LLM and print the reply."""
    provider = os.environ.get("LLM_PROVIDER", "ollama").lower()
    model = os.environ.get("LLM_MODEL", "llama3.1:latest")

    if provider != "ollama":
        # Phase 0 only wires the provider this machine actually has (Ollama).
        # Other providers get their factory in Phase 2.
        print(f"[LLM]    SKIP - provider '{provider}' not wired in Phase 0")
        return False

    import ollama

    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    client = ollama.Client(host=base_url)
    resp = client.chat(
        model=model,
        messages=[{"role": "user", "content": "Reply with OK"}],
        options={"temperature": 0.0},
    )
    reply = resp["message"]["content"].strip()
    print(f"[LLM]    OK   - {provider}/{model} replied: {reply!r}")
    return True


def check_embedding() -> bool:
    """Embed one sentence with fastembed and verify the vector length."""
    from fastembed import TextEmbedding

    model_name = os.environ.get("EMBED_MODEL", "BAAI/bge-small-en-v1.5")
    embedder = TextEmbedding(model_name=model_name)
    vector = next(embedder.embed(["SecureRAG smoke test sentence."]))
    length = len(vector)
    status = "OK  " if length == EXPECTED_EMBED_DIM else "WARN"
    print(f"[EMBED]  {status} - {model_name} vector length: {length}")
    return length == EXPECTED_EMBED_DIM


def check_qdrant() -> bool:
    """Ping Qdrant and print how many collections it currently holds."""
    from qdrant_client import QdrantClient

    url = os.environ.get("QDRANT_URL", "http://localhost:6333")
    try:
        client = QdrantClient(url=url, timeout=5.0)
        collections = client.get_collections().collections
        print(f"[QDRANT] OK   - reachable at {url}, {len(collections)} collection(s)")
        return True
    except Exception as exc:  # noqa: BLE001 - smoke test reports, does not raise
        print(f"[QDRANT] FAIL - cannot reach {url}: {exc}")
        print("         Hint: start Docker Desktop, then `docker compose up -d`.")
        return False


def main() -> int:
    """Run all checks; exit non-zero if any fail so CI/you notice."""
    load_dotenv()
    print("SecureRAG Phase 0 smoke test")
    print("-" * 40)
    results = {
        "llm": check_llm(),
        "embedding": check_embedding(),
        "qdrant": check_qdrant(),
    }
    print("-" * 40)
    passed = sum(results.values())
    print(f"{passed}/{len(results)} checks passed.")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
