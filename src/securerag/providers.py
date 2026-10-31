"""Factories for the pluggable model backends.

Everything that needs a model asks these factories, never a concrete class, so
swapping providers (Groq <-> Gemini <-> local Ollama) is a `.env` change with no
code change. Heavy or not-yet-needed backends (the cross-encoder reranker, Gemini,
LangChain-Groq) are imported lazily inside the factory, so importing this module
stays cheap and a machine only pays for what it actually uses.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from typing import Any

from llama_index.core.embeddings import BaseEmbedding
from llama_index.core.llms import LLM
from pydantic import PrivateAttr
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from .config import SUPPORTED_PROVIDERS, Settings, get_settings

# --------------------------------------------------------------------------- #
# Rate-limit retry
# --------------------------------------------------------------------------- #

# Substrings that mark a rate-limit / quota error across providers. We match on
# the message because each SDK raises a different exception type.
_RATE_LIMIT_HINTS = ("rate limit", "rate_limit", "429", "too many requests", "quota")


def _is_rate_limit_error(exc: BaseException) -> bool:
    """Return True if the exception looks like a provider rate-limit/quota error."""
    return any(hint in str(exc).lower() for hint in _RATE_LIMIT_HINTS)


# Exponential backoff: 1s, 2s, 4s, ... capped at 30s, up to 5 attempts, then
# re-raise the original error so callers see the real failure.
rate_limit_retry = retry(
    retry=retry_if_exception(_is_rate_limit_error),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    stop=stop_after_attempt(5),
    reraise=True,
)


def complete_with_retry(llm: LLM, prompt: str) -> Any:
    """Call `llm.complete(prompt)`, retrying on rate-limit errors with backoff."""

    @rate_limit_retry
    def _call() -> Any:
        return llm.complete(prompt)

    return _call()


# --------------------------------------------------------------------------- #
# Embedding cache
# --------------------------------------------------------------------------- #


class CachingEmbedding(BaseEmbedding):
    """Wrap an embedding model with an on-disk cache of computed vectors.

    Keyed by sha256(model_name + text), so re-embedding the same text (common
    when re-running ingestion or eval) is a disk read instead of a model call.
    The cache stores vectors, not model weights.
    """

    # Declared as private attrs so the pydantic-based BaseEmbedding allows them.
    _inner: Any = PrivateAttr()
    _cache: Any = PrivateAttr()

    def __init__(self, inner: BaseEmbedding, cache_dir: str, **kwargs: Any) -> None:
        """Wrap `inner`, storing computed vectors in a diskcache at `cache_dir`."""
        import diskcache

        super().__init__(
            model_name=getattr(inner, "model_name", "cached"),
            embed_batch_size=getattr(inner, "embed_batch_size", 10),
            **kwargs,
        )
        self._inner = inner
        self._cache = diskcache.Cache(cache_dir)

    def _key(self, text: str) -> str:
        return hashlib.sha256(f"{self.model_name}:{text}".encode()).hexdigest()

    def _get_text_embedding(self, text: str) -> list[float]:
        key = self._key(text)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        vector = self._inner._get_text_embedding(text)
        self._cache.set(key, vector)
        return vector

    def _get_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        return [self._get_text_embedding(t) for t in texts]

    def _get_query_embedding(self, query: str) -> list[float]:
        # A query embeds identically to a passage for bge-small, so share the cache.
        return self._get_text_embedding(query)

    async def _aget_query_embedding(self, query: str) -> list[float]:
        return self._get_query_embedding(query)

    async def _aget_text_embedding(self, text: str) -> list[float]:
        return self._get_text_embedding(text)


# --------------------------------------------------------------------------- #
# LLM factories
# --------------------------------------------------------------------------- #


def _build_llama_llm(provider: str, model: str, temperature: float, settings: Settings) -> LLM:
    """Build a LlamaIndex LLM for the named provider, or raise a clear error."""
    provider = provider.lower()
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(
            f"Unknown LLM provider {provider!r}. "
            f"Set LLM_PROVIDER to one of: {', '.join(sorted(SUPPORTED_PROVIDERS))}."
        )

    if provider == "ollama":
        from llama_index.llms.ollama import Ollama

        return Ollama(
            model=model,
            base_url=settings.ollama_base_url,
            temperature=temperature,
            context_window=settings.llm_context_window,
            request_timeout=settings.llm_request_timeout,
        )

    if provider == "groq":
        from llama_index.llms.groq import Groq

        if not settings.groq_api_key:
            raise ValueError("GROQ_API_KEY is empty; set it in .env to use the groq provider.")
        return Groq(model=model, api_key=settings.groq_api_key, temperature=temperature)

    # provider == "gemini"
    try:
        from llama_index.llms.google_genai import GoogleGenAI
    except ImportError as exc:
        raise RuntimeError(
            "Gemini backend not installed. Run `uv add llama-index-llms-google-genai` to use it."
        ) from exc
    if not settings.google_api_key:
        raise ValueError("GOOGLE_API_KEY is empty; set it in .env to use the gemini provider.")
    return GoogleGenAI(model=model, api_key=settings.google_api_key, temperature=temperature)


def get_llm() -> LLM:
    """Build the main answering LLM, per `LLM_PROVIDER` / `LLM_MODEL`."""
    s = get_settings()
    return _build_llama_llm(s.llm_provider, s.llm_model, s.llm_temperature, s)


def get_judge_llm() -> LLM:
    """Build the evaluation judge LLM; always temperature 0 for consistent grading."""
    s = get_settings()
    return _build_llama_llm(s.judge_provider, s.judge_model, 0.0, s)


def get_langchain_llm() -> Any:
    """Build a LangChain chat model for the LangGraph agent (Phases 11+)."""
    s = get_settings()
    provider = s.llm_provider.lower()

    if provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=s.llm_model, base_url=s.ollama_base_url, temperature=s.llm_temperature
        )

    if provider == "groq":
        try:
            from langchain_groq import ChatGroq
        except ImportError as exc:
            raise RuntimeError(
                "LangChain Groq not installed. Run `uv add langchain-groq` to use it."
            ) from exc
        if not s.groq_api_key:
            raise ValueError("GROQ_API_KEY is empty; set it in .env to use the groq provider.")
        return ChatGroq(model=s.llm_model, api_key=s.groq_api_key, temperature=s.llm_temperature)

    raise ValueError(
        f"get_langchain_llm() does not support provider {provider!r} yet "
        "(supported: ollama, groq)."
    )


# --------------------------------------------------------------------------- #
# Embedding / reranker factories
# --------------------------------------------------------------------------- #


@lru_cache
def get_embed_model() -> BaseEmbedding:
    """Return the embedding model (bge-small, 384-dim) wrapped in the on-disk cache.

    Cached so the fastembed model is loaded once per process instead of on every
    query; the on-disk vector cache sits on top of that single instance.
    """
    s = get_settings()
    from llama_index.embeddings.fastembed import FastEmbedEmbedding

    inner = FastEmbedEmbedding(model_name=s.embed_model)
    return CachingEmbedding(inner=inner, cache_dir=s.embed_cache_dir)


@lru_cache
def get_sparse_embed_model() -> Any:
    """Return the sparse BM25 embedding model (fastembed) for hybrid search.

    Cached so the model loads once per process. Used to produce the sparse vector
    stored per chunk and the sparse query vector at search time.
    """
    from fastembed import SparseTextEmbedding

    return SparseTextEmbedding(model_name=get_settings().sparse_embed_model)


def get_reranker() -> Any:
    """Build the cross-encoder reranker. Imported lazily; its heavy deps land in Phase 8."""
    s = get_settings()
    try:
        from llama_index.postprocessor.flag_embedding_reranker import FlagEmbeddingReranker
    except ImportError as exc:
        raise RuntimeError(
            "Reranker not available yet (needs PyTorch). It is wired up in Phase 8 via "
            "`uv add llama-index-postprocessor-flag-embedding-reranker`."
        ) from exc
    return FlagEmbeddingReranker(model=s.rerank_model, top_n=s.rerank_top_n)
