"""Phase 7 unit tests: Reciprocal Rank Fusion (no Qdrant)."""

from __future__ import annotations

from securerag.retrieval.hybrid import reciprocal_rank_fusion


class _Point:
    def __init__(self, id_: str, payload: dict | None = None) -> None:
        self.id = id_
        self.payload = payload or {}


def test_rrf_rewards_appearing_in_both_lists():
    dense = [_Point("a"), _Point("b"), _Point("c")]
    sparse = [_Point("b"), _Point("d"), _Point("a")]
    fused = reciprocal_rank_fusion([dense, sparse])
    ids = [h.id for h in fused]

    assert set(ids) == {"a", "b", "c", "d"}
    # b is rank 0 in sparse and rank 1 in dense -> highest combined score.
    assert ids[0] == "b"
    # d (one list, rank 1) outranks c (one list, rank 2).
    assert ids.index("d") < ids.index("c")


def test_rrf_single_list_preserves_order():
    one = [_Point("x"), _Point("y"), _Point("z")]
    fused = reciprocal_rank_fusion([one])
    assert [h.id for h in fused] == ["x", "y", "z"]


def test_rrf_carries_payload():
    fused = reciprocal_rank_fusion([[_Point("a", {"doc_id": "d1"})]])
    assert fused[0].payload["doc_id"] == "d1"
