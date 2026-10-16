"""知识库管理与检索验证路由。

对应 04 文档 12.7（知识库管理）+ 12.8（检索验证）。
权限：KB_ADMIN / ORG_ADMIN。
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentKbAdmin
from app.common.database import get_db
from app.schemas.common import ApiResponse
from app.services import kb_service

router = APIRouter(prefix="/api/v1/admin/kb", tags=["知识库管理"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


class EntryCreate(BaseModel):
    entry_code: str = Field(..., max_length=128)
    kb_type: str = Field(...)
    title: str | None = Field(None, max_length=255)
    content: str = Field(...)
    content_json: dict | None = None
    dept_code: str | None = None
    icd10_codes: list[str] | None = None
    age_group: str | None = "all"
    gender: str | None = "0"
    source: str | None = None
    entry_version: str | None = None


class EntryUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    content_json: dict | None = None
    dept_code: str | None = None
    icd10_codes: list[str] | None = None
    age_group: str | None = None
    gender: str | None = None
    source: str | None = None
    entry_version: str | None = None


class RetrievalTest(BaseModel):
    query: str = Field(..., min_length=1, description="查询文本（模拟患者主诉）")
    mode: str = Field("DENSE", description="检索模式：DENSE / SPARSE / HYBRID")
    limit: int = Field(10, ge=1, le=50)


class GoldenQueryCreate(BaseModel):
    query_text: str = Field(...)
    query_code: str | None = None
    expect_depts: list[str] | None = None
    expect_not_depts: list[str] | None = None
    expect_route: str | None = None
    category: str | None = None
    description: str | None = None


class PublishRequest(BaseModel):
    version_tag: str | None = None


@router.get("/entries", response_model=ApiResponse[dict])
async def list_entries(
    db: DbSession,
    admin: CurrentKbAdmin,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    kb_type: str | None = None,
    dept_code: str | None = None,
    status: str | None = None,
    is_active: bool | None = None,
    keyword: str | None = None,
    sort_by: str = "update_time",
    sort_order: str = "desc",
) -> ApiResponse[dict]:
    data = await kb_service.list_entries(
        db, tenant_id=admin["tenant_id"], page=page, size=size, kb_type=kb_type,
        dept_code=dept_code, status=status, is_active=is_active, keyword=keyword,
        sort_by=sort_by, sort_order=sort_order,
    )
    return ApiResponse(data=data)


@router.post("/entries", response_model=ApiResponse[dict])
async def create_entry(
    req: EntryCreate, db: DbSession, admin: CurrentKbAdmin
) -> ApiResponse[dict]:
    data = await kb_service.create_entry(
        db, tenant_id=admin["tenant_id"], actor_id=admin["sub"],
        actor_role=admin["role"], payload=req.model_dump(exclude_none=True),
    )
    return ApiResponse(data=data, message="新增成功")


@router.get("/entries/{entry_id}", response_model=ApiResponse[dict])
async def get_entry(entry_id: str, db: DbSession, admin: CurrentKbAdmin) -> ApiResponse[dict]:
    data = await kb_service.get_entry(db, tenant_id=admin["tenant_id"], entry_id=entry_id)
    return ApiResponse(data=data)


@router.put("/entries/{entry_id}", response_model=ApiResponse[dict])
async def update_entry(
    entry_id: str, req: EntryUpdate, db: DbSession, admin: CurrentKbAdmin
) -> ApiResponse[dict]:
    data = await kb_service.update_entry(
        db, tenant_id=admin["tenant_id"], actor_id=admin["sub"],
        actor_role=admin["role"], entry_id=entry_id, payload=req.model_dump(exclude_none=True),
    )
    return ApiResponse(data=data, message="修改成功")


@router.post("/entries/{entry_id}/toggle", response_model=ApiResponse[dict])
async def toggle_entry(entry_id: str, db: DbSession, admin: CurrentKbAdmin) -> ApiResponse[dict]:
    data = await kb_service.toggle_entry(
        db, tenant_id=admin["tenant_id"], actor_id=admin["sub"],
        actor_role=admin["role"], entry_id=entry_id,
    )
    return ApiResponse(data=data)


@router.get("/entries/{entry_id}/history", response_model=ApiResponse[dict])
async def list_entry_history(
    entry_id: str,
    db: DbSession,
    admin: CurrentKbAdmin,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
) -> ApiResponse[dict]:
    data = await kb_service.list_entry_history(
        db, tenant_id=admin["tenant_id"], entry_id=entry_id, page=page, size=size
    )
    return ApiResponse(data=data)


@router.post("/retrieval-test", response_model=ApiResponse[dict])
async def retrieval_test(
    req: RetrievalTest, db: DbSession, admin: CurrentKbAdmin, request: Request
) -> ApiResponse[dict]:
    data = await kb_service.retrieval_test(
        db,
        tenant_id=admin["tenant_id"],
        query=req.query,
        mode=req.mode,
        embedder=request.app.state.model_client.embedder,
        store=request.app.state.milvus_store,
        limit=req.limit,
    )
    return ApiResponse(data=data)


@router.get("/golden-queries", response_model=ApiResponse[dict])
async def list_golden_queries(
    db: DbSession,
    admin: CurrentKbAdmin,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    category: str | None = None,
    is_active: bool | None = None,
) -> ApiResponse[dict]:
    data = await kb_service.list_golden_queries(
        db, tenant_id=admin["tenant_id"], page=page, size=size,
        category=category, is_active=is_active,
    )
    return ApiResponse(data=data)


@router.post("/golden-queries", response_model=ApiResponse[dict])
async def create_golden_query(
    req: GoldenQueryCreate, db: DbSession, admin: CurrentKbAdmin
) -> ApiResponse[dict]:
    data = await kb_service.create_golden_query(
        db, tenant_id=admin["tenant_id"], actor_id=admin["sub"],
        payload=req.model_dump(exclude_none=True),
    )
    return ApiResponse(data=data, message="新增成功")


@router.post("/publish", response_model=ApiResponse[dict])
async def publish_kb(
    req: PublishRequest, db: DbSession, admin: CurrentKbAdmin
) -> ApiResponse[dict]:
    data = await kb_service.publish_kb(
        db, tenant_id=admin["tenant_id"], actor_id=admin["sub"], version_tag=req.version_tag
    )
    return ApiResponse(data=data, message="发布成功")


@router.get("/publishes", response_model=ApiResponse[dict])
async def list_publishes(
    db: DbSession, admin: CurrentKbAdmin,
    page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
) -> ApiResponse[dict]:
    data = await kb_service.list_publishes(db, tenant_id=admin["tenant_id"], page=page, size=size)
    return ApiResponse(data=data)


@router.post("/ingest", response_model=ApiResponse[dict])
async def trigger_ingest(db: DbSession, admin: CurrentKbAdmin) -> ApiResponse[dict]:
    data = await kb_service.trigger_ingest(
        db, tenant_id=admin["tenant_id"], actor_id=admin["sub"]
    )
    return ApiResponse(data=data, message="入库任务已创建")


@router.get("/ingest-tasks", response_model=ApiResponse[dict])
async def list_ingest_tasks(
    db: DbSession, admin: CurrentKbAdmin,
    page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
) -> ApiResponse[dict]:
    data = await kb_service.list_ingest_tasks(db, tenant_id=admin["tenant_id"], page=page, size=size)
    return ApiResponse(data=data)


@router.get("/ingest-tasks/{task_id}", response_model=ApiResponse[dict])
async def get_ingest_task(task_id: str, db: DbSession, admin: CurrentKbAdmin) -> ApiResponse[dict]:
    data = await kb_service.get_ingest_task(db, tenant_id=admin["tenant_id"], task_id=task_id)
    return ApiResponse(data=data)
