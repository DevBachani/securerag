"""Central configuration for SecureRAG.

Every tunable value the system uses lives here as a typed field on `Settings`,
read from environment variables / the `.env` file by pydantic-settings. Nothing
elsewhere in the codebase should read `os.environ` directly or hard-code a model
name, URL or threshold -- it should import `get_settings()` instead. That single
rule is what makes the whole system swappable and testable.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# The set of LLM backends the provider factory knows how to build. Kept here so
# both config validation and the factory agree on one list.
SUPPORTED_PROVIDERS = frozenset({"groq", "gemini", "ollama"})


class Settings(BaseSettings):
    """All runtime configuration, loaded from the environment or `.env`.

    Field names are the lower-case form of the `.env` keys; pydantic-settings
    matches them case-insensitively, so `LLM_PROVIDER` fills `llm_provider`.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- LLM ---
    llm_provider: str = "ollama"
    llm_model: str = "llama3.1:latest"
    llm_temperature: float = 0.0  # low temperature: factual, repeatable answers
    # Context window for local models. Ollama's default (2048) truncates multi-chunk
    # RAG context silently; 4096 fits the ~6 chunks the generator sees.
    llm_context_window: int = 4096
    # Timeout for a single LLM call (seconds). Generous so slow local models don't
    # time out mid-generation; cloud providers answer well within it.
    llm_request_timeout: float = 600.0
    # How many of the retrieved chunks are actually sent to the generator. Smaller
    # than RETRIEVAL_TOP_K so prompts stay compact (retrieval still fetches top_k).
    answer_context_chunks: int = 6
    groq_api_key: str = ""
    google_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    judge_provider: str = "ollama"
    judge_model: str = "llama3.1:latest"

    # --- Embeddings / reranker ---
    embed_model: str = "BAAI/bge-small-en-v1.5"
    sparse_embed_model: str = "Qdrant/bm25"  # sparse/BM25 vectors for hybrid search
    embed_cache_dir: str = ".embeddings_cache"
    rerank_model: str = "BAAI/bge-reranker-base"
    rerank_top_n: int = 4

    # --- Governance ---
    pii_redaction_enabled: bool = True  # redact contact/ID PII before embedding

    # --- Agent ---
    agent_checkpoint_db: str = "checkpoints.db"  # SQLite file for LangGraph conversation state
    self_correction_enabled: bool = True  # grade context, rewrite weak queries, check grounding
    max_rewrites: int = 2  # query-rewrite retries before refusing
    max_generations: int = 2  # answer attempts (1 regenerate) before refusing on grounding failure

    # --- Retrieval ---
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection: str = "acme_docs"
    retrieval_top_k: int = 12
    hybrid_enabled: bool = True
    rerank_enabled: bool = True
    chunk_size: int = 512
    chunk_overlap: int = 64

    # --- App ---
    database_url: str = "sqlite:///./securerag.db"
    jwt_secret: str = "change-me"
    jwt_expire_minutes: int = 60
    api_base_url: str = "http://localhost:8000"
    ui_origin: str = "http://localhost:8501"  # Streamlit UI origin allowed by CORS
    rate_limit_per_minute: int = 20  # per-user chat rate limit

    # --- Observability ---
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide Settings, parsed once and cached.

    Cached so every caller shares one object and the `.env` file is read a
    single time. Tests that need a different environment should construct
    `Settings(_env_file=...)` directly rather than mutating the cache.
    """
    return Settings()
