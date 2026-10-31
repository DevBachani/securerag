"""Phase 5 unit tests for the no-LLM custom metrics."""

from __future__ import annotations

from securerag.evaluation import (
    citation_accuracy,
    hit_rate,
    mean_ignoring_none,
    refusal_correct,
)


def test_hit_rate():
    assert hit_rate(["a", "b"], ["b"]) == 1.0
    assert hit_rate(["a", "b"], ["c"]) == 0.0
    assert hit_rate(["a"], []) is None  # unanswerable: not applicable


def test_citation_accuracy():
    assert citation_accuracy(["a", "b"], ["a", "b"]) == 1.0
    assert citation_accuracy(["a", "x"], ["a", "b"]) == 0.5
    assert citation_accuracy([], ["a"]) is None  # nothing cited


def test_refusal_correct():
    assert refusal_correct(refused=True, is_unanswerable=True) is True
    assert refusal_correct(refused=False, is_unanswerable=True) is False
    assert refusal_correct(refused=False, is_unanswerable=False) is True
    assert refusal_correct(refused=True, is_unanswerable=False) is False


def test_mean_ignoring_none():
    assert mean_ignoring_none([1.0, 0.0, None]) == 0.5
    assert mean_ignoring_none([None, None]) is None
    assert mean_ignoring_none([]) is None
