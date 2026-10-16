"""结果融合策略。

背景（ADR-004 / ADR-005）：稀疏向量由 BGE-M3 应用层产出，按字切分。
中文同义词（如「肚子疼」vs「腹痛」）token 不重叠，稀疏内积几乎为 0，
甚至会把无关文档顶上来。因此：

- **稠密路为主**：语义匹配承担主要排序
- **稀疏路只做精确命中的加分**：仅当稀疏内积超过阈值（真实词元匹配）时，
  给对应文档加小额权重，不改变整体排序
- **检索模式可配置**：DENSE（仅语义）/ SPARSE（仅词元）/ HYBRID（融合），
  用 F30/F31 的黄金查询回归数据决定是否值得启用稀疏路
"""
from __future__ import annotations

from typing import Literal

RetrievalMode = Literal["DENSE", "SPARSE", "HYBRID"]


def fuse(
    dense_hits: list[dict],
    sparse_hits: list[dict],
    *,
    mode: str = "HYBRID",
    sparse_threshold: float = 0.01,
    sparse_weight: float = 0.1,
) -> list[dict]:
    """融合稠密与稀疏检索结果。

    - DENSE：直接返回稠密结果
    - SPARSE：只返回稀疏内积超过阈值的结果
    - HYBRID：稠密排序为主，稀疏精确命中（score ≥ threshold）加 sparse_weight * score
    """
    if mode == "DENSE":
        return _sorted(dense_hits)
    if mode == "SPARSE":
        return _sorted([h for h in sparse_hits if h.get("score", 0) >= sparse_threshold])

    # HYBRID
    sparse_map = {
        h["id"]: h.get("score", 0)
        for h in sparse_hits
        if h.get("score", 0) >= sparse_threshold
    }
    fused = []
    for h in dense_hits:
        bonus = sparse_weight * sparse_map.get(h["id"], 0.0)
        fused.append({**h, "score": h.get("score", 0) + bonus})
    return _sorted(fused)


def _sorted(hits: list[dict]) -> list[dict]:
    return sorted(hits, key=lambda h: h.get("score", 0), reverse=True)
