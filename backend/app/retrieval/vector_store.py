"""Milvus 向量库客户端。

封装集合创建、索引、插入与混合检索。稀疏向量由应用层（BGE-M3）产出，
度量用内积（IP）；稠密向量度量用余弦相似度（COSINE）。

Milvus 的 insert 是异步的，`insert` 后必须 `flush` 才能统计与检索（踩坑记录）。
"""
from __future__ import annotations

import contextlib
import logging
from typing import Any

from pymilvus import (
    AnnSearchRequest,
    DataType,
    MilvusClient,
    RRFRanker,
)

from app.retrieval.collections import VectorCollection

logger = logging.getLogger(__name__)

# 标量字段类型映射：collections.py 里的类型字符串 → Milvus 字段定义
_SCALAR_TYPES: dict[str, tuple[DataType, int]] = {
    "varchar1": (DataType.VARCHAR, 1),
    "varchar8": (DataType.VARCHAR, 8),
    "varchar16": (DataType.VARCHAR, 16),
    "varchar32": (DataType.VARCHAR, 32),
    "varchar64": (DataType.VARCHAR, 64),
    "varchar128": (DataType.VARCHAR, 128),
    "varchar4096": (DataType.VARCHAR, 4096),
}


class MilvusStore:
    """Milvus 向量库客户端（Standalone）。"""

    def __init__(self, uri: str) -> None:
        self._client = MilvusClient(uri)

    # ---------------- 集合管理 ----------------

    def ensure_collection(self, spec: VectorCollection) -> bool:
        """建集合（幂等）。返回是否新建。"""
        if self._client.has_collection(spec.name):
            return False

        schema = self._client.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field("id", DataType.VARCHAR, is_primary=True, max_length=64)
        schema.add_field("dense", DataType.FLOAT_VECTOR, dim=1024)
        if spec.has_sparse:
            schema.add_field("sparse", DataType.SPARSE_FLOAT_VECTOR)

        for field_name, type_str in spec.scalar_fields:
            dtype, max_len = _SCALAR_TYPES[type_str]
            is_pk = spec.partition_key == field_name
            schema.add_field(
                field_name, dtype, max_length=max_len, is_partition_key=is_pk
            )

        self._client.create_collection(spec.name, schema=schema)
        logger.info("已创建向量集合：%s", spec.name)
        return True

    def create_index(self, spec: VectorCollection) -> None:
        """建索引（幂等）并加载集合。"""
        index_params = self._client.prepare_index_params()
        index_params.add_index(
            field_name="dense",
            index_type="HNSW",
            metric_type="COSINE",
            params={"M": 32, "efConstruction": 256},
        )
        if spec.has_sparse:
            index_params.add_index(
                field_name="sparse",
                index_type="SPARSE_INVERTED_INDEX",
                metric_type="IP",  # 稀疏向量度量内积（ADR-004）
                params={},
            )
        self._client.create_index(spec.name, index_params)
        self._client.load_collection(spec.name)

    def drop(self, name: str) -> None:
        if self._client.has_collection(name):
            self._client.drop_collection(name)

    # ---------------- 写入 ----------------

    def upsert(self, spec: VectorCollection, rows: list[dict[str, Any]]) -> None:
        """插入/覆盖向量。rows 每项含 id/dense/[sparse]/标量字段。"""
        if not rows:
            return
        self._client.upsert(spec.name, rows)
        self._client.flush(spec.name)  # insert 是异步的，必须 flush

    def delete(self, spec: VectorCollection, ids: list[str]) -> None:
        if ids:
            self._client.delete(spec.name, ids=ids)

    # ---------------- 检索 ----------------

    def hybrid_search(
        self,
        spec: VectorCollection,
        *,
        dense: list[float],
        sparse: dict[int, float],
        filter_expr: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """稠密 + 稀疏混合检索（RRF 融合）。"""
        dense_req = AnnSearchRequest(
            data=[dense],
            anns_field="dense",
            param={"metric_type": "COSINE"},
            limit=limit,
        )
        sparse_req = AnnSearchRequest(
            data=[sparse],
            anns_field="sparse",
            param={"metric_type": "IP"},
            limit=limit,
        )
        hits = self._client.hybrid_search(
            spec.name,
            [dense_req, sparse_req],
            ranker=RRFRanker(),
            limit=limit,
            filter=filter_expr or "",
            output_fields=["id", *[f for f, _ in spec.scalar_fields]],
        )
        return self._normalize(hits)

    def dense_search(
        self,
        spec: VectorCollection,
        *,
        dense: list[float],
        filter_expr: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """纯稠密检索。"""
        hits = self._client.search(
            spec.name,
            data=[dense],
            anns_field="dense",
            limit=limit,
            filter=filter_expr or "",
            output_fields=["id", *[f for f, _ in spec.scalar_fields]],
        )
        return self._normalize(hits)

    def sparse_search(
        self,
        spec: VectorCollection,
        *,
        sparse: dict[int, float],
        filter_expr: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """纯稀疏检索（内积 IP）。"""
        hits = self._client.search(
            spec.name,
            data=[sparse],
            anns_field="sparse",
            search_params={"metric_type": "IP"},
            limit=limit,
            filter=filter_expr or "",
            output_fields=["id", *[f for f, _ in spec.scalar_fields]],
        )
        return self._normalize(hits)

    def _normalize(self, hits: list[list[dict]]) -> list[dict[str, Any]]:
        """把 Milvus 的嵌套结果拍平成 [{'id':..., 'distance':..., ...字段}]。"""
        if not hits or not hits[0]:
            return []
        out = []
        for h in hits[0]:
            entity = h.get("entity", h)
            item = {"id": entity.get("id"), "score": h.get("distance", h.get("score"))}
            for k, v in entity.items():
                if k not in ("id",):
                    item[k] = v
            out.append(item)
        return out

    def ping(self) -> None:
        """就绪探针：能列出集合即视为可用（连接失败会抛异常）。"""
        self._client.list_collections()

    def close(self) -> None:
        with contextlib.suppress(Exception):  # pragma: no cover
            self._client.close()
