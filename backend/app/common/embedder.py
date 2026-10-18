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
import zipfile
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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
    """本地 BGE-M3（ONNX Runtime），同时产出稠密与稀疏向量。

    采用 ONNX Runtime + tokenizers + numpy，不引入 torch / FlagEmbedding
    （镜像体积少约 2 GB，见《01 需求》8.1.1）。

    稀疏向量由模型自带权重计算：``relu(token_embeddings @ W.T + b)``，
    再按 token_id 取 max。W、b 从 ``sparse_linear.pt``（torch zip 格式）读取：
    ``data/0`` = weight (1, 1024) float16，``data/1`` = bias (1,) float16。

    懒加载 + 线程池执行（推理是 CPU 密集操作），用锁保证只加载一次。
    """

    supports_sparse = True

    #: 稀疏计算需排除的特殊 token（<s>/<pad>/</s>/<unk>），避免噪声权重
    _SPECIAL_TOKENS = ("<s>", "<pad>", "</s>", "<unk>")

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

        self._session: Any = None
        self._tokenizer: Any = None
        self._sparse_w: Any = None
        self._sparse_b: Any = None
        self._excluded_tokens: set[int] = set()
        self._load_lock = threading.Lock()

    @property
    def name(self) -> str:
        return f"local:{self._model_path}"

    def _ensure_loaded(self) -> None:
        if self._session is not None:
            return
        with self._load_lock:
            # 双重检查锁定：mypy 只看到单线程路径，这里确实可能被其他线程赋值
            if self._session is not None:
                return  # type: ignore[unreachable]
            import onnxruntime as ort
            from tokenizers import Tokenizer

            model_dir = Path(self._model_path)
            logger.info("载入本地向量模型（ONNX）：%s", model_dir)

            self._session = ort.InferenceSession(
                str(model_dir / "onnx" / "model.onnx"),
                providers=["CPUExecutionProvider"],
            )
            self._tokenizer = Tokenizer.from_file(str(model_dir / "tokenizer.json"))

            # 读取稀疏线性层权重（torch zip 格式，不依赖 torch）
            with zipfile.ZipFile(str(model_dir / "sparse_linear.pt")) as zf:
                self._sparse_w = np.frombuffer(
                    zf.read("sparse_linear/data/0"), dtype=np.float16
                ).astype(np.float32).reshape(1, 1024)
                self._sparse_b = np.frombuffer(
                    zf.read("sparse_linear/data/1"), dtype=np.float16
                ).astype(np.float32).reshape(1)

            for name in self._SPECIAL_TOKENS:
                tid = self._tokenizer.token_to_id(name)
                if tid is not None:
                    self._excluded_tokens.add(tid)

            logger.info(
                "本地向量模型载入完成（词表 %d）", self._tokenizer.get_vocab_size()
            )

    def _encode_sync(self, texts: list[str]) -> list[Embedding]:
        self._ensure_loaded()

        encodings = self._tokenizer.encode_batch(texts)
        batch_ids = [e.ids[: self._max_length] for e in encodings]
        max_len = max(len(ids) for ids in batch_ids)

        input_ids = np.array(
            [ids + [0] * (max_len - len(ids)) for ids in batch_ids], dtype=np.int64
        )
        attention_mask = np.array(
            [[1] * len(ids) + [0] * (max_len - len(ids)) for ids in batch_ids],
            dtype=np.int64,
        )

        dense, token_emb = self._session.run(
            ["sentence_embedding", "token_embeddings"],
            {"input_ids": input_ids, "attention_mask": attention_mask},
        )
        dense_norm = l2_normalize(np.asarray(dense, dtype=np.float32))

        # 稀疏权重：relu(token_embeddings @ W.T + b)，按 token_id 取 max
        scores = np.maximum(
            np.asarray(token_emb, dtype=np.float32) @ self._sparse_w.T + self._sparse_b,
            0.0,
        )

        results: list[Embedding] = []
        for i, ids in enumerate(batch_ids):
            sparse: dict[int, float] = {}
            for tid, score in zip(ids, scores[i].ravel(), strict=True):
                if tid in self._excluded_tokens:
                    continue
                if score > 0:
                    sparse[tid] = max(sparse.get(tid, 0.0), float(score))
            results.append(
                Embedding(
                    dense=dense_norm[i].tolist(),
                    sparse=to_milvus_sparse(sparse, top_k=self._sparse_top_k),
                )
            )
        return results

    async def embed(self, texts: Sequence[str]) -> list[Embedding]:
        if not texts:
            return []
        # 推理是 CPU 密集操作，放到线程池，避免阻塞事件循环
        return await asyncio.to_thread(self._encode_sync, list(texts))

    async def aclose(self) -> None:
        self._session = None
        self._tokenizer = None
        self._sparse_w = None
        self._sparse_b = None


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
