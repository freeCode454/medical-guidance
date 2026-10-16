"""医生端服务：接诊列表、会话详情、对话/病历/鉴别诊断查询、确认与修正分诊、接管。

多租户与权限约定：
- tenant_id 从 JWT 取，不接受客户端传参
- 医生只能访问自己接诊（doctor_id == 本人）或待接管队列中的会话
- 医生端越权访问返回 403（明确区分「无权限」，与患者端的 404 策略不同，便于定位）
- 确认 / 修正分诊写审计日志（TRIAGE_CONFIRM / TRIAGE_CORRECT）
"""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import AuditActionType, AuditResult, SessionStatus
from app.common.error_codes import (
    FORBIDDEN,
    NOT_FOUND,
    SESSION_CORRECTION_REASON,
    SESSION_CORRECTION_SAME,
    SESSION_NOT_TAKEOVER,
    SESSION_TAKEN_BY_OTHER,
    SESSION_TRIAGE_NOT_READY,
)
from app.common.exceptions import BizError
from app.models import (
    AuditLog,
    Dept,
    EmrRecord,
    MdtCouncil,
    Patient,
    Session,
    SessionMessage,
    TriageCorrection,
    TriageResult,
    User,
)

# 排序字段白名单（防对未索引字段排序）
_SORT_WHITELIST = {"started_time", "inquiry_rounds"}
# 可评价职称（副主任医师及以上，修正记录可作评测样本 AC-F19-2）
_EVAL_TITLES = {"副主任医师", "主任医师"}


def _patient_display(patient: Patient | None) -> str:
    """患者脱敏展示名：优先院内编号，否则用哈希前缀。"""
    if patient is None:
        return "患者"
    if patient.patient_no:
        return patient.patient_no
    return f"患者 {patient.patient_hash[:4] if patient.patient_hash else ''}"


async def _write_audit(
    db: AsyncSession,
    *,
    tenant_id: str,
    actor_id: str,
    actor_role: str,
    action_type: str,
    target_type: str,
    target_id: str | None,
    session_id: str | None,
    patient_hash: str | None = None,
    detail: dict | None = None,
) -> None:
    """写审计日志（只追加）。"""
    db.add(
        AuditLog(
            tenant_id=tenant_id,
            actor_id=actor_id,
            actor_role=actor_role,
            action_type=action_type,
            target_type=target_type,
            target_id=target_id,
            session_id=session_id,
            patient_hash=patient_hash,
            result=AuditResult.SUCCESS.value,
            detail_json=detail,
        )
    )


async def _get_doctor_session(
    db: AsyncSession, session_id: str, doctor_id: str, tenant_id: str
) -> Session:
    """取会话并校验医生归属。

    - 不存在 → 404
    - 存在但非本人接诊且不在待接管队列 → 403（医生端明确区分无权限）
    """
    session = await db.scalar(
        select(Session).where(Session.id == session_id, Session.tenant_id == tenant_id)
    )
    if session is None:
        raise BizError(NOT_FOUND)
    if session.doctor_id != doctor_id and session.status != SessionStatus.PENDING_TAKEOVER.value:
        raise BizError(FORBIDDEN, "该会话不属于当前医生")
    return session


async def list_encounters(
    db: AsyncSession,
    *,
    doctor_id: str,
    tenant_id: str,
    page: int,
    size: int,
    status: str | None,
    encounter_date: str | None,
    sort_by: str,
    sort_order: str,
) -> dict:
    """今日接诊列表（只返回当前医生接诊的患者）。"""
    if sort_by not in _SORT_WHITELIST:
        sort_by = "started_time"
    order_col = getattr(Session, sort_by)
    order = order_col.desc() if sort_order == "desc" else order_col.asc()

    # 就诊日期范围（默认今天）
    if encounter_date:
        day = datetime.strptime(encounter_date, "%Y-%m-%d").date()
    else:
        day = datetime.now(timezone.utc).date()
    day_start = datetime.combine(day, time.min, tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)

    conds = [
        Session.tenant_id == tenant_id,
        Session.doctor_id == doctor_id,
        Session.started_time >= day_start,
        Session.started_time < day_end,
    ]
    if status:
        conds.append(Session.status == status)

    total = await db.scalar(select(func.count()).select_from(Session).where(*conds))
    rows = (
        await db.scalars(
            select(Session)
            .where(*conds)
            .order_by(order)
            .offset((page - 1) * size)
            .limit(size)
        )
    ).all()

    # 批量取患者脱敏信息
    patient_ids = {s.patient_id for s in rows}
    patients = {
        p.id: p
        for p in (
            await db.scalars(select(Patient).where(Patient.id.in_(patient_ids)))
        ).all()
    }

    items = [
        {
            "session_id": s.id,
            "session_no": s.session_no,
            "patient_display": _patient_display(patients.get(s.patient_id)),
            "patient_hash": patients.get(s.patient_id).patient_hash if patients.get(s.patient_id) else None,
            "chief_complaint": s.chief_complaint,
            "status": s.status,
            "risk_flag": s.risk_flag == "1",
            "inquiry_rounds": s.inquiry_rounds,
            "started_time": s.started_time.isoformat() if s.started_time else None,
        }
        for s in rows
    ]
    return {"total": total, "page": page, "size": size, "items": items}


