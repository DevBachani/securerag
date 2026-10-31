"""Phase 8 unit tests: reranking orders by cross-encoder score and keeps top_n."""

from __future__ import annotations

from dataclasses import dataclass

from securerag.retrieval import rerank as rerank_mod


@dataclass
class _Item:
    text: str
    doc_id: str
    score: float = 0.0


class _FakeReranker:
    """Scores a candidate high iff it contains the word 'target'."""

    def rerank(self, query: str, docs: list[str]) -> list[float]:
        return [9.0 if "target" in d else 0.1 for d in docs]


def test_rerank_orders_by_score_and_keeps_top_n(monkeypatch):
    monkeypatch.setattr(rerank_mod, "get_reranker", lambda: _FakeReranker())
    items = [_Item("aaa", "d1"), _Item("the target bbb", "d2"), _Item("ccc", "d3")]

    out = rerank_mod.rerank("q", items, top_n=2)

    assert len(out) == 2
    assert out[0].doc_id == "d2"
    assert out[0].score == 9.0


def test_rerank_empty_is_noop():
    assert rerank_mod.rerank("q", [], 4) == []
