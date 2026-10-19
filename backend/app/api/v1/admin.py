"""管理端路由：账号与机构、系统与模型配置、审计。

对应 04 文档 12.9（账号与机构）+ 12.10（系统与模型配置）+ 12.11（审计）。
"""
from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentKbAdmin, CurrentOrgAdmin
from app.common.database import get_db
from app.schemas.common import ApiResponse
from app.services import admin_service

router = APIRouter(prefix="/api/v1/admin", tags=["账号与机构"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


# ---- 请求体 ---------------------------------------------------------------


class UserCreate(BaseModel):
    account: str = Field(..., min_length=4, max_length=64)
    real_name: str = Field(...)
    role: str = Field(...)
    title: str | None = None
    dept_code: str | None = None
    initial_password: str = Field(..., min_length=8)
    remark: str | None = None


class UserUpdate(BaseModel):
    real_name: str | None = None
    title: str | None = None
    dept_code: str | None = None
    remark: str | None = None


class DeptCreate(BaseModel):
    dept_code: str = Field(...)
    dept_name: str = Field(...)
    sub_specialty: list[str] | None = None
    common_complaints: list[str] | None = None
    parent_code: str | None = None
    sort_no: int = 0


class DeptUpdate(BaseModel):
    dept_name: str | None = None
    sub_specialty: list[str] | None = None
    common_complaints: list[str] | None = None
    parent_code: str | None = None
    sort_no: int | None = None


class OrgUpdate(BaseModel):
    tenant_name: str | None = None
    hospital_level: str | None = None
    contact_person: str | None = None
    contact_phone: str | None = None


class ConfigUpdate(BaseModel):
    config_value: str = Field(...)


class ModelProviderCreate(BaseModel):
    provider_code: str = Field(...)
    provider_type: str = Field(...)
    provider_name: str | None = None
    base_url: str = Field(...)
    model_name: str | None = None
    api_key_enc: str | None = None
    is_on_prem: bool = False
    timeout_seconds: int = 60
    extra_json: dict | None = None


class ModelProviderUpdate(BaseModel):
    provider_name: str | None = None
    base_url: str | None = None
    model_name: str | None = None
    api_key_enc: str | None = None
    timeout_seconds: int | None = None
    extra_json: dict | None = None


# ---- 用户（ORG_ADMIN） -----------------------------------------------------


@router.get("/users", response_model=ApiResponse[dict])
async def list_users(
    db: DbSession,
    admin: CurrentOrgAdmin,
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    role: str | None = None,
    dept_code: str | None = None,
    status: str | None = None,
    keyword: str | None = None,
) -> ApiResponse[dict]:
    data = await admin_service.list_users(
        db, tenant_id=admin["tenant_id"], page=page, size=size,
        role=role, dept_code=dept_code, status=status, keyword=keyword,
    )
    return ApiResponse(data=data)


@router.post("/users", response_model=ApiResponse[dict])
async def create_user(
    req: UserCreate, db: DbSession, admin: CurrentOrgAdmin
) -> ApiResponse[dict]:
    data = await admin_service.create_user(
        db, tenant_id=admin["tenant_id"], actor_id=admin["sub"],
        actor_role=admin["role"], payload=req.model_dump(exclude_none=True),
    )
    return ApiResponse(data=data, message="创建成功")


@router.put("/users/{user_id}", response_model=ApiResponse[dict])
async def update_user(
    user_id: str, req: UserUpdate, db: DbSession, admin: CurrentOrgAdmin
) -> ApiResponse[dict]:
    data = await admin_service.update_user(
        db, tenant_id=admin["tenant_id"], actor_id=admin["sub"],
        actor_role=admin["role"], user_id=user_id, payload=req.model_dump(exclude_none=True),
    )
    return ApiResponse(data=data, message="修改成功")


@router.post("/users/{user_id}/toggle", response_model=ApiResponse[dict])
async def toggle_user(user_id: str, db: DbSession, admin: CurrentOrgAdmin) -> ApiResponse[dict]:
    data = await admin_service.toggle_user(
        db, tenant_id=admin["tenant_id"], actor_id=admin["sub"],
        actor_role=admin["role"], user_id=user_id,
    )
    return ApiResponse(data=data)


# ---- 患者（普通用户，ORG_ADMIN） -------------------------------------------


@router.get("/patients", response_model=ApiResponse[dict])
async def list_patients(
    db: DbSession,
    admin: CurrentOrgAdmin,
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    status: str | None = None,
    registered: bool | None = None,
    keyword: str | None = None,
) -> ApiResponse[dict]:
    """普通用户（患者）列表：账号、状态、问诊/预约次数。"""
    data = await admin_service.list_patients(
        db,
        tenant_id=admin["tenant_id"],
        page=page,
        size=size,
        status=status,
        registered=registered,
        keyword=keyword,
    )
    return ApiResponse(data=data)


@router.post("/patients/{patient_id}/toggle", response_model=ApiResponse[dict])
async def toggle_patient(
    patient_id: str, db: DbSession, admin: CurrentOrgAdmin
) -> ApiResponse[dict]:
    """启用/停用患者账号；停用后无法登录，历史数据保留。"""
    data = await admin_service.toggle_patient(
        db,
        tenant_id=admin["tenant_id"],
        actor_id=admin["sub"],
        actor_role=admin["role"],
        patient_id=patient_id,
    )
    return ApiResponse(data=data)


# ---- 科室（ORG_ADMIN） -----------------------------------------------------


@router.get("/depts", response_model=ApiResponse[dict])
async def list_depts(
    db: DbSession, admin: CurrentOrgAdmin,
    status: str | None = None, keyword: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=500),  # 科室下拉需要一次拉全量
) -> ApiResponse[dict]:
    data = await admin_service.list_depts(
        db, tenant_id=admin["tenant_id"], status=status, keyword=keyword, page=page, size=size
    )
    return ApiResponse(data=data)


@router.post("/depts", response_model=ApiResponse[dict])
async def create_dept(
    req: DeptCreate, db: DbSession, admin: CurrentOrgAdmin
) -> ApiResponse[dict]:
    data = await admin_service.create_dept(
        db, tenant_id=admin["tenant_id"], actor_id=admin["sub"],
        actor_role=admin["role"], payload=req.model_dump(exclude_none=True),
    )
    return ApiResponse(data=data, message="新增成功")


@router.put("/depts/{dept_id}", response_model=ApiResponse[dict])
async def update_dept(
    dept_id: str, req: DeptUpdate, db: DbSession, admin: CurrentOrgAdmin
) -> ApiResponse[dict]:
    data = await admin_service.update_dept(
        db, tenant_id=admin["tenant_id"], actor_id=admin["sub"],
        actor_role=admin["role"], dept_id=dept_id, payload=req.model_dump(exclude_none=True),
    )
    return ApiResponse(data=data, message="修改成功")


@router.post("/depts/{dept_id}/toggle", response_model=ApiResponse[dict])
async def toggle_dept(dept_id: str, db: DbSession, admin: CurrentOrgAdmin) -> ApiResponse[dict]:
    data = await admin_service.toggle_dept(
        db, tenant_id=admin["tenant_id"], actor_id=admin["sub"],
        actor_role=admin["role"], dept_id=dept_id,
    )
    return ApiResponse(data=data)


# ---- 机构信息与系统配置（ORG_ADMIN） ---------------------------------------


@router.get("/org", response_model=ApiResponse[dict])
async def get_org(db: DbSession, admin: CurrentOrgAdmin) -> ApiResponse[dict]:
    data = await admin_service.get_org(db, tenant_id=admin["tenant_id"])
    return ApiResponse(data=data)


@router.put("/org", response_model=ApiResponse[dict])
async def update_org(
    req: OrgUpdate, db: DbSession, admin: CurrentOrgAdmin
) -> ApiResponse[dict]:
    data = await admin_service.update_org(
        db, tenant_id=admin["tenant_id"], actor_id=admin["sub"],
        actor_role=admin["role"], payload=req.model_dump(exclude_none=True),
    )
    return ApiResponse(data=data, message="修改成功")


@router.get("/configs", response_model=ApiResponse[dict])
async def list_configs(db: DbSession, admin: CurrentOrgAdmin) -> ApiResponse[dict]:
    data = await admin_service.list_configs(db, tenant_id=admin["tenant_id"])
    return ApiResponse(data=data)


@router.put("/configs/{config_key}", response_model=ApiResponse[dict])
async def update_config(
    config_key: str, req: ConfigUpdate, db: DbSession, admin: CurrentOrgAdmin
) -> ApiResponse[dict]:
    data = await admin_service.update_config(
        db, tenant_id=admin["tenant_id"], actor_id=admin["sub"],
        actor_role=admin["role"], config_key=config_key, config_value=req.config_value,
    )
    return ApiResponse(data=data, message="修改成功")


# ---- 模型配置（KB_ADMIN / ORG_ADMIN） -------------------------------------


@router.get("/model-providers", response_model=ApiResponse[dict])
async def list_model_providers(db: DbSession, admin: CurrentKbAdmin) -> ApiResponse[dict]:
    data = await admin_service.list_model_providers(db, tenant_id=admin["tenant_id"])
    return ApiResponse(data=data)


@router.post("/model-providers", response_model=ApiResponse[dict])
async def create_model_provider(
    req: ModelProviderCreate, db: DbSession, admin: CurrentKbAdmin
) -> ApiResponse[dict]:
    data = await admin_service.create_model_provider(
        db, tenant_id=admin["tenant_id"], actor_id=admin["sub"],
        payload=req.model_dump(exclude_none=True),
    )
    return ApiResponse(data=data, message="新增成功")


@router.put("/model-providers/{provider_id}", response_model=ApiResponse[dict])
async def update_model_provider(
    provider_id: str, req: ModelProviderUpdate, db: DbSession, admin: CurrentKbAdmin
) -> ApiResponse[dict]:
    data = await admin_service.update_model_provider(
        db, tenant_id=admin["tenant_id"], actor_id=admin["sub"],
        provider_id=provider_id, payload=req.model_dump(exclude_none=True),
    )
    return ApiResponse(data=data, message="修改成功")


@router.post("/model-providers/{provider_id}/default", response_model=ApiResponse[dict])
async def set_default_model_provider(
    provider_id: str, db: DbSession, admin: CurrentKbAdmin
) -> ApiResponse[dict]:
    data = await admin_service.set_default_model_provider(
        db, tenant_id=admin["tenant_id"], actor_id=admin["sub"], provider_id=provider_id
    )
    return ApiResponse(data=data, message="已设为默认")


# ---- 审计日志（KB_ADMIN / ORG_ADMIN） -------------------------------------


@router.get("/audit-logs", response_model=ApiResponse[dict])
async def list_audit_logs(
    db: DbSession,
    admin: CurrentKbAdmin,
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    action_type: str | None = None,
    actor_id: str | None = None,
    target_type: str | None = None,
) -> ApiResponse[dict]:
    data = await admin_service.list_audit_logs(
        db, tenant_id=admin["tenant_id"], page=page, size=size,
        action_type=action_type, actor_id=actor_id, target_type=target_type,
    )
    return ApiResponse(data=data)


# ---------------- 知识图谱 ----------------
# Neo4j 驱动是同步的，放线程池执行，避免阻塞事件循环


@router.get("/kg/stats", response_model=ApiResponse[dict])
async def kg_stats(admin: CurrentKbAdmin) -> ApiResponse[dict]:
    """知识图谱规模（各类节点数 / 关系数）。"""
    from app.services.kg_service import get_kg

    data = await asyncio.to_thread(get_kg().stats)
    return ApiResponse(data=data)


@router.get("/kg/symptoms", response_model=ApiResponse[dict])
async def kg_symptoms(admin: CurrentKbAdmin) -> ApiResponse[dict]:
    """图谱中的标准症状名（供前端选择/提示）。"""
    from app.services.kg_service import get_kg

    items = await asyncio.to_thread(get_kg().symptom_names)
    return ApiResponse(data={"items": items})


@router.get("/kg/network", response_model=ApiResponse[dict])
async def kg_network(
    admin: CurrentKbAdmin,
    symptom: str = Query(..., min_length=1, description="标准症状名"),
    limit: int = Query(30, ge=5, le=200),
) -> ApiResponse[dict]:
    """症状 → 疾病 → 科室 的推理子图（nodes + edges）。"""
    from app.services.kg_service import get_kg

    data = await asyncio.to_thread(get_kg().network, symptom, limit)
    return ApiResponse(data=data)


@router.get("/kg/dept-network", response_model=ApiResponse[dict])
async def kg_dept_network(
    admin: CurrentKbAdmin,
    dept_code: str = Query(..., min_length=1, description="科室编码"),
    limit: int = Query(30, ge=5, le=100),
) -> ApiResponse[dict]:
    """科室 → 疾病 → 症状 的反向子图（科室视角）。"""
    from app.services.kg_service import get_kg

    data = await asyncio.to_thread(get_kg().dept_network, dept_code, limit)
    return ApiResponse(data=data)