async def get_session_detail(
    db: AsyncSession, *, session_id: str, doctor_id: str, tenant_id: str
) -> dict:
    """会话详情（医生视图）。"""
    session = await _get_doctor_session(db, session_id, doctor_id, tenant_id)
    patient = await db.scalar(
        select(Patient).where(Patient.id == session.patient_id)
    )
    triage = await db.scalar(
        select(TriageResult).where(TriageResult.session_id == session_id)
    )

    return {
        "session_id": session.id,
        "session_no": session.session_no,
        "status": session.status,
        "risk_flag": session.risk_flag == "1",
        "chief_complaint": session.chief_complaint,
        "inquiry_rounds": session.inquiry_rounds,
        "patient": {
            "patient_id": session.patient_id,
            "patient_hash": patient.patient_hash if patient else None,
            "patient_display": _patient_display(patient),
            "age": patient.age if patient else None,
            "gender": _gender_label(patient.gender) if patient else None,
        },
        "triage_status": {
            "has_result": triage is not None,
            "route": triage.route if triage else None,
            "doctor_confirmed": triage.doctor_confirmed == "1" if triage else False,
        },
        "symptom_timeline": [],
        "consent_granted": False,
        "consent_scope_label": None,
        "started_time": session.started_time.isoformat() if session.started_time else None,
        "finished_time": session.finished_time.isoformat() if session.finished_time else None,
    }


def _gender_label(gender: str | None) -> str | None:
    return {"1": "男", "2": "女", "0": "未知"}.get(gender or "0")


async def list_messages(
    db: AsyncSession,
    *,
    session_id: str,
    doctor_id: str,
    tenant_id: str,
    page: int,
    size: int,
    include_system: bool,
) -> dict:
    """完整对话记录（医生视图，含系统内部消息）。"""
    await _get_doctor_session(db, session_id, doctor_id, tenant_id)

    conds = [SessionMessage.session_id == session_id, SessionMessage.tenant_id == tenant_id]
    if not include_system:
        conds.append(SessionMessage.role != "SYSTEM")

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

    items = [
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
    ]
    return {"total": total, "page": page, "size": size, "items": items}


async def get_emr(
    db: AsyncSession, *, session_id: str, doctor_id: str, tenant_id: str
) -> dict:
    """SOAP 病历（医生视图，保留评估段与鉴别方向）。"""
    await _get_doctor_session(db, session_id, doctor_id, tenant_id)

    emr = await db.scalar(
        select(EmrRecord).where(EmrRecord.session_id == session_id)
    )
    if emr is None:
        raise BizError(SESSION_TRIAGE_NOT_READY)

    triage = await db.scalar(
        select(TriageResult).where(TriageResult.session_id == session_id)
    )
    differential = []
    if triage and triage.candidates_json:
        for c in triage.candidates_json:
            differential.append(
                {
                    "dept_code": c.get("dept_code", ""),
                    "confidence": float(c.get("confidence", 0)),
                    "basis": [c.get("reason", "")] if c.get("reason") else [],
                }
            )

    return {
        "emr_record_id": emr.id,
        "schema_version": emr.schema_version,
        "generate_status": emr.generate_status,
        "completeness_rate": float(emr.completeness_rate or 0),
        "subjective": {
            "chief_complaint": emr.subjective or "",
            "present_illness": "",
            "past_history": [],
            "allergy": [],
        },
        "objective": {
            "collected_vitals": [],
            "note": "本次为线上预问诊，未采集体格检查数据",
        },
        "assessment": {
            "differential_directions": differential,
            "note": "以上为鉴别方向参考，不构成诊断",
        },
        "plan": {
            "recommended_depts": (
                [triage.candidates_json[0].get("dept_name", "")]
                if triage and triage.candidates_json
                else []
            ),
            "suggested_workup": [],
            "note": "以上为就诊建议，不构成诊断",
        },
        "disclaimer": "本系统仅提供分诊建议，不构成医学诊断。请以医生面诊为准。",
        "generated_time": emr.create_time.isoformat() if emr.create_time else None,
    }


