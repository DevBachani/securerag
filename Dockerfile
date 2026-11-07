# Single image for both the API and the UI (compose runs it with different commands).
# Built on the uv image; models are pre-downloaded so the first request isn't slow.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    FASTEMBED_CACHE_PATH=/app/.fastembed_cache \
    HF_HOME=/app/.hf \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# 1) Dependencies first (cached layer): needs pyproject + lock + the package source,
#    because the project installs itself (hatchling, src/ layout).
COPY pyproject.toml uv.lock ./
COPY src ./src
RUN uv sync --frozen --no-dev

# 2) Application code and data.
COPY data ./data
COPY eval ./eval
COPY scripts ./scripts
COPY ui ./ui

# 3) Pre-download the local models (embedding + sparse BM25 + reranker) at build time.
RUN python -c "from fastembed import TextEmbedding, SparseTextEmbedding; \
TextEmbedding('BAAI/bge-small-en-v1.5'); SparseTextEmbedding('Qdrant/bm25')" && \
    python -c "from fastembed.rerank.cross_encoder import TextCrossEncoder; \
TextCrossEncoder('BAAI/bge-reranker-base')"

# 4) Non-root user; /data holds the SQLite DBs (mounted volume at runtime).
RUN useradd --create-home appuser && mkdir -p /data && chown -R appuser /app /data
USER appuser

EXPOSE 8000 8501

# Default command (overridden per service in docker-compose.yml).
CMD ["uvicorn", "securerag.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
