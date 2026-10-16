"""最小可运行后端。

当前只提供健康检查与自检接口，用于在开始业务开发前确认三件事：

1. 配置是否正确加载（切换后端靠的就是配置）
2. 云端 API 是否连通（开发期唯一可用的推理路径）
3. 出域守卫是否生效（数据安全的代码级兜底）

业务接口后续按需求文档 `F01` 起逐步补充。
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from app.common.egress_guard import (
    ABSOLUTE_PII_CAPABILITIES,
    PATIENT_PIPELINE_CAPABILITIES,
    DataResidencyViolation,
    EgressGuard,
    is_private_host,
)
from app.common.llm_client import ModelClient
from app.api.v1 import api_v1_router
from app.common.exceptions import register_exception_handlers
from app.config import settings
from app.retrieval import MilvusStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("app")

_client: ModelClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _client
    _client = ModelClient(settings)
    milvus_store = MilvusStore(settings.milvus_uri)
    # 挂到 app.state，供接口与后台任务复用
    app.state.model_client = _client
    app.state.milvus_store = milvus_store
    logger.info(
        "启动完成 deploy_mode=%s egress_policy=%s llm=%s",
        settings.deploy_mode,
        settings.egress_policy.value,
        settings.llm_model,
    )
    yield
    if _client is not None:
        await _client.aclose()
    _client = None
    milvus_store.close()


app = FastAPI(title="MedicalGuidance", version="0.1.0", lifespan=lifespan)

# 全局异常处理器（业务错误 → 统一响应）+ 业务路由
register_exception_handlers(app)
app.include_router(api_v1_router)


def _require_debug() -> None:
    if not settings.debug_endpoints:
        raise HTTPException(status_code=404, detail="Not Found")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    """健康检查。不含任何敏感信息，可用于探针。"""
    return {
        "status": "ok",
        "deploy_mode": settings.deploy_mode,
        "egress_policy": settings.egress_policy.value,
    }


@app.get("/debug/config")
async def debug_config() -> dict[str, object]:
    """查看当前生效的配置（凭证只显示末 4 位）。

    切换环境后先调这个接口确认地址是否真的换过去了，
    避免"改了配置但没生效"这类排查半天的问题。
    """
    _require_debug()

    def mask(value: str) -> str:
        if not value or value == "not-needed":
            return "(未配置)"
        return f"****{value[-4:]}" if len(value) > 4 else "****"

    return {
        "deploy_mode": settings.deploy_mode,
        "egress_policy": settings.egress_policy.value,
        "llm": {
            "base_url": settings.llm_base_url,
            "model": settings.llm_model,
            "small_model": settings.small_llm_model,
            "api_key": mask(settings.llm_api_key),
        },
        "embedding": {
            "base_url": settings.effective_embedding_base_url,
            "model": settings.embedding_model,
            "api_key": mask(settings.effective_embedding_api_key),
        },
        "storage": {
            "milvus_uri": settings.milvus_uri,
            "database_url": settings.database_url.split("@")[-1]
            if "@" in settings.database_url
            else settings.database_url,
        },
        "features": {
            "asr_enabled": settings.asr_enabled,
            "tracing_enabled": settings.tracing_enabled,
        },
    }


@app.get("/debug/llm")
async def debug_llm() -> dict[str, object]:
    """真实调用一次内容生成与向量化，确认云端 API 连通。"""
    _require_debug()
    if _client is None:
        raise HTTPException(status_code=503, detail="客户端未初始化")

    try:
        reply = await _client.chat(
            [{"role": "user", "content": "回复两个字：可用"}],
            small=True,
            capability="llm_chat",
        )
        vectors = await _client.embed(["腹痛三天"], capability="llm_embed")
    except DataResidencyViolation as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:  # 网络、鉴权、限流等
        raise HTTPException(
            status_code=502,
            detail=f"{type(exc).__name__}: {exc}",
        ) from exc

    return {
        "chat": {"model": settings.small_llm_model, "reply": reply},
        "embedding": {
            "model": settings.embedding_model,
            "dim": len(vectors[0]) if vectors else 0,
        },
    }


@app.get("/debug/egress")
async def debug_egress() -> dict[str, object]:
    """出域守卫自检：用几组地址验证守卫的判定是否符合预期。"""
    _require_debug()
    guard = EgressGuard(settings.egress_policy)

    cases = [
        ("llm_chat", "http://vllm-svc.intranet:8000/v1", False),
        ("llm_chat", "https://api.siliconflow.cn/v1", False),
        ("llm_chat", "https://api.siliconflow.cn/v1", True),
        ("emr_query", "http://his.intranet:8080", False),
        ("emr_query", "https://api.siliconflow.cn/v1", True),
        ("patient_profile", "https://example.com/v1", True),
        ("kb_build", "https://api.siliconflow.cn/v1", False),
    ]

    results = []
    for capability, url, synthetic in cases:
        try:
            guard.check(capability, url, is_synthetic=synthetic)
            decision, reason = "放行", None
        except DataResidencyViolation as exc:
            decision, reason = "拒绝", str(exc).split("\n")[0]
        item: dict[str, object] = {
            "capability": capability,
            "target": url,
            "is_synthetic": synthetic,
            "decision": decision,
        }
        if reason:
            item["reason"] = reason
        results.append(item)

    return {
        "policy": settings.egress_policy.value,
        "absolute_pii": sorted(ABSOLUTE_PII_CAPABILITIES),
        "patient_pipeline": sorted(PATIENT_PIPELINE_CAPABILITIES),
        "probe": results,
        "note": (
            "涉及患者原始数据的能力（absolute_pii）在任何策略、任何数据标记下都不得"
            "访问院外地址；患者链路能力仅在 dev_sandbox 且标记为合成数据时放行。"
        ),
    }


@app.get("/debug/net")
async def debug_net(host: str) -> dict[str, object]:
    """判断给定主机是否被识别为内网地址，用于排查地址配置。"""
    _require_debug()
    return {"host": host, "is_private": is_private_host(host)}