async def get_diagnosis(
    db: AsyncSession,
    *,
    session_id: str,
    doctor_id: str,
    tenant_id: str,
    include_mdt: bool,
) -> dict:
    """鉴别诊断候选与依据 + 用药禁忌校验。"""
    await _get_doctor_session(db, session_id, doctor_id, tenant_id)

    triage = await db.scalar(
        select(TriageResult).where(TriageResult.session_id == session_id)
    )
    if triage is None:
        raise BizError(SESSION_TRIAGE_NOT_READY)

    candidates = [
        {
            "rank": i + 1,
            "dept_code": c.get("dept_code", ""),
            "dept_name": c.get("dept_name", ""),
            "confidence": float(c.get("confidence", 0)),
            "hit_symptoms": [c.get("reason", "")] if c.get("reason") else [],
            "guideline_refs": [],  # 依据不足须显式为空，不隐藏候选
        }
        for i, c in enumerate(triage.candidates_json or [])
    ]

    mdt_data = None
    if include_mdt:
        mdt = await db.scalar(
            select(MdtCouncil).where(MdtCouncil.session_id == session_id)
        )
        if mdt is not None:
            divergence_items = []
            if mdt.divergence_json and mdt.divergence_json.get("minority_opinions"):
                for op in mdt.divergence_json["minority_opinions"]:
                    divergence_items.append(
                        {
                            "dept_code": op.get("dept_code", ""),
                            "dept_name": op.get("dept_name", ""),
                            "opinion": op.get("suggested_dept", ""),
                            "reason": op.get("rationale", ""),
                            "confidence": None,
                        }
                    )
            mdt_data = {
                "triggered": True,
                "candidate_depts": mdt.candidate_depts or [],
                "opinion_count": len(mdt.opinions_json or []),
                "missing_count": mdt.missing_count,
                "duration_ms": mdt.duration_ms,
                "divergence": {
                    "exists": mdt.divergence_flag == "1",
                    "items": divergence_items,
                },
                "consensus_dept": mdt.consensus_dept,
                "consensus_confidence": float(mdt.consensus_confidence or 0),
            }

    return {
        "triage_result_id": triage.id,
        "retrieval_mode": triage.retrieval_mode,
        "kb_version": triage.kb_version,
        "candidates": candidates,
        "mdt": mdt_data,
        # 用药禁忌校验：禁忌知识库未建立，显式告知未完成（不得静默略过）
        "drug_safety": {
            "checked": False,
            "allergy_hits": [],
            "contraindication_hits": [],
            "note": "用药禁忌校验未完成（禁忌知识库尚未建立），请医生自行核对患者过敏史。",
        },
    }


async def confirm_triage(
    db: AsyncSession,
    *,
    session_id: str,
    doctor_id: str,
    tenant_id: str,
    note: str | None,
) -> dict:
    """确认分诊建议（幂等）。"""
    session = await _get_doctor_session(db, session_id, doctor_id, tenant_id)

    triage = await db.scalar(
        select(TriageResult).where(TriageResult.session_id == session_id)
    )
    if triage is None:
        raise BizError(SESSION_TRIAGE_NOT_READY)
    if session.doctor_id != doctor_id:
        raise BizError(SESSION_TAKEN_BY_OTHER)

    # 幂等：已确认则直接返回
    if triage.doctor_confirmed == "1":
        top = (triage.candidates_json or [{}])[0]
        return {
            "session_id": session_id,
            "triage_result_id": triage.id,
            "doctor_confirmed": True,
            "confirmed_time": triage.confirmed_time.isoformat() if triage.confirmed_time else None,
            "dept_code": top.get("dept_code"),
            "dept_name": top.get("dept_name"),
            "snapshot_saved": True,
        }

    triage.doctor_confirmed = "1"
    triage.confirmed_time = datetime.now(timezone.utc)

    await _write_audit(
        db,
        tenant_id=tenant_id,
        actor_id=doctor_id,
        actor_role="DOCTOR",
        action_type=AuditActionType.TRIAGE_CONFIRM.value,
        target_type="triage_result",
        target_id=triage.id,
        session_id=session_id,
        detail={"note": note},
    )
    await db.commit()

    top = (triage.candidates_json or [{}])[0]
    return {
        "session_id": session_id,
        "triage_result_id": triage.id,
        "doctor_confirmed": True,
        "confirmed_time": triage.confirmed_time.isoformat(),
        "dept_code": top.get("dept_code"),
        "dept_name": top.get("dept_name"),
        "snapshot_saved": True,
    }


