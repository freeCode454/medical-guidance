"""向量化后端抽象。

本项目有两类向量化后端，用途不同：

| 后端 | 稠密向量 | 稀疏向量 | 用途 |
|---|---|---|---|
| `local`（本地 BGE-M3） | ✅ | ✅ **同一模型产出** | **主力**。两路向量同源，混合检索效果稳定 |
| `api`（云端 BGE-M3） | ✅ | ❌ 云端只返回稠密向量 | **金标准**。用于校验本地量化后的向量是否失真 |

⚠️ 不要把两类后端产出的向量写进同一个 Milvus 集合。
   稀疏向量的打分口径不同（本地是模型权重，Milvus 内置 BM25 是词频统计），
   混用会导致 RRF 融合权重失效。
"""

from __future__ import annotations

import asyncio
import logging
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Embedding:
    """一条文本的向量化结果。"""

    dense: list[float]
    # 稀疏词元权重：{token_id: weight}；后端不支持时为 None
    sparse: dict[int, float] | None = field(default=None)

    @property
    def has_sparse(self) -> bool:
        return bool(self.sparse)


def l2_normalize(matrix: np.ndarray) -> np.ndarray:
    """按行做 L2 归一化。零向量保持为零，避免除零。"""
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


def to_milvus_sparse(weights: dict, *, top_k: int = 256) -> dict[int, float]:
    """BGE-M3 的稀疏权重 → Milvus 稀疏向量格式。

    Milvus 的稀疏向量是 {维度下标: 权重}，权重必须为非负有限值。
    过长会拖慢检索，按权重排序截断到 top_k。词元下标自上而下取最大值合并。
    """
    merged: dict[int, float] = {}
    for key, value in weights.items():
        try:
            index = int(key)
            weight = float(value)
        except (TypeError, ValueError):
            continue
        if weight <= 0 or not np.isfinite(weight):
            continue
        if weight > merged.get(index, 0.0):
            merged[index] = weight

    if len(merged) <= top_k:
        return merged
    top = sorted(merged.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
    return dict(top)


class BaseEmbedder(ABC):
    """向量化后端接口。"""

    #: 是否产出稀疏向量
    supports_sparse: bool = False

    @property
    @abstractmethod
    def name(self) -> str:
        """后端标识，用于日志与自检接口。"""

    @abstractmethod
    async def embed(self, texts: Sequence[str]) -> list[Embedding]:
        """批量向量化，返回顺序与入参一致。"""

    @abstractmethod
    async def aclose(self) -> None:
        """释放资源。"""


class ApiEmbedder(BaseEmbedder):
    """云端向量化。只产出稠密向量。"""

    supports_sparse = False

    def __init__(self, client, model: str) -> None:
        self._client = client
        self._model = model

    @property
    def name(self) -> str:
        return f"api:{self._model}"

    async def embed(self, texts: Sequence[str]) -> list[Embedding]:
        if not texts:
            return []
        response = await self._client.embeddings.create(
            model=self._model,
            input=list(texts),
        )
        ordered = sorted(response.data, key=lambda d: d.index)
        return [Embedding(dense=list(d.embedding)) for d in ordered]

    async def aclose(self) -> None:
        await self._client.close()


class LocalBgeM3Embedder(BaseEmbedder):
    """本地 BGE-M3，同时产出稠密与稀疏向量。

    模型较大（fp32 约 2.2 GB），因此：

    - **懒加载**：首次调用时才载入，避免拖慢服务启动
    - **线程池执行**：模型推理是 CPU 密集型，必须放到线程里，否则阻塞事件循环
    - **只加载一次**：用锁保证并发首次调用不会重复加载

    内存不足时请先做 ONNX int8 量化，见 docs/开发环境与后端切换方案.md 4.1 节。
    """

    supports_sparse = True

    def __init__(
        self,
        model_path: str,
        *,
        batch_size: int = 8,
        max_length: int = 512,
        use_fp16: bool = False,
        sparse_top_k: int = 256,
    ) -> None:
        self._model_path = model_path
        self._batch_size = batch_size
        self._max_length = max_length
        self._use_fp16 = use_fp16
        self._sparse_top_k = sparse_top_k

        self._model = None
        self._load_lock = threading.Lock()

    @property
    def name(self) -> str:
        return f"local:{self._model_path}"

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        with self._load_lock:
            if self._model is not None:
                return
            try:
                from FlagEmbedding import BGEM3FlagModel
            except ImportError as exc:  # pragma: no cover - 依赖缺失时给出明确指引
                raise RuntimeError(
                    "本地向量化需要 FlagEmbedding，请先执行："
                    "pip install -U FlagEmbedding"
                ) from exc

            logger.info("载入本地向量模型：%s", self._model_path)
            self._model = BGEM3FlagModel(self._model_path, use_fp16=self._use_fp16)
            logger.info("本地向量模型载入完成")

    def _encode_sync(self, texts: list[str]) -> list[Embedding]:
        self._ensure_loaded()
        assert self._model is not None

        output = self._model.encode(
            texts,
            batch_size=self._batch_size,
            max_length=self._max_length,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False,  # 多向量占用大且本项目不需要
        )

        dense_matrix = l2_normalize(np.asarray(output["dense_vecs"], dtype=np.float32))
        lexical = output.get("lexical_weights") or [{} for _ in texts]

        results: list[Embedding] = []
        for dense_row, weights in zip(dense_matrix, lexical):
            results.append(
                Embedding(
                    dense=dense_row.tolist(),
                    sparse=to_milvus_sparse(weights, top_k=self._sparse_top_k),
                )
            )
        return results

    async def embed(self, texts: Sequence[str]) -> list[Embedding]:
        if not texts:
            return []
        # 推理是 CPU 密集操作，放到线程池，避免阻塞事件循环
        return await asyncio.to_thread(self._encode_sync, list(texts))

    async def aclose(self) -> None:
        self._model = None


def build_embedder(settings) -> BaseEmbedder:
    """按配置构造向量化后端。"""
    from openai import AsyncOpenAI

    if settings.embedding_provider == "local":
        return LocalBgeM3Embedder(
            settings.embedding_model_path,
            batch_size=settings.embedding_batch_size,
            max_length=settings.embedding_max_length,
            use_fp16=settings.embedding_use_fp16,
            sparse_top_k=settings.embedding_sparse_top_k,
        )

    client = AsyncOpenAI(
        base_url=settings.effective_embedding_base_url,
        api_key=settings.effective_embedding_api_key,
        timeout=settings.llm_timeout_seconds,
    )
    return ApiEmbedder(client, settings.embedding_model)
