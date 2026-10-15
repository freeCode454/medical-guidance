"""患者端路由：预问诊会话、消息、分诊结果。

对应 04 文档 12.2.1 / 12.2.4 / 12.3.1。
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
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
    req: SessionCreateRequest, db: DbSession, patient: CurrentPatient
) -> ApiResponse[SessionCreateResponse]:
    """创建一次预问诊会话。"""
    data = await session_service.create_session(db, patient, req)
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
) -> ApiResponse[MessageSendResponse]:
    """发送一条患者消息，触发智能体流程（本期仅落库，AI 回复经 WS 推送）。"""
    data = await session_service.send_message(
        db, session_id, patient, req.content, req.msg_type, req.extra
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