async def correct_triage(
    db: AsyncSession,
    *,
    session_id: str,
    doctor_id: str,
    tenant_id: str,
    after_dept: str,
    reason: str,
) -> dict:
    """修正分诊建议，留存为评测样本。"""
    session = await _get_doctor_session(db, session_id, doctor_id, tenant_id)

    if session.doctor_id != doctor_id:
        raise BizError(SESSION_TAKEN_BY_OTHER)
    if len(reason.strip()) < 10:
        raise BizError(SESSION_CORRECTION_REASON)

    triage = await db.scalar(
        select(TriageResult).where(TriageResult.session_id == session_id)
    )
    if triage is None:
        raise BizError(SESSION_TRIAGE_NOT_READY)

    before_dept = session.dept_code or ""
    if before_dept == after_dept:
        raise BizError(SESSION_CORRECTION_SAME)

    # 校验修正后科室存在
    dept = await db.scalar(
        select(Dept).where(Dept.tenant_id == tenant_id, Dept.dept_code == after_dept)
    )
    if dept is None:
        raise BizError(NOT_FOUND, "修正后科室不存在于当前租户")

    # 职称快照 + 是否可评测（副主任医师及以上）
    doctor = await db.scalar(select(User).where(User.id == doctor_id))
    doctor_title = doctor.title if doctor else None
    usable = doctor_title in _EVAL_TITLES

    correction = TriageCorrection(
        tenant_id=tenant_id,
        triage_id=triage.id,
        session_id=session_id,
        before_dept=before_dept,
        after_dept=after_dept,
        reason=reason.strip(),
        doctor_id=doctor_id,
        doctor_title=doctor_title or "",
        usable_for_eval="1" if usable else "0",
    )
    db.add(correction)

    # 更新会话建议科室为修正后科室
    session.dept_code = after_dept

    await _write_audit(
        db,
        tenant_id=tenant_id,
        actor_id=doctor_id,
        actor_role="DOCTOR",
        action_type=AuditActionType.TRIAGE_CORRECT.value,
        target_type="triage_result",
        target_id=triage.id,
        session_id=session_id,
        detail={"before_dept": before_dept, "after_dept": after_dept},
    )
    await db.commit()

    return {
        "correction_id": correction.id,
        "before_dept": before_dept,
        "before_dept_name": None,
        "after_dept": after_dept,
        "after_dept_name": dept.dept_name,
        "doctor_title": doctor_title,
        "usable_for_eval": usable,
        "created_time": correction.create_time.isoformat() if correction.create_time else None,
    }


async def list_takeover_queue(
    db: AsyncSession, *, tenant_id: str, page: int, size: int
) -> dict:
    """待接管队列（所有待接管会话，供医生认领）。"""
    conds = [
        Session.tenant_id == tenant_id,
        Session.status == SessionStatus.PENDING_TAKEOVER.value,
    ]
    total = await db.scalar(select(func.count()).select_from(Session).where(*conds))
    rows = (
        await db.scalars(
            select(Session)
            .where(*conds)
            .order_by(Session.started_time.asc())
            .offset((page - 1) * size)
            .limit(size)
        )
    ).all()

    patient_ids = {s.patient_id for s in rows}
    patients = {
        p.id: p
        for p in (await db.scalars(select(Patient).where(Patient.id.in_(patient_ids)))).all()
    }

    items = [
        {
            "session_id": s.id,
            "session_no": s.session_no,
            "patient_display": _patient_display(patients.get(s.patient_id)),
            "chief_complaint": s.chief_complaint,
            "risk_flag": s.risk_flag == "1",
            "inquiry_rounds": s.inquiry_rounds,
            "started_time": s.started_time.isoformat() if s.started_time else None,
        }
        for s in rows
    ]
    return {"total": total, "page": page, "size": size, "items": items}


