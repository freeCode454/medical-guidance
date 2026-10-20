"""患者端「我的」：个人资料、历史病历摘要。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Appointment, Dept, EmrRecord, Patient, Session


async def get_profile(db: AsyncSession, *, tenant_id: str, patient_id: str) -> dict:
    patient = await db.scalar(
        select(Patient).where(
            Patient.id == patient_id,
            Patient.tenant_id == tenant_id,
            Patient.del_flag == "0",
        )
    )
    if patient is None:
        return {}

    session_count = await db.scalar(
        select(func.count()).select_from(Session).where(
            Session.tenant_id == tenant_id, Session.patient_id == patient_id
        )
    )
    appointment_count = await db.scalar(
        select(func.count()).select_from(Appointment).where(
            Appointment.tenant_id == tenant_id,
            Appointment.patient_id == patient_id,
            Appointment.status != "CANCELLED",
        )
    )
    record_count = await db.scalar(
        select(func.count()).select_from(EmrRecord).where(
            EmrRecord.tenant_id == tenant_id, EmrRecord.patient_id == patient_id
        )
    )
    gender_label = {"1": "男", "2": "女"}.get(patient.gender or "", "未知")
    return {
        "patient_id": patient.id,
        "account": patient.account,
        "real_name": patient.real_name,
        "patient_no": patient.patient_no,
        "age": patient.age,
        "gender": patient.gender,
        "gender_label": gender_label,
        "created_at": patient.create_time.isoformat() if patient.create_time else None,
        "last_login_time": patient.last_login_time.isoformat() if patient.last_login_time else None,
        "session_count": session_count or 0,
        "appointment_count": appointment_count or 0,
        "record_count": record_count or 0,
    }


async def update_profile(
    db: AsyncSession,
    *,
    tenant_id: str,
    patient_id: str,
    gender: str | None = None,
    age: int | None = None,
) -> dict:
    patient = await db.scalar(
        select(Patient).where(
            Patient.id == patient_id,
            Patient.tenant_id == tenant_id,
            Patient.del_flag == "0",
        )
    )
    if patient is None:
        return {}

    if gender is not None:
        patient.gender = {"男": "1", "女": "2"}.get(gender, patient.gender)
    if age is not None:
        patient.age = age
    await db.commit()
    return await get_profile(db, tenant_id=tenant_id, patient_id=patient_id)


async def list_records(
    db: AsyncSession, *, tenant_id: str, patient_id: str, limit: int = 20
) -> dict:
    records = list(
        (
            await db.scalars(
                select(EmrRecord)
                .where(
                    EmrRecord.tenant_id == tenant_id,
                    EmrRecord.patient_id == patient_id,
                )
                .order_by(EmrRecord.create_time.desc())
                .limit(limit)
            )
        ).all()
    )
    session_ids = {r.session_id for r in records}
    sessions = {}
    if session_ids:
        sessions = {
            s.id: s
            for s in (
                await db.scalars(
                    select(Session).where(
                        Session.tenant_id == tenant_id, Session.id.in_(session_ids)
                    )
                )
            ).all()
        }
    dept_codes = {s.dept_code for s in sessions.values() if s.dept_code}
    depts = {}
    if dept_codes:
        depts = {
            d.dept_code: d.dept_name
            for d in (
                await db.scalars(
                    select(Dept).where(
                        Dept.tenant_id == tenant_id, Dept.dept_code.in_(dept_codes)
                    )
                )
            ).all()
        }

    items = []
    for record in records:
        session = sessions.get(record.session_id)
        visit_time = (
            session.started_time if session and session.started_time else record.create_time
        )
        items.append(
            {
                "record_id": record.id,
                "session_id": record.session_id,
                "visit_time": visit_time.isoformat() if visit_time else None,
                "chief_complaint": session.chief_complaint if session else None,
                "dept_name": depts.get(session.dept_code) if session and session.dept_code else None,
                "summary": (record.subjective or "")[:160],
                "generate_status": record.generate_status,
            }
        )
    return {"total": len(items), "items": items}
