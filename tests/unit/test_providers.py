"""Phase 2 tests: provider dispatch, embedding cache and rate-limit retry."""

from __future__ import annotations

import pytest
from llama_index.llms.groq import Groq
from llama_index.llms.ollama import Ollama

from securerag import providers
from securerag.config import get_settings


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    """Each test must see its own env, not a cached Settings from a prior test."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_unknown_provider_raises_clear_error(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "does-not-exist")
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        providers.get_llm()


def test_get_llm_switches_backend_by_env(monkeypatch):
    # Ollama
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("LLM_MODEL", "llama3.1:latest")
    get_settings.cache_clear()
    assert isinstance(providers.get_llm(), Ollama)

    # Flip one env var -> different backend, no code change.
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("LLM_MODEL", "llama-3.3-70b-versatile")
    monkeypatch.setenv("GROQ_API_KEY", "test-key-not-real")
    get_settings.cache_clear()
    assert isinstance(providers.get_llm(), Groq)


def test_groq_without_key_raises(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "")
    with pytest.raises(ValueError, match="GROQ_API_KEY is empty"):
        providers.get_llm()


class _FakeInner:
    """Stand-in embedding model that counts how often it actually computes."""

    model_name = "fake-embed"
    embed_batch_size = 10

    def __init__(self) -> None:
        self.calls = 0

    def _get_text_embedding(self, text: str) -> list[float]:
        self.calls += 1
        return [float(len(text)), 1.0, 2.0]


def test_caching_embedding_serves_second_call_from_disk(tmp_path):
    fake = _FakeInner()
    emb = providers.CachingEmbedding(inner=fake, cache_dir=str(tmp_path / "cache"))

    first = emb.get_text_embedding("hello world")
    second = emb.get_text_embedding("hello world")

    assert first == second
    assert fake.calls == 1  # second call hit the cache, not the model


def test_rate_limit_retry_recovers():
    # Backoff waits ~1s then ~2s between the three attempts; acceptable for a test.
    attempts = {"n": 0}

    @providers.rate_limit_retry
    def flaky() -> str:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError("429 Too Many Requests")
        return "ok"

    assert flaky() == "ok"
    assert attempts["n"] == 3


def test_rate_limit_retry_ignores_other_errors():
    attempts = {"n": 0}

    @providers.rate_limit_retry
    def boom() -> None:
        attempts["n"] += 1
        raise ValueError("a plain bug in business logic")

    with pytest.raises(ValueError, match="plain bug"):
        boom()
    assert attempts["n"] == 1  # not retried
