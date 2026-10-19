"""患者端路由：预问诊会话、消息、分诊结果。

对应 04 文档 12.2.1 / 12.2.4 / 12.3.1。
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentPatient
from app.common.database import get_db
from app.schemas.appointment import AppointmentCreateRequest
from app.schemas.common import ApiResponse
from app.schemas.consent import ConsentCreateRequest, ConsentItem, ConsentListResponse
from app.schemas.session import (
    MessageSendRequest,
    MessageSendResponse,
    SessionCreateRequest,
    SessionCreateResponse,
)
from app.schemas.triage import TriageResultResponse
from app.services import appointment_service, consent_service, history_service, session_service

router = APIRouter(prefix="/api/v1/patient", tags=["患者端"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.post("/sessions", response_model=ApiResponse[SessionCreateResponse])
async def create_session(
    req: SessionCreateRequest,
    db: DbSession,
    patient: CurrentPatient,
    request: Request,
    background_tasks: BackgroundTasks,
) -> ApiResponse[SessionCreateResponse]:
    """创建一次预问诊会话，并触发编排图（追问/分诊）。"""
    data = await session_service.create_session(db, patient, req)
    # 患者已授权时，把既往病史摘要注入本次问诊上下文（未授权不读取）
    history = await history_service.load_history_context(
        db,
        tenant_id=patient["tenant_id"],
        patient_id=patient["sub"],
        exclude_session_id=data.session_id,
    )
    # 后台触发编排图：主诉 → 澄清追问（interrupt）或直接分诊
    if req.chief_complaint:
        background_tasks.add_task(
            request.app.state.orchestrator.start,
            session_id=data.session_id,
            tenant_id=patient["tenant_id"],
            patient_id=patient["sub"],
            chief_complaint=req.chief_complaint,
            gender=req.gender,
            age=req.age,
            history_summary=history["summary"] if history else None,
            history_past=history["past_history"] if history else None,
            history_allergy=history["allergy"] if history else None,
        )
    return ApiResponse(data=data)


@router.post(
    "/sessions/{session_id}/messages",
    response_model=ApiResponse[MessageSendResponse],
)
async def send_message(
    session_id: str,
    req: MessageSendRequest,
    db: DbSession,
    patient: CurrentPatient,
    request: Request,
    background_tasks: BackgroundTasks,
) -> ApiResponse[MessageSendResponse]:
    """发送一条患者消息，恢复编排图（患者回答追问）。"""
    data = await session_service.send_message(
        db, session_id, patient, req.content, req.msg_type, req.extra
    )
    # 后台恢复编排图：患者回答 → 继续追问或生成分诊结论
    background_tasks.add_task(
        request.app.state.orchestrator.resume,
        session_id=session_id,
        tenant_id=patient["tenant_id"],
        patient_id=patient["sub"],
        answer=req.content,
    )
    return ApiResponse(data=data)


@router.get(
    "/sessions/{session_id}/triage",
    response_model=ApiResponse[TriageResultResponse],
)
async def get_triage(
    session_id: str, db: DbSession, patient: CurrentPatient
) -> ApiResponse[TriageResultResponse]:
    """查询分诊结果（患者视图）。"""
    data = await session_service.get_triage_result(db, session_id, patient)
    return ApiResponse(data=data)


@router.get("/sessions/{session_id}", response_model=ApiResponse[dict])
async def get_session_detail(
    session_id: str, db: DbSession, patient: CurrentPatient
) -> ApiResponse[dict]:
    """查询会话详情（患者视图，12.2.3）。"""
    data = await session_service.get_session_detail(db, session_id, patient)
    return ApiResponse(data=data)


@router.get("/sessions/{session_id}/messages", response_model=ApiResponse[dict])
async def list_messages(
    session_id: str,
    db: DbSession,
    patient: CurrentPatient,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    after_seq: int | None = Query(None, ge=0),
) -> ApiResponse[dict]:
    """查询对话记录（患者视图，12.2.5）。"""
    data = await session_service.list_messages(
        db, session_id, patient, page=page, size=size, after_seq=after_seq
    )
    return ApiResponse(data=data)


@router.get("/sessions/{session_id}/emr", response_model=ApiResponse[dict])
async def get_emr(session_id: str, db: DbSession, patient: CurrentPatient) -> ApiResponse[dict]:
    """查询预问诊病历（患者视图，12.3.2）。"""
    data = await session_service.get_emr(db, session_id, patient)
    return ApiResponse(data=data)


# ---------------- 预约挂号 ----------------


@router.get("/appointments/slots", response_model=ApiResponse[dict])
async def list_appointment_slots(
    db: DbSession,
    patient: CurrentPatient,
    dept_code: str = Query(..., min_length=1, max_length=32),
) -> ApiResponse[dict]:
    """查询某科室未来 7 天的医生、日期与全部时段号源。"""
    data = await appointment_service.list_slots(
        db, tenant_id=patient["tenant_id"], dept_code=dept_code
    )
    return ApiResponse(data=data)


@router.get("/appointments", response_model=ApiResponse[dict])
async def list_appointments(
    db: DbSession, patient: CurrentPatient
) -> ApiResponse[dict]:
    """我的预约记录。"""
    data = await appointment_service.list_appointments(
        db, tenant_id=patient["tenant_id"], patient_id=patient["sub"]
    )
    return ApiResponse(data=data)


@router.post("/appointments", response_model=ApiResponse[dict])
async def create_appointment(
    req: AppointmentCreateRequest, db: DbSession, patient: CurrentPatient
) -> ApiResponse[dict]:
    """预约挂号：占用一个号源。"""
    data = await appointment_service.create_appointment(
        db,
        tenant_id=patient["tenant_id"],
        patient_id=patient["sub"],
        session_id=req.session_id,
        dept_code=req.dept_code,
        doctor_id=req.doctor_id,
        schedule_date=req.schedule_date,
        time_slot=req.time_slot,
    )
    return ApiResponse(data=data, message="预约成功")


@router.post("/appointments/{appointment_id}/cancel", response_model=ApiResponse[dict])
async def cancel_appointment(
    appointment_id: str, db: DbSession, patient: CurrentPatient
) -> ApiResponse[dict]:
    """取消预约。"""
    data = await appointment_service.cancel_appointment(
        db,
        tenant_id=patient["tenant_id"],
        patient_id=patient["sub"],
        appointment_id=appointment_id,
    )
    return ApiResponse(data=data, message="已取消预约")


# ---------------- 病史调阅授权 ----------------


@router.get("/consents", response_model=ApiResponse[ConsentListResponse])
async def list_consents(db: DbSession, patient: CurrentPatient) -> ApiResponse[ConsentListResponse]:
    """查看自己的病史调阅授权记录（含已撤回/过期）。"""
    items = await consent_service.list_consents(
        db, tenant_id=patient["tenant_id"], patient_id=patient["sub"]
    )
    return ApiResponse(data=ConsentListResponse(items=[ConsentItem(**item) for item in items]))


@router.post("/consents", response_model=ApiResponse[ConsentItem])
async def grant_consent(
    req: ConsentCreateRequest, db: DbSession, patient: CurrentPatient
) -> ApiResponse[ConsentItem]:
    """授权接诊医生调阅历史预问诊病历。"""
    data = await consent_service.grant_consent(
        db,
        tenant_id=patient["tenant_id"],
        patient_id=patient["sub"],
        scope=req.scope,
        session_id=req.session_id,
        expire_days=req.expire_days,
    )
    return ApiResponse(data=ConsentItem(**data), message="已授权")


@router.post("/consents/{consent_id}/revoke", response_model=ApiResponse[ConsentItem])
async def revoke_consent(
    consent_id: str, db: DbSession, patient: CurrentPatient
) -> ApiResponse[ConsentItem]:
    """撤回授权。"""
    data = await consent_service.revoke_consent(
        db,
        tenant_id=patient["tenant_id"],
        patient_id=patient["sub"],
        consent_id=consent_id,
    )
    return ApiResponse(data=ConsentItem(**data), message="已撤回")
