"""医生端路由：接诊分诊与病历患者。

对应 04 文档 12.5（医生端·接诊分诊，9 接口）+ 12.6（医生端·病历患者，2 接口）。
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentDoctor
from app.common.database import get_db
from app.schemas.common import ApiResponse
from app.services import doctor_service

router = APIRouter(prefix="/api/v1/doctor", tags=["医生端"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


class ConfirmRequest(BaseModel):
    note: str | None = Field(None, max_length=200, description="确认备注")


class CorrectRequest(BaseModel):
    after_dept: str = Field(..., description="修正后的科室编码")
    reason: str = Field(..., min_length=10, description="修正理由，不少于 10 字")


@router.get("/encounters", response_model=ApiResponse[dict])
async def list_encounters(
    db: DbSession,
    doctor: CurrentDoctor,
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    status: str | None = None,
    encounter_date: str | None = None,
    sort_by: str = "started_time",
    sort_order: str = "desc",
) -> ApiResponse[dict]:
    """查询今日接诊列表（F14）。"""
    data = await doctor_service.list_encounters(
        db,
        doctor_id=doctor["sub"],
        tenant_id=doctor["tenant_id"],
        page=page,
        size=size,
        status=status,
        encounter_date=encounter_date,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return ApiResponse(data=data)


@router.get("/sessions/{session_id}", response_model=ApiResponse[dict])
async def get_session_detail(
    session_id: str, db: DbSession, doctor: CurrentDoctor
) -> ApiResponse[dict]:
    """查询会话详情（医生视图，F15）。"""
    data = await doctor_service.get_session_detail(
        db, session_id=session_id, doctor_id=doctor["sub"], tenant_id=doctor["tenant_id"]
    )
    return ApiResponse(data=data)


@router.get("/sessions/{session_id}/messages", response_model=ApiResponse[dict])
async def list_messages(
    session_id: str,
    db: DbSession,
    doctor: CurrentDoctor,
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=1, le=100),
    include_system: bool = True,
) -> ApiResponse[dict]:
    """查询完整对话记录（F20）。"""
    data = await doctor_service.list_messages(
        db,
        session_id=session_id,
        doctor_id=doctor["sub"],
        tenant_id=doctor["tenant_id"],
        page=page,
        size=size,
        include_system=include_system,
    )
    return ApiResponse(data=data)


@router.get("/sessions/{session_id}/emr", response_model=ApiResponse[dict])
async def get_emr(session_id: str, db: DbSession, doctor: CurrentDoctor) -> ApiResponse[dict]:
    """查询 SOAP 病历（医生视图，F16）。"""
    data = await doctor_service.get_emr(
        db, session_id=session_id, doctor_id=doctor["sub"], tenant_id=doctor["tenant_id"]
    )
    return ApiResponse(data=data)


@router.get("/sessions/{session_id}/diagnosis", response_model=ApiResponse[dict])
async def get_diagnosis(
    session_id: str,
    db: DbSession,
    doctor: CurrentDoctor,
    include_mdt: bool = True,
) -> ApiResponse[dict]:
    """查询鉴别诊断候选与依据 + 用药禁忌（F17、F47）。"""
    data = await doctor_service.get_diagnosis(
        db,
        session_id=session_id,
        doctor_id=doctor["sub"],
        tenant_id=doctor["tenant_id"],
        include_mdt=include_mdt,
    )
    return ApiResponse(data=data)


@router.post("/sessions/{session_id}/confirm", response_model=ApiResponse[dict])
async def confirm_triage(
    session_id: str, req: ConfirmRequest, db: DbSession, doctor: CurrentDoctor
) -> ApiResponse[dict]:
    """确认分诊建议（F18）。"""
    data = await doctor_service.confirm_triage(
        db,
        session_id=session_id,
        doctor_id=doctor["sub"],
        tenant_id=doctor["tenant_id"],
        note=req.note,
    )
    return ApiResponse(data=data, message="已确认分诊建议")


@router.post("/sessions/{session_id}/correct", response_model=ApiResponse[dict])
async def correct_triage(
    session_id: str, req: CorrectRequest, db: DbSession, doctor: CurrentDoctor
) -> ApiResponse[dict]:
    """修正分诊建议（F19）。"""
    data = await doctor_service.correct_triage(
        db,
        session_id=session_id,
        doctor_id=doctor["sub"],
        tenant_id=doctor["tenant_id"],
        after_dept=req.after_dept,
        reason=req.reason,
    )
    return ApiResponse(data=data, message="修正已记录")


@router.get("/takeover-queue", response_model=ApiResponse[dict])
async def list_takeover_queue(
    db: DbSession,
    doctor: CurrentDoctor,
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
) -> ApiResponse[dict]:
    """查询待接管队列（F21）。"""
    data = await doctor_service.list_takeover_queue(
        db, tenant_id=doctor["tenant_id"], page=page, size=size
    )
    return ApiResponse(data=data)


@router.post("/sessions/{session_id}/takeover", response_model=ApiResponse[dict])
async def takeover_session(
    session_id: str, db: DbSession, doctor: CurrentDoctor
) -> ApiResponse[dict]:
    """接管会话（F21）。"""
    data = await doctor_service.takeover_session(
        db, session_id=session_id, doctor_id=doctor["sub"], tenant_id=doctor["tenant_id"]
    )
    return ApiResponse(data=data, message="已接管会话")


@router.get("/patients/{patient_id}/emr", response_model=ApiResponse[dict])
async def get_patient_emr(
    patient_id: str, db: DbSession, doctor: CurrentDoctor
) -> ApiResponse[dict]:
    """查阅患者既往病历（F23）。"""
    data = await doctor_service.get_patient_emr(
        db, patient_id=patient_id, doctor_id=doctor["sub"], tenant_id=doctor["tenant_id"]
    )
    return ApiResponse(data=data)


@router.get("/patients/{patient_id}/summaries", response_model=ApiResponse[dict])
async def list_patient_summaries(
    patient_id: str,
    db: DbSession,
    doctor: CurrentDoctor,
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
) -> ApiResponse[dict]:
    """查询患者预问诊摘要列表（F24）。"""
    data = await doctor_service.list_patient_summaries(
        db,
        patient_id=patient_id,
        doctor_id=doctor["sub"],
        tenant_id=doctor["tenant_id"],
        page=page,
        size=size,
    )
    return ApiResponse(data=data)


@router.get("/depts", response_model=ApiResponse[list])
async def list_depts(db: DbSession, doctor: CurrentDoctor) -> ApiResponse[list]:
    """查询启用中的科室列表（供修正分诊下拉选择）。"""
    data = await doctor_service.list_depts(db, tenant_id=doctor["tenant_id"])
    return ApiResponse(data=data)
