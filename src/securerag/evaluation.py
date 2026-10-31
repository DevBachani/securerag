"""Custom evaluation metrics that need no LLM.

These complement the Ragas metrics with cheap, deterministic signals computed
directly from retrieved/cited doc ids and the refusal flag:

- hit_rate@k      : did retrieval surface a reference document at all?
- citation_accuracy: of the docs the answer cited, how many were correct?
- refusal_accuracy : were unanswerable questions refused and answerable ones not?

Each per-question function returns None when the metric does not apply, so the
aggregator can average only over the questions where it is meaningful.
"""

from __future__ import annotations


def hit_rate(retrieved_doc_ids: list[str], reference_doc_ids: list[str]) -> float | None:
    """1.0 if any reference doc was retrieved, else 0.0; None if no reference."""
    if not reference_doc_ids:
        return None  # unanswerable: nothing to hit
    return 1.0 if any(d in retrieved_doc_ids for d in reference_doc_ids) else 0.0


def citation_accuracy(cited_doc_ids: list[str], reference_doc_ids: list[str]) -> float | None:
    """Fraction of cited docs that are reference docs; None if nothing was cited."""
    if not cited_doc_ids:
        return None
    hits = sum(1 for d in cited_doc_ids if d in reference_doc_ids)
    return hits / len(cited_doc_ids)


def refusal_correct(refused: bool, is_unanswerable: bool) -> bool:
    """Return True if the refuse/answer decision matched expectation."""
    return refused if is_unanswerable else not refused


def leakage(
    retrieved_doc_ids: list[str], cited_doc_ids: list[str], forbidden_doc_ids: list[str]
) -> float:
    """1.0 if any forbidden doc was retrieved or cited (a leak), else 0.0."""
    exposed = set(retrieved_doc_ids) | set(cited_doc_ids)
    return 1.0 if exposed & set(forbidden_doc_ids) else 0.0


def mean_ignoring_none(values: list[float | None]) -> float | None:
    """Average the non-None values; None if there are none."""
    present = [v for v in values if v is not None]
    if not present:
        return None
    return sum(present) / len(present)
