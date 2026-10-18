"""检索融合：稠密为主、稀疏只做小额加分。"""
from __future__ import annotations

from app.retrieval.fusion import fuse


def test_dense_mode_ignores_sparse() -> None:
    dense = [{"id": "a", "score": 0.8}, {"id": "b", "score": 0.6}]
    sparse = [{"id": "b", "score": 0.9}]
    assert [h["id"] for h in fuse(dense, sparse, mode="DENSE")] == ["a", "b"]


def test_hybrid_adds_bonus_without_flipping_order() -> None:
    dense = [{"id": "a", "score": 0.8}, {"id": "b", "score": 0.6}]
    sparse = [{"id": "b", "score": 0.5}]
    fused = fuse(dense, sparse, mode="HYBRID", sparse_weight=0.1)
    assert [h["id"] for h in fused] == ["a", "b"]
    assert fused[1]["score"] > 0.6


def test_sparse_mode_filters_low_scores() -> None:
    sparse = [{"id": "a", "score": 0.5}, {"id": "b", "score": 0.001}]
    assert [h["id"] for h in fuse([], sparse, mode="SPARSE")] == ["a"]


def test_hybrid_tolerates_empty_inputs() -> None:
    assert fuse([], [], mode="HYBRID") == []
