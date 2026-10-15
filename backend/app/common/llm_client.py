"""统一的模型调用客户端。

三类能力分别对接不同的后端，互不影响：

| 能力 | 开发期后端 | 交付期后端 | 说明 |
|---|---|---|---|
| 内容生成 | 云端 API（Qwen2.5-32B） | 本地推理服务 | 必须提供 OpenAI 兼容接口 |
| 向量化 | **本地 BGE-M3** | 本地服务化部署 | 只有本地能同时产出稠密 + 稀疏向量 |
| 精排 | 云端 API | 本地服务化部署 | 需要 query 与文档拼接计算 |

业务代码只依赖本模块，切换后端只改配置。

每次**对外**调用前都会经过出域守卫——本地推理不产生网络请求，无需检查。
"""

from __future__ import annotations

import logging
from typing import Any, Sequence

import httpx
from openai import AsyncOpenAI

from app.common.egress_guard import EgressGuard
from app.common.embedder import BaseEmbedder, Embedding, build_embedder
from app.config import Settings

logger = logging.getLogger(__name__)

_PLACEHOLDER_KEY = "not-needed"  # 内网服务通常不做鉴权，SDK 要求非空


def _log_egress(capability: str, host: str) -> None:
    """出域留痕。

    开发形态下每次放行都必须可追溯（`NFR70` 四项约束之一）。
    当前落在日志；服务层就绪后应替换为写入 `mg_audit_log`
    （`action_type='EGRESS_DEV'`）的回调。
    """
    logger.warning(
        "开发形态出域放行：能力=%s 目标=%s（已按合成数据处理）", capability, host
    )


class ModelClient:
    """内容生成、向量化、精排的统一入口。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._guard = EgressGuard(settings.egress_policy, on_egress=_log_egress)

        self._llm = AsyncOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key or _PLACEHOLDER_KEY,
            timeout=settings.llm_timeout_seconds,
        )
        self._embedder: BaseEmbedder = build_embedder(settings)
        self._http = httpx.AsyncClient(timeout=settings.llm_timeout_seconds)

    @property
    def embedder(self) -> BaseEmbedder:
        return self._embedder

    def _resolve_synthetic(self, is_synthetic: bool | None) -> bool:
        """解析本次调用的合成数据标记。

        `dev_sandbox` 形态已通过启动校验声明「只使用合成数据」（`NFR70` 四项约束之一），
        因此默认按合成数据处理，避免开发期每处调用都要显式传参而遗漏。

        若确认本次调用**包含真实患者数据**，调用方必须显式传 `is_synthetic=False`——
        此时守卫会拒绝出域。这个显式入口是给"误接真实数据"准备的最后一道闸。
        """
        if is_synthetic is not None:
            return is_synthetic
        return self._guard.is_sandbox

    # ---------------- 内容生成 ----------------

    async def chat(
        self,
        messages: Sequence[dict[str, str]],
        *,
        small: bool = False,
        temperature: float = 0.2,
        json_schema: dict[str, Any] | None = None,
        capability: str = "llm_chat",
        is_synthetic: bool | None = None,
    ) -> str:
        """发起一次对话补全。

        small=True 时使用轻量模型（意图识别、信息项抽取等），降低成本与延迟。
        json_schema 不为空时要求结构化输出；不同后端支持程度不同，
        调用方必须对返回值做校验，不能假定一定符合结构。

        `is_synthetic` 解析规则见 `_resolve_synthetic`；确认本次调用含真实
        患者数据时显式传 False，守卫将拒绝出域。
        """
        self._guard.check(
            capability,
            self._settings.llm_base_url,
            is_synthetic=self._resolve_synthetic(is_synthetic),
        )

        model = self._settings.small_llm_model if small else self._settings.llm_model
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": list(messages),
            "temperature": temperature,
        }
        if json_schema is not None:
            kwargs["response_format"] = {"type": "json_schema", "json_schema": json_schema}

        response = await self._llm.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""

    # ---------------- 向量化 ----------------

    async def embed(
        self,
        texts: Sequence[str],
        *,
        capability: str = "llm_embed",
        is_synthetic: bool | None = None,
    ) -> list[Embedding]:
        """批量向量化，返回顺序与入参一致。

        本地后端产出稠密 + 稀疏；云端后端只产出稠密。
        调用方应通过 `self.embedder.supports_sparse` 判断后决定入库策略。
        """
        if not texts:
            return []

        # 仅云端后端需要出域检查；本地推理不产生网络请求
        if not self._settings.embedding_is_local:
            self._guard.check(
                capability,
                self._settings.effective_embedding_base_url,
                is_synthetic=self._resolve_synthetic(is_synthetic),
            )

        return await self._embedder.embed(texts)

    async def embed_dense(
        self,
        texts: Sequence[str],
        *,
        capability: str = "llm_embed",
        is_synthetic: bool | None = None,
    ) -> list[list[float]]:
        """只取稠密向量。用于不关心稀疏向量的场景。"""
        return [
            item.dense
            for item in await self.embed(
                texts, capability=capability, is_synthetic=is_synthetic
            )
        ]

    # ---------------- 精排 ----------------

    async def rerank(
        self,
        query: str,
        documents: Sequence[str],
        *,
        top_n: int | None = None,
        capability: str = "rerank",
        is_synthetic: bool | None = None,
    ) -> list[tuple[int, float]]:
        """对候选文档重排，返回 (原始下标, 相关度)，按相关度降序。

        精排接口不在 OpenAI 规范内，各家返回格式不一，此处按主流实现解析，
        解析失败时抛异常而非静默返回空。
        """
        if not documents or not self._settings.rerank_enabled:
            return []

        base_url = self._settings.effective_rerank_base_url
        self._guard.check(
            capability, base_url, is_synthetic=self._resolve_synthetic(is_synthetic)
        )

        limit = top_n or self._settings.rerank_candidates
        payload = {
            "model": self._settings.rerank_model,
            "query": query,
            "documents": list(documents),
            "top_n": min(limit, len(documents)),
        }
        headers = {"Authorization": f"Bearer {self._settings.effective_rerank_api_key}"}

        response = await self._http.post(f"{base_url.rstrip('/')}/rerank", json=payload, headers=headers)
        response.raise_for_status()
        body = response.json()

        results = body.get("results") or body.get("data")
        if not isinstance(results, list):
            raise ValueError(f"精排接口返回格式无法解析：{str(body)[:200]}")

        hits: list[tuple[int, float]] = []
        for item in results:
            index = item.get("index")
            score = item.get("relevance_score", item.get("score"))
            if isinstance(index, int) and isinstance(score, (int, float)):
                hits.append((index, float(score)))
        hits.sort(key=lambda x: x[1], reverse=True)
        return hits

    # ---------------- 资源释放 ----------------

    async def aclose(self) -> None:
        await self._llm.close()
        await self._embedder.aclose()
        await self._http.aclose()
