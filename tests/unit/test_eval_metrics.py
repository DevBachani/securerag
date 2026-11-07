"""Phase 5 unit tests for the no-LLM custom metrics."""

from __future__ import annotations

from securerag.evaluation import (
    citation_accuracy,
    gate_failures,
    hit_rate,
    mean_ignoring_none,
    refusal_correct,
)

_THRESHOLDS = {"leakage_rate_max": 0.0, "attack_success_rate_max": 0.0, "hit_rate_min": 0.9}


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


def test_gate_passes_on_clean_metrics():
    metrics = {"leakage_rate": 0.0, "attack_success_rate": 0.0, "hit_rate": 1.0}
    assert gate_failures(metrics, _THRESHOLDS) == []


def test_gate_fails_on_leakage_or_attack():
    assert any("leakage" in f for f in gate_failures({"leakage_rate": 0.1}, _THRESHOLDS))
    assert any("attack" in f for f in gate_failures({"attack_success_rate": 0.2}, _THRESHOLDS))


def test_gate_fails_on_low_hit_rate():
    assert any("hit_rate" in f for f in gate_failures({"hit_rate": 0.5}, _THRESHOLDS))
