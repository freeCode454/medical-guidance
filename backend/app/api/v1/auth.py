"""认证路由：患者匿名会话创建、院内用户登录。

对应 04 文档 12.1.1 / 12.1.4。
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.database import get_db
from app.schemas.auth import (
    PatientSessionCreateRequest,
    PatientSessionCreateResponse,
    StaffLoginRequest,
    StaffLoginResponse,
    StaffRefreshRequest,
)
from app.schemas.common import ApiResponse
from app.services import auth_service

router = APIRouter(prefix="/api/v1/auth", tags=["认证"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.post("/patient/session", response_model=ApiResponse[PatientSessionCreateResponse])
async def create_patient_session(
    req: PatientSessionCreateRequest, db: DbSession
) -> ApiResponse[PatientSessionCreateResponse]:
    """创建匿名患者会话并签发令牌（公开接口，不采集身份信息）。"""
    data = await auth_service.create_patient_session(
        db, req.device_id, req.client_type, req.channel
    )
    return ApiResponse(data=data)


@router.post("/staff/login", response_model=ApiResponse[StaffLoginResponse])
async def staff_login(
    req: StaffLoginRequest, db: DbSession
) -> ApiResponse[StaffLoginResponse]:
    """院内用户（医生/管理员）账号口令登录。"""
    data = await auth_service.staff_login(db, req.account, req.password, req.client_type)
    return ApiResponse(data=data, message="登录成功")


@router.post("/staff/refresh", response_model=ApiResponse[StaffLoginResponse])
async def staff_refresh(
    req: StaffRefreshRequest, db: DbSession
) -> ApiResponse[StaffLoginResponse]:
    """用刷新令牌续期（令牌轮换：同时返回新的 access / refresh）。"""
    data = await auth_service.refresh_staff_session(db, req.refresh_token)
    return ApiResponse(data=data, message="续期成功")
