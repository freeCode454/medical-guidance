"""患者端会话服务：创建会话、发送消息、查询分诊结果。

本期不含智能体：发消息仅落库并返回异步提示，AI 回复后续由编排层经
WebSocket 推送。分诊结果接口在结论未生成时返回 20006。
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.database import lock_message_sequence
from app.common.enums import MessageRole, MessageType, SessionStatus, TriageRoute
from app.common.error_codes import (
    NOT_FOUND,
    SESSION_ALREADY_CLOSED,
    SESSION_EMERGENCY_TRIGGERED,
    SESSION_MESSAGE_EMPTY,
    SESSION_TRIAGE_NOT_READY,
)
from app.common.exceptions import BizError
from app.common.security import device_fingerprint
from app.models import EmrRecord, Patient, Session, SessionMessage, TriageResult
from app.schemas.session import (
    MessageSendResponse,
    SessionCreateRequest,
    SessionCreateResponse,
)
from app.schemas.triage import (
    EmergencyGuidance,
    RecommendedDept,
    SymptomSummary,
    TriageResultResponse,
)


def _gen_session_no() -> str:
    """会话业务编号：S + 年月日时分秒 + 4 位随机。"""
    now = datetime.now()
    return f"S{now:%Y%m%d%H%M%S}{uuid4().hex[:4]}"


def _is_terminal(status: str) -> bool:
    return status in {
        SessionStatus.FINISHED.value,
        SessionStatus.PENDING_TAKEOVER.value,
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

    # 同设备存在未完成会话则复用（幂等兜底）；设备密钥只存指纹，兼容旧的明文记录
    if req.device_id:
        fingerprint = device_fingerprint(req.device_id)
        existing = await db.scalar(
            select(Session).where(
                Session.tenant_id == tenant_id,
                Session.patient_id == patient_id,
                or_(
                    Session.device_id == fingerprint,
                    Session.device_id == req.device_id,
                ),
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

    now = datetime.now(UTC)
    session = Session(
        tenant_id=tenant_id,
        patient_id=patient_id,
        session_no=_gen_session_no(),
        chief_complaint=req.chief_complaint,
        status=SessionStatus.IN_PROGRESS.value,
        inquiry_rounds=0,
        device_id=device_fingerprint(req.device_id) if req.device_id else None,
        started_time=now,
        expire_time=now + timedelta(hours=24),
    )
    db.add(session)
    await db.flush()

    # 采集性别/年龄（若请求提供），供分诊规则的人群过滤使用（妇科/产科仅女性、儿童/老年科室）
    if req.gender or req.age is not None:
        patient = await db.scalar(select(Patient).where(Patient.id == patient_id))
        if patient is not None:
            if req.gender:
                patient.gender = "1" if req.gender == "男" else "2"
            if req.age is not None:
                patient.age = req.age

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

    # 会话内序号 = 当前最大 + 1；先加事务级会话锁，避免并发消息撞唯一键
    await lock_message_sequence(db, session_id)
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

    session = await _get_owned_session(db, session_id, patient_id, tenant_id)

    result = await db.scalar(
        select(TriageResult).where(
            TriageResult.session_id == session_id,
            TriageResult.tenant_id == tenant_id,
        )
    )
    if result is None:
        raise BizError(SESSION_TRIAGE_NOT_READY)

    # 从 JSONB 快照还原候选科室（患者视图：只含科室，不含疾病名）
    candidates = result.candidates_json or []
    recommended = [
        RecommendedDept(
            dept_code=c.get("dept_code", ""),
            dept_name=c.get("dept_name", ""),
            confidence=float(c.get("confidence", 0)),
            is_primary=(i == 0),  # 置信度最高者为首要推荐
        )
        for i, c in enumerate(candidates)
    ]

    # 症状摘要来自落库时的 state 快照，进程重启后仍可还原
    evidence = result.evidence_json or {}
    raw_summary = evidence.get("symptom_summary") or {}
    summary = SymptomSummary(
        chief_complaint=raw_summary.get("chief_complaint") or session.chief_complaint,
        duration=raw_summary.get("duration"),
        location=raw_summary.get("location"),
        nature=raw_summary.get("nature"),
        accompanying=raw_summary.get("accompanying"),
        past_history=raw_summary.get("past_history"),
        allergy=raw_summary.get("allergy"),
    )

    emergency = None
    if result.route == TriageRoute.EMERGENCY.value:
        emergency = EmergencyGuidance(
            triggered=True,
            reason=evidence.get("risk_reason") or "症状命中急危重症预警规则",
            advice="请立即前往就近医院急诊科就诊，或拨打 120 急救电话。",
            emergency_phone="120",
            recommended_dept="急诊科",
        )

    return TriageResultResponse(
        triage_result_id=result.id,
        route=TriageRoute(result.route),
        confidence=float(result.confidence or 0),
        recommended_depts=recommended,
        symptom_summary=summary,
        inquiry_rounds=session.inquiry_rounds,
        history_used=bool(evidence.get("history_used")),
        emergency_guidance=emergency,
        disclaimer="本系统仅提供分诊建议，不构成医学诊断。请以医生面诊为准。",
        generated_time=result.create_time,
    )


async def list_messages(
    db: AsyncSession,
    session_id: str,
    payload: dict,
    page: int,
    size: int,
    after_seq: int | None,
) -> dict:
    """查询对话记录（患者视图）。过滤 SYSTEM 内部消息，按 seq_no 升序。"""
    patient_id = payload["sub"]
    tenant_id = payload["tenant_id"]
    await _get_owned_session(db, session_id, patient_id, tenant_id)

    conds = [
        SessionMessage.session_id == session_id,
        SessionMessage.tenant_id == tenant_id,
        SessionMessage.role != "SYSTEM",
    ]
    if after_seq is not None:
        conds.append(SessionMessage.seq_no > after_seq)

    total = await db.scalar(select(func.count()).select_from(SessionMessage).where(*conds))
    rows = (
        await db.scalars(
            select(SessionMessage)
            .where(*conds)
            .order_by(SessionMessage.seq_no.asc())
            .offset((page - 1) * size)
            .limit(size)
        )
    ).all()
    return {
        "total": total,
        "page": page,
        "size": size,
        "items": [
            {
                "message_id": m.id,
                "seq_no": m.seq_no,
                "role": m.role,
                "content": m.content,
                "msg_type": m.msg_type,
                "extra": m.extra_json,
                "send_time": m.send_time.isoformat() if m.send_time else None,
            }
            for m in rows
        ],
    }


async def get_session_detail(db: AsyncSession, session_id: str, payload: dict) -> dict:
    """查询会话详情（患者视图）。"""
    patient_id = payload["sub"]
    tenant_id = payload["tenant_id"]
    session = await _get_owned_session(db, session_id, patient_id, tenant_id)

    triage = await db.scalar(
        select(TriageResult).where(
            TriageResult.session_id == session_id,
            TriageResult.tenant_id == tenant_id,
        )
    )
    return {
        "session_id": session.id,
        "session_no": session.session_no,
        "status": session.status,
        "chief_complaint": session.chief_complaint,
        "inquiry_rounds": session.inquiry_rounds,
        "has_triage": triage is not None,
        "route": triage.route if triage else None,
        "started_time": session.started_time.isoformat() if session.started_time else None,
        "finished_time": session.finished_time.isoformat() if session.finished_time else None,
    }


async def get_emr(db: AsyncSession, session_id: str, payload: dict) -> dict:
    """查询预问诊病历（患者视图）。A 段恒为 null（R01），不含疾病名与用药建议。"""
    patient_id = payload["sub"]
    tenant_id = payload["tenant_id"]
    session = await _get_owned_session(db, session_id, patient_id, tenant_id)

    emr = await db.scalar(
        select(EmrRecord).where(
            EmrRecord.session_id == session_id,
            EmrRecord.tenant_id == tenant_id,
        )
    )
    if emr is None:
        raise BizError(SESSION_TRIAGE_NOT_READY)

    triage = await db.scalar(
        select(TriageResult).where(
            TriageResult.session_id == session_id,
            TriageResult.tenant_id == tenant_id,
        )
    )
    dept_names = [
        c.get("dept_name", "")
        for c in ((triage.candidates_json if triage else []) or [])
        if c.get("dept_name")
    ]

    # 结构化实体在生成时随 soap_json 一起保存，这里只读取，不臆造
    soap = emr.soap_json or {}
    entities = soap.get("entities") or {}

    def _as_list(value: object) -> list[str]:
        if isinstance(value, list):
            return [str(item) for item in value if item]
        if isinstance(value, str) and value:
            return [value]
        return []

    return {
        "emr_record_id": emr.id,
        "schema_version": emr.schema_version,
        "generate_status": emr.generate_status,
        "subjective": {
            "chief_complaint": session.chief_complaint or "",
            "present_illness": emr.subjective or "",
            "past_history": _as_list(entities.get("past_history")),
            "allergy": _as_list(entities.get("allergy")),
        },
        "objective": {
            "collected_vitals": [],
            "note": emr.objective
            or "本次为线上预问诊，未采集体格检查数据",
        },
        "assessment": None,  # 患者视图恒为 null
        "plan": {
            "recommended_depts": dept_names,
            "suggested_workup": [],
            "note": emr.plan or "以上为就诊建议，不构成诊断",
        },
        "disclaimer": "本系统仅提供分诊建议，不构成医学诊断。请以医生面诊为准。",
        "generated_time": emr.create_time.isoformat() if emr.create_time else None,
    }
