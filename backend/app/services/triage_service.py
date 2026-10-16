"""分诊服务：候选科室召回 + 分诊结论生成。

当前阶段（LLM 未接入前）只实现候选科室召回：主诉 → 向量化 → 混合检索 → 融合。
分诊结论的 LLM 生成在阶段十后续接入。
"""
from __future__ import annotations

from app.common.embedder import BaseEmbedder
from app.retrieval import KB_DEPT, MilvusStore
from app.retrieval.fusion import fuse


async def recall_depts(
    embedder: BaseEmbedder,
    store: MilvusStore,
    *,
    complaint: str,
    tenant_id: str,
    mode: str = "HYBRID",
    limit: int = 10,
) -> list[dict]:
    """主诉 → 候选科室召回（按 score 降序）。

    返回：[{"dept_code": str, "score": float}, ...]
    """
    emb = (await embedder.embed([complaint]))[0]

    dense_hits = store.dense_search(
        KB_DEPT,
        dense=emb.dense,
        filter_expr=f'tenant_id == "{tenant_id}"',
        limit=limit,
    )

    sparse_hits: list[dict] = []
    if emb.has_sparse and mode != "DENSE":
        sparse_hits = store.sparse_search(
            KB_DEPT,
            sparse=emb.sparse or {},
            filter_expr=f'tenant_id == "{tenant_id}"',
            limit=limit,
        )

    fused = fuse(dense_hits, sparse_hits, mode=mode)
    return [{"dept_code": h["dept_code"], "score": float(h.get("score", 0))} for h in fused]
