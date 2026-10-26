"""Phase 2 tests: Settings parse types correctly and fall back to defaults."""

from __future__ import annotations

import pytest

from securerag.config import Settings

# Keys we set in these tests; cleared from the real OS environment so a value in
# the developer's shell cannot leak in and make the assertions flaky.
_KEYS = ["LLM_PROVIDER", "LLM_MODEL", "RETRIEVAL_TOP_K", "HYBRID_ENABLED", "CHUNK_SIZE"]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for key in _KEYS:
        monkeypatch.delenv(key, raising=False)


def test_settings_load_and_coerce_types(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        "LLM_PROVIDER=groq\n"
        "LLM_MODEL=some-model\n"
        "RETRIEVAL_TOP_K=7\n"
        "HYBRID_ENABLED=false\n"
        "CHUNK_SIZE=256\n",
        encoding="utf-8",
    )
    settings = Settings(_env_file=str(env))

    assert settings.llm_provider == "groq"
    assert settings.llm_model == "some-model"
    assert settings.retrieval_top_k == 7  # coerced str -> int
    assert settings.hybrid_enabled is False  # coerced str -> bool
    assert settings.chunk_size == 256
    # A key absent from the file keeps its default.
    assert settings.embed_model == "BAAI/bge-small-en-v1.5"


def test_defaults_when_env_file_missing(tmp_path):
    settings = Settings(_env_file=str(tmp_path / "does_not_exist.env"))

    assert settings.llm_provider == "ollama"
    assert settings.hybrid_enabled is True
    assert settings.retrieval_top_k == 12
    assert settings.llm_temperature == 0.0
