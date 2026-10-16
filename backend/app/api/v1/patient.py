"""患者端路由：预问诊会话、消息、分诊结果。

对应 04 文档 12.2.1 / 12.2.4 / 12.3.1。
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentPatient
from app.common.database import get_db
from app.schemas.common import ApiResponse
from app.schemas.session import (
    MessageSendRequest,
    MessageSendResponse,
    SessionCreateRequest,
    SessionCreateResponse,
)
from app.schemas.triage import TriageResultResponse
from app.services import session_service

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
    # 后台触发编排图：主诉 → 澄清追问（interrupt）或直接分诊
    if req.chief_complaint:
        background_tasks.add_task(
            request.app.state.orchestrator.start,
            session_id=data.session_id,
            tenant_id=patient["tenant_id"],
            patient_id=patient["sub"],
            chief_complaint=req.chief_complaint,
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
