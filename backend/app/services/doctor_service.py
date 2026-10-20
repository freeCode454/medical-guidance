"""医生端服务：接诊列表、会话详情、对话/病历/鉴别诊断查询、确认与修正分诊、接管。

多租户与权限约定：
- tenant_id 从 JWT 取，不接受客户端传参
- 医生只能访问自己接诊（doctor_id == 本人）或待接管队列中的会话
- 医生端越权访问返回 403（明确区分「无权限」，与患者端的 404 策略不同，便于定位）
- 确认 / 修正分诊写审计日志（TRIAGE_CONFIRM / TRIAGE_CORRECT）
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import AuditActionType, AuditResult
from app.common.error_codes import (
    FORBIDDEN,
    NOT_FOUND,
    SESSION_CORRECTION_REASON,
    SESSION_CORRECTION_SAME,
    SESSION_TAKEN_BY_OTHER,
    SESSION_TRIAGE_NOT_READY,
)
from app.common.exceptions import BizError
from app.models import (
    Appointment,
    AuditLog,
    Dept,
    EmrRecord,
    KbEntry,
    MdtCouncil,
    Patient,
    Session,
    SessionMessage,
    TriageCorrection,
    TriageResult,
    User,
)
from app.services.consent_service import has_active_consent
from app.services import drug_safety_service

# 排序字段白名单（防对未索引字段排序）
_SORT_WHITELIST = {"started_time", "inquiry_rounds"}
# 可评价职称（副主任医师及以上，修正记录可作评测样本 AC-F19-2）
_EVAL_TITLES = {"副主任医师", "主任医师"}


def _patient_display(patient: Patient | None) -> str:
    """医生端患者展示名：优先姓名，其次账号，最后院内编号。"""
    if patient is None:
        return "患者"
    if patient.real_name:
        return patient.real_name
    if patient.account:
        return patient.account
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
    result: AuditResult = AuditResult.SUCCESS,
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
            result=result.value,
            detail_json=detail,
        )
    )


async def _get_doctor_session(
    db: AsyncSession, session_id: str, doctor_id: str, tenant_id: str
) -> Session:
    """取会话并校验：必须存在该医生名下的预约号源。"""
    session = await db.scalar(
        select(Session).where(Session.id == session_id, Session.tenant_id == tenant_id)
    )
    if session is None:
        raise BizError(NOT_FOUND)
    appointment = await db.scalar(
        select(Appointment.id).where(
            Appointment.tenant_id == tenant_id,
            Appointment.session_id == session_id,
            Appointment.doctor_id == doctor_id,
            Appointment.status.in_(["BOOKED", "COMPLETED", "NOSHOW"]),
        )
    )
    if appointment is None:
        raise BizError(FORBIDDEN, "该患者未预约当前医生的号源")
    return session


async def _doctor_has_patient(
    db: AsyncSession, *, tenant_id: str, doctor_id: str, patient_id: str
) -> bool:
    """医生是否拥有该患者的预约号源。"""
    found = await db.scalar(
        select(Appointment.id).where(
            Appointment.tenant_id == tenant_id,
            Appointment.patient_id == patient_id,
            Appointment.doctor_id == doctor_id,
            Appointment.status.in_(["BOOKED", "COMPLETED", "NOSHOW"]),
        ).limit(1)
    )
    return found is not None


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
    """预约接诊列表：默认返回今天起、预约了当前医生号源的患者。"""
    if sort_by not in _SORT_WHITELIST:
        sort_by = "started_time"
    order_col = getattr(Session, sort_by)
    order = (order_col.desc() if sort_order == "desc" else order_col.asc(),)

    if encounter_date:
        day = datetime.strptime(encounter_date, "%Y-%m-%d").date()
        date_cond = Appointment.schedule_date == day
    else:
        day = datetime.now(UTC).date()
        date_cond = Appointment.schedule_date >= day

    conds = [
        Appointment.tenant_id == tenant_id,
        Appointment.doctor_id == doctor_id,
        date_cond,
        Appointment.session_id.is_not(None),
        Appointment.status.in_(["BOOKED", "COMPLETED", "NOSHOW"]),
    ]
    if status:
        conds.append(Session.status == status)

    if not encounter_date:
        order = (Appointment.schedule_date.asc(), Appointment.time_slot.asc())

    base = (
        select(Appointment, Session)
        .join(Session, Session.id == Appointment.session_id)
        .where(*conds)
    )
    total = await db.scalar(
        select(func.count(func.distinct(Appointment.id)))
        .select_from(Appointment)
        .join(Session, Session.id == Appointment.session_id)
        .where(*conds)
    )
    pairs = (
        await db.execute(
            base.order_by(*order).offset((page - 1) * size).limit(size)
        )
    ).all()

    patient_ids = {s.patient_id for _, s in pairs}
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
            "appointment_id": a.id,
            "schedule_date": a.schedule_date.isoformat(),
            "time_slot": a.time_slot,
            "patient_display": _patient_display(patients.get(s.patient_id)),
            "patient_hash": (
                patients[s.patient_id].patient_hash
                if s.patient_id in patients
                else None
            ),
            "chief_complaint": s.chief_complaint,
            "status": s.status,
            "risk_flag": s.risk_flag == "1",
            "inquiry_rounds": s.inquiry_rounds,
            "started_time": s.started_time.isoformat() if s.started_time else None,
        }
        for a, s in pairs
    ]
    return {"total": total or 0, "page": page, "size": size, "items": items}


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
    consent_ok = await has_active_consent(
        db, tenant_id=tenant_id, patient_id=session.patient_id
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
            "real_name": patient.real_name if patient else None,
            "account": patient.account if patient else None,
            "age": patient.age if patient else None,
            "gender": _gender_label(patient.gender) if patient else None,
        },
        "triage_status": {
            "has_result": triage is not None,
            "route": triage.route if triage else None,
            "doctor_confirmed": triage.doctor_confirmed == "1" if triage else False,
        },
        "symptom_timeline": [],
        "consent_granted": consent_ok,
        "consent_scope_label": "历史病历调阅" if consent_ok else None,
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
    session = await _get_doctor_session(db, session_id, doctor_id, tenant_id)

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
        "completeness_rate": float(emr.completeness_rate or 0),
        "subjective": {
            "chief_complaint": session.chief_complaint or "",
            "present_illness": emr.subjective or "",
            "past_history": _as_list(entities.get("past_history")),
            "allergy": _as_list(entities.get("allergy")),
        },
        "objective": {
            "collected_vitals": [],
            "note": emr.objective or "本次为线上预问诊，未采集体格检查数据",
        },
        "assessment": {
            "differential_directions": differential,
            "note": emr.assessment or "以上为鉴别方向参考，不构成诊断",
        },
        "plan": {
            "recommended_depts": (
                [triage.candidates_json[0].get("dept_name", "")]
                if triage and triage.candidates_json
                else []
            ),
            "suggested_workup": [],
            "note": emr.plan or "以上为就诊建议，不构成诊断",
        },
        "disclaimer": "本系统仅提供分诊建议，不构成医学诊断。请以医生面诊为准。",
        "generated_time": emr.create_time.isoformat() if emr.create_time else None,
    }


async def _load_guidelines(
    db: AsyncSession, tenant_id: str, dept_code: str, limit: int = 3
) -> list[dict]:
    """加载某科室的结构化指南推荐意见（GUIDELINE_REC）。"""
    rows = (
        await db.scalars(
            select(KbEntry)
            .where(
                KbEntry.tenant_id == tenant_id,
                KbEntry.kb_type == "GUIDELINE_REC",
                KbEntry.dept_code == dept_code,
                KbEntry.is_active == "1",
            )
            .limit(limit)
        )
    ).all()
    refs = []
    for r in rows:
        j = r.content_json or {}
        refs.append(
            {
                "disease_name": j.get("disease_name", ""),
                "recommendation": j.get("recommendation", "") or r.content or "",
                "evidence_level": j.get("evidence_level", ""),
                "strength": j.get("recommendation_strength", ""),
                "population": j.get("population", ""),
                "source": j.get("guideline_source", ""),
            }
        )
    return refs


async def get_diagnosis(
    db: AsyncSession,
    *,
    session_id: str,
    doctor_id: str,
    tenant_id: str,
    include_mdt: bool,
) -> dict:
    """鉴别诊断候选与依据 + 用药禁忌校验。"""
    session = await _get_doctor_session(db, session_id, doctor_id, tenant_id)

    triage = await db.scalar(
        select(TriageResult).where(TriageResult.session_id == session_id)
    )
    if triage is None:
        raise BizError(SESSION_TRIAGE_NOT_READY)

    candidates = []
    for i, c in enumerate(triage.candidates_json or []):
        dept_code = c.get("dept_code", "")
        candidates.append(
            {
                "rank": i + 1,
                "dept_code": dept_code,
                "dept_name": c.get("dept_name", ""),
                "confidence": float(c.get("confidence", 0)),
                "hit_symptoms": [c.get("reason", "")] if c.get("reason") else [],
                "guideline_refs": await _load_guidelines(db, tenant_id, dept_code),
                "kg_paths": c.get("kg_paths", []),
                "kg_disease_hits": c.get("kg_disease_hits", 0),
            }
        )

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
        "drug_safety": await drug_safety_service.check_drug_safety(
            db,
            tenant_id=tenant_id,
            patient_id=session.patient_id,
            session_id=session_id,
        ),
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

    # 并发安全：两个医生同时点确认时，只有第一个 UPDATE 能命中 doctor_confirmed='0'
    now = datetime.now(UTC)
    updated = await db.execute(
        update(TriageResult)
        .where(
            TriageResult.id == triage.id,
            TriageResult.tenant_id == tenant_id,
            TriageResult.doctor_confirmed == "0",
        )
        .values(doctor_confirmed="1", confirmed_time=now)
    )
    if getattr(updated, "rowcount", 0) == 1:
        triage.doctor_confirmed = "1"
        triage.confirmed_time = now
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
    else:
        # 已被并发请求确认：回读结果，保持幂等语义
        await db.refresh(triage)

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
    # 锁住会话行：修正与后台落库/他人确认并发时，以先到者为准
    session = (
        await db.scalar(
            select(Session)
            .where(Session.id == session_id, Session.tenant_id == tenant_id)
            .with_for_update()
        )
        or session
    )

    if session.doctor_id != doctor_id:
        raise BizError(SESSION_TAKEN_BY_OTHER)
    if len(reason.strip()) < 10:
        raise BizError(SESSION_CORRECTION_REASON)

    triage = await db.scalar(
        select(TriageResult)
        .where(
            TriageResult.session_id == session_id,
            TriageResult.tenant_id == tenant_id,
        )
        .with_for_update()
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


async def get_patient_emr(
    db: AsyncSession, *, patient_id: str, doctor_id: str, tenant_id: str
) -> dict:
    """查阅患者既往病历（预问诊病历列表）。"""
    patient = await db.scalar(
        select(Patient).where(Patient.id == patient_id, Patient.tenant_id == tenant_id)
    )
    if patient is None:
        raise BizError(NOT_FOUND)
    if not await _doctor_has_patient(
        db, tenant_id=tenant_id, doctor_id=doctor_id, patient_id=patient_id
    ):
        raise BizError(FORBIDDEN, "该患者未预约当前医生的号源")

    consent_ok = await has_active_consent(
        db, tenant_id=tenant_id, patient_id=patient_id
    )
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
        detail=None if consent_ok else {"reason": "consent_required"},
        result=AuditResult.SUCCESS if consent_ok else AuditResult.FAILURE,
    )
    await db.commit()

    if not consent_ok:
        # 无授权不报错、不泄露有无病历：返回空列表并显式告知前端
        return {
            "patient_id": patient_id,
            "patient_display": _patient_display(patient),
            "consent_required": True,
            "records": [],
        }

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
        "consent_required": False,
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
    if not await _doctor_has_patient(
        db, tenant_id=tenant_id, doctor_id=doctor_id, patient_id=patient_id
    ):
        raise BizError(FORBIDDEN, "该患者未预约当前医生的号源")

    consent_ok = await has_active_consent(
        db, tenant_id=tenant_id, patient_id=patient_id
    )
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
        detail=None if consent_ok else {"reason": "consent_required"},
        result=AuditResult.SUCCESS if consent_ok else AuditResult.FAILURE,
    )
    await db.commit()

    if not consent_ok:
        return {
            "patient_id": patient_id,
            "patient_display": _patient_display(patient),
            "consent_required": True,
            "total": 0,
            "page": page,
            "size": size,
            "items": [],
        }

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
        return {
            "patient_id": patient_id,
            "patient_display": _patient_display(patient),
            "consent_required": False,
            "total": 0,
            "page": page,
            "size": size,
            "items": [],
        }

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
    return {
        "patient_id": patient_id,
        "patient_display": _patient_display(patient),
        "consent_required": False,
        "total": total,
        "page": page,
        "size": size,
        "items": items,
    }


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
