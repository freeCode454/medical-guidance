"""患者端会话服务：创建会话、发送消息、查询分诊结果。

本期不含智能体：发消息仅落库并返回异步提示，AI 回复后续由编排层经
WebSocket 推送。分诊结果接口在结论未生成时返回 20006。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import MessageRole, MessageType, SessionStatus
from app.common.error_codes import (
    NOT_FOUND,
    SESSION_ALREADY_CLOSED,
    SESSION_EMERGENCY_TRIGGERED,
    SESSION_MESSAGE_EMPTY,
    SESSION_TRIAGE_NOT_READY,
)
from app.common.exceptions import BizError
from app.models import Session, SessionMessage, TriageResult
from app.schemas.session import (
    MessageSendResponse,
    SessionCreateRequest,
    SessionCreateResponse,
)
from app.schemas.triage import TriageResultResponse


def _gen_session_no() -> str:
    """会话业务编号：S + 年月日时分秒 + 4 位随机。"""
    now = datetime.now()
    return f"S{now:%Y%m%d%H%M%S}{uuid4().hex[:4]}"


def _is_terminal(status: str) -> bool:
    return status in {
        SessionStatus.FINISHED.value,
        SessionStatus.TAKEN_OVER.value,
        SessionStatus.CLOSED.value,
        SessionStatus.EMERGENCY.value,
    }


async def _get_owned_session(
    db: AsyncSession, session_id: str, patient_id: str, tenant_id: str
) -> Session:
    """取会话并校验归属。

    会话不存在、不属于当前租户、或不属于当前患者，统一返回 404——
    不区分「不存在」与「无权访问」，避免探测其他租户/患者资源是否存在
    （《04 文档》错误码约定第 1 条）。
    """
    session = await db.scalar(
        select(Session).where(
            Session.id == session_id,
            Session.tenant_id == tenant_id,
            Session.patient_id == patient_id,
        )
    )
    if session is None:
        raise BizError(NOT_FOUND)
    return session


async def create_session(
    db: AsyncSession,
    payload: dict,
    req: SessionCreateRequest,
) -> SessionCreateResponse:
    """创建预问诊会话。"""
    patient_id = payload["sub"]
    tenant_id = payload["tenant_id"]

    # 同设备存在未完成会话则复用（幂等兜底）
    if req.device_id:
        existing = await db.scalar(
            select(Session).where(
                Session.tenant_id == tenant_id,
                Session.patient_id == patient_id,
                Session.device_id == req.device_id,
                Session.status.in_([SessionStatus.IN_PROGRESS.value]),
            )
        )
        if existing is not None:
            return SessionCreateResponse(
                session_id=existing.id,
                session_no=existing.session_no,
                status=SessionStatus(existing.status),
                started_time=existing.started_time,
                expire_time=existing.expire_time,
                ws_url=f"/api/v1/ws/sessions/{existing.id}",
            )

    now = datetime.now(timezone.utc)
    session = Session(
        tenant_id=tenant_id,
        patient_id=patient_id,
        session_no=_gen_session_no(),
        chief_complaint=req.chief_complaint,
        status=SessionStatus.IN_PROGRESS.value,
        inquiry_rounds=0,
        device_id=req.device_id,
        started_time=now,
        expire_time=now + timedelta(hours=24),
    )
    db.add(session)
    await db.flush()

    # 主诉非空时落第一条患者消息
    if req.chief_complaint:
        db.add(
            SessionMessage(
                tenant_id=tenant_id,
                session_id=session.id,
                seq_no=1,
                role=MessageRole.PATIENT.value,
                content=req.chief_complaint,
                msg_type=MessageType.TEXT.value,
            )
        )

    await db.commit()

    return SessionCreateResponse(
        session_id=session.id,
        session_no=session.session_no,
        status=SessionStatus.IN_PROGRESS,
        started_time=session.started_time,
        expire_time=session.expire_time,
        ws_url=f"/api/v1/ws/sessions/{session.id}",
    )


async def send_message(
    db: AsyncSession,
    session_id: str,
    payload: dict,
    content: str,
    msg_type: MessageType,
    extra: dict,
) -> MessageSendResponse:
    """落库一条患者消息，触发异步智能体流程（本期仅落库）。"""
    patient_id = payload["sub"]
    tenant_id = payload["tenant_id"]

    session = await _get_owned_session(db, session_id, patient_id, tenant_id)

    if session.status == SessionStatus.EMERGENCY.value:
        raise BizError(SESSION_EMERGENCY_TRIGGERED)
    if _is_terminal(session.status):
        raise BizError(SESSION_ALREADY_CLOSED)

    content = (content or "").strip()
    if not content:
        raise BizError(SESSION_MESSAGE_EMPTY)

    # 会话内序号 = 当前最大 + 1
    current_max = await db.scalar(
        select(func.max(SessionMessage.seq_no)).where(
            SessionMessage.session_id == session_id,
            SessionMessage.tenant_id == tenant_id,
        )
    )
    seq_no = (current_max or 0) + 1

    message = SessionMessage(
        tenant_id=tenant_id,
        session_id=session_id,
        seq_no=seq_no,
        role=MessageRole.PATIENT.value,
        content=content,
        msg_type=msg_type.value,
        extra_json=extra or None,
    )
    db.add(message)
    await db.commit()

    return MessageSendResponse(
        message_id=message.id,
        seq_no=seq_no,
        session_status=SessionStatus(session.status),
    )


async def get_triage_result(
    db: AsyncSession, session_id: str, payload: dict
) -> TriageResultResponse:
    """查询分诊结果（患者视图）。结论未生成时返回 20006。"""
    patient_id = payload["sub"]
    tenant_id = payload["tenant_id"]

    await _get_owned_session(db, session_id, patient_id, tenant_id)

    result = await db.scalar(
        select(TriageResult).where(
            TriageResult.session_id == session_id,
            TriageResult.tenant_id == tenant_id,
        )
    )
    if result is None:
        raise BizError(SESSION_TRIAGE_NOT_READY)

    # 从 JSONB 快照还原候选科室（患者视图：只含科室，不含疾病名）
    from app.schemas.triage import EmergencyGuidance, RecommendedDept, SymptomSummary

    candidates = result.candidates_json or []
    recommended = [
        RecommendedDept(
            dept_code=c.get("dept_code", ""),
            dept_name=c.get("dept_name", ""),
            confidence=float(c.get("confidence", 0)),
            is_primary=bool(c.get("is_primary", False)),
        )
        for c in candidates
    ]

    return TriageResultResponse(
        triage_result_id=result.id,
        route=result.route,
        confidence=float(result.confidence or 0),
        recommended_depts=recommended,
        symptom_summary=SymptomSummary(),
        inquiry_rounds=0,
        emergency_guidance=None,
        disclaimer="本系统仅提供分诊建议，不构成医学诊断。请以医生面诊为准。",
        generated_time=result.create_time,
    )