async def takeover_session(
    db: AsyncSession, *, session_id: str, doctor_id: str, tenant_id: str
) -> dict:
    """医生接管会话。"""
    session = await db.scalar(
        select(Session).where(Session.id == session_id, Session.tenant_id == tenant_id)
    )
    if session is None:
        raise BizError(NOT_FOUND)
    if session.status != SessionStatus.PENDING_TAKEOVER.value:
        raise BizError(SESSION_NOT_TAKEOVER)

    session.doctor_id = doctor_id
    session.status = SessionStatus.TAKEN_OVER.value
    await db.commit()

    return {
        "session_id": session_id,
        "doctor_id": doctor_id,
        "status": SessionStatus.TAKEN_OVER.value,
    }


async def get_patient_emr(
    db: AsyncSession, *, patient_id: str, doctor_id: str, tenant_id: str
) -> dict:
    """查阅患者既往病历（预问诊病历列表）。"""
    patient = await db.scalar(
        select(Patient).where(Patient.id == patient_id, Patient.tenant_id == tenant_id)
    )
    if patient is None:
        raise BizError(NOT_FOUND)

    # 医生查看患者病历需有授权（简化：当前租户内医生均可查看，后续接 consent 校验）
    await _write_audit(
        db,
        tenant_id=tenant_id,
        actor_id=doctor_id,
        actor_role="DOCTOR",
        action_type=AuditActionType.EMR_READ.value,
        target_type="patient",
        target_id=patient_id,
        session_id=None,
        patient_hash=patient.patient_hash,
    )
    await db.commit()

    emrs = (
        await db.scalars(
            select(EmrRecord)
            .where(EmrRecord.patient_id == patient_id, EmrRecord.tenant_id == tenant_id)
            .order_by(EmrRecord.create_time.desc())
        )
    ).all()

    return {
        "patient_id": patient_id,
        "patient_display": _patient_display(patient),
        "records": [
            {
                "emr_record_id": e.id,
                "session_id": e.session_id,
                "chief_complaint": e.subjective or "",
                "generate_status": e.generate_status,
                "created_time": e.create_time.isoformat() if e.create_time else None,
            }
            for e in emrs
        ],
    }


async def list_patient_summaries(
    db: AsyncSession, *, patient_id: str, doctor_id: str, tenant_id: str, page: int, size: int
) -> dict:
    """查询患者预问诊摘要列表（历史分诊结论）。"""
    patient = await db.scalar(
        select(Patient).where(Patient.id == patient_id, Patient.tenant_id == tenant_id)
    )
    if patient is None:
        raise BizError(NOT_FOUND)

    conds = [
        TriageResult.tenant_id == tenant_id,
    ]
    # 通过会话关联患者：先取该患者的会话
    session_ids = (
        await db.scalars(
            select(Session.id).where(
                Session.tenant_id == tenant_id, Session.patient_id == patient_id
            )
        )
    ).all()
    if not session_ids:
        return {"total": 0, "page": page, "size": size, "items": []}

    conds.append(TriageResult.session_id.in_(session_ids))
    total = await db.scalar(select(func.count()).select_from(TriageResult).where(*conds))
    rows = (
        await db.scalars(
            select(TriageResult)
            .where(*conds)
            .order_by(TriageResult.create_time.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
    ).all()

    items = [
        {
            "triage_result_id": t.id,
            "session_id": t.session_id,
            "route": t.route,
            "confidence": float(t.confidence or 0),
            "dept_code": (t.candidates_json or [{}])[0].get("dept_code"),
            "dept_name": (t.candidates_json or [{}])[0].get("dept_name"),
            "doctor_confirmed": t.doctor_confirmed == "1",
            "created_time": t.create_time.isoformat() if t.create_time else None,
        }
        for t in rows
    ]
    return {"total": total, "page": page, "size": size, "items": items}


async def list_depts(db: AsyncSession, *, tenant_id: str) -> list[dict]:
    """查询启用中的科室列表（供修正分诊下拉选择）。"""
    rows = (
        await db.scalars(
            select(Dept)
            .where(Dept.tenant_id == tenant_id, Dept.status == "1")
            .order_by(Dept.sort_no.asc())
        )
    ).all()
    return [{"dept_code": d.dept_code, "dept_name": d.dept_name} for d in rows]
