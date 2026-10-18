"""应用入口：组装中间件、路由、生命周期与探针。

启动期只做「必须成功」的初始化（模型客户端、向量库、编排器）；
依赖不可用时宁可起不来，也不要带病运行（与《02 架构》一致）。

探针分两个：
- ``/healthz`` 存活探针：只回答进程是否活着，不访问外部依赖
- ``/readyz``  就绪探针：检查 PostgreSQL 与 Milvus，任一不可用返回 503
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.staticfiles import StaticFiles

from app.api import ws as ws_router
from app.api.v1 import api_v1_router
from app.common.database import ping_database
from app.common.egress_guard import (
    ABSOLUTE_PII_CAPABILITIES,
    PATIENT_PIPELINE_CAPABILITIES,
    DataResidencyViolation,
    EgressGuard,
    is_private_host,
)
from app.common.exceptions import register_exception_handlers
from app.common.llm_client import ModelClient
from app.config import settings
from app.middleware.request_context import RequestContextMiddleware
from app.retrieval import MilvusStore
from app.services.orchestration import init_orchestrator

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
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
    # 构建分诊编排器（LangGraph 图 + 多轮状态管理）
    app.state.orchestrator = init_orchestrator(_client, _client.embedder, milvus_store)
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


# docs_url=None 禁用默认 /docs（其模板引用 jsdelivr CDN，国内不可达会白屏），
# 由下方自定义路由用本地静态资源接管
app = FastAPI(title="MedicalGuidance", version="0.1.0", lifespan=lifespan, docs_url=None)

# 中间件：请求上下文（trace/访问日志/安全头）+ CORS。
# 后添加的在外层：CORS 包住请求上下文，异常响应也能拿到跨域头。
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Trace-ID"],
)

# Swagger UI 静态资源本地托管：不依赖公网 CDN（内网/私有化部署同样可用）
_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    """用本地静态资源渲染 Swagger UI。"""
    return get_swagger_ui_html(
        openapi_url=app.openapi_url or "/openapi.json",
        title=app.title + " - Swagger UI",
        swagger_js_url="/static/swagger-ui/swagger-ui-bundle.js",
        swagger_css_url="/static/swagger-ui/swagger-ui.css",
    )


# 全局异常处理器（业务错误 → 统一响应）+ 业务路由 + WebSocket
register_exception_handlers(app)
app.include_router(api_v1_router)
app.include_router(ws_router.router)


def _require_debug() -> None:
    if not settings.debug_endpoints:
        raise HTTPException(status_code=404, detail="Not Found")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    """存活探针。只回答进程是否活着，不访问任何外部依赖。"""
    return {
        "status": "ok",
        "deploy_mode": settings.deploy_mode,
        "egress_policy": settings.egress_policy.value,
    }


@app.get("/readyz")
async def readyz(response: Response) -> dict[str, object]:
    """就绪探针。PostgreSQL 或 Milvus 不可用时返回 503，供网关摘流量。"""
    checks: dict[str, str] = {}

    async def _check_db() -> None:
        await asyncio.wait_for(ping_database(), timeout=2.0)

    async def _check_milvus() -> None:
        store: MilvusStore | None = getattr(app.state, "milvus_store", None)
        if store is None:
            raise RuntimeError("向量库未初始化")
        await asyncio.wait_for(asyncio.to_thread(store.ping), timeout=2.0)

    results = await asyncio.gather(
        _check_db(), _check_milvus(), return_exceptions=True
    )
    for name, result in zip(("postgres", "milvus"), results, strict=True):
        checks[name] = (
            "ok" if not isinstance(result, BaseException) else type(result).__name__
        )

    ok = all(value == "ok" for value in checks.values())
    if not ok:
        response.status_code = 503
    return {"status": "ok" if ok else "degraded", "checks": checks}


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
            "dim": len(vectors[0].dense) if vectors else 0,
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
