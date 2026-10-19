"""患者预约挂号：科室 → 医生 → 日期 → 时段 → 号源。

当前没有独立排班表，按「医生 + 未来 7 天 + 固定时段 + 容量」动态生成号源，
再用预约记录实时扣减；同一号源通过 PostgreSQL advisory lock 串行化，避免超卖。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.error_codes import (
    APPT_DUPLICATE,
    APPT_NO_SLOT,
    APPT_NOT_CANCELLABLE,
    APPT_NOT_FOUND,
    APPT_SLOT_GONE,
    APPT_SLOT_TAKEN,
    NOT_FOUND,
)
from app.common.exceptions import BizError
from app.models import Appointment, Dept, Session, User

SLOT_CAPACITY = 3
SLOT_TIMES = (
    "08:30-09:00",
    "09:00-09:30",
    "09:30-10:00",
    "10:00-10:30",
    "14:00-14:30",
    "14:30-15:00",
    "15:00-15:30",
    "15:30-16:00",
)
_TITLE_RANK = {"主任医师": 0, "副主任医师": 1, "主治医师": 2, "住院医师": 3}


def _dates() -> list[date]:
    today = date.today()
    return [today + timedelta(days=i) for i in range(1, 8)]


def _is_expert(title: str | None) -> bool:
    return title in {"主任医师", "副主任医师"}


def _weekday(value: date) -> str:
    return "周" + "一二三四五六日"[value.weekday()]


def _dept_name(dept: Dept | None, code: str) -> str:
    return dept.dept_name if dept else code


def _status_label(status: str) -> str:
    return {
        "BOOKED": "已预约",
        "CANCELLED": "已取消",
        "COMPLETED": "已完成",
        "NOSHOW": "爽约",
    }.get(status, status)


async def list_slots(
    db: AsyncSession, *, tenant_id: str, dept_code: str
) -> dict:
    dept = await db.scalar(
        select(Dept).where(Dept.tenant_id == tenant_id, Dept.dept_code == dept_code)
    )
    if dept is None:
        raise BizError(NOT_FOUND, "科室不存在")

    doctors = list(
        (
            await db.scalars(
                select(User).where(
                    User.tenant_id == tenant_id,
                    User.role == "DOCTOR",
                    User.status == "1",
                    User.dept_code == dept_code,
                )
            )
        ).all()
    )
    doctors.sort(key=lambda d: (_TITLE_RANK.get(d.title or "", 9), d.real_name or d.account))
    if not doctors:
        raise BizError(APPT_NO_SLOT)

    dates = _dates()
    booked_rows = (
        await db.execute(
            select(
                Appointment.doctor_id,
                Appointment.schedule_date,
                Appointment.time_slot,
                func.count().label("cnt"),
            )
            .where(
                Appointment.tenant_id == tenant_id,
                Appointment.dept_code == dept_code,
                Appointment.schedule_date.in_(dates),
                Appointment.status == "BOOKED",
            )
            .group_by(Appointment.doctor_id, Appointment.schedule_date, Appointment.time_slot)
        )
    ).all()
    booked = {
        (row.doctor_id, row.schedule_date, row.time_slot): int(row.cnt)
        for row in booked_rows
    }

    days = []
    for day in dates:
        doctor_items = []
        for doctor in doctors:
            slots = []
            for slot in SLOT_TIMES:
                used = booked.get((doctor.id, day, slot), 0)
                remaining = max(0, SLOT_CAPACITY - used)
                slots.append(
                    {
                        "time_slot": slot,
                        "capacity": SLOT_CAPACITY,
                        "remaining": remaining,
                        "available": remaining > 0,
                    }
                )
            doctor_items.append(
                {
                    "doctor_id": doctor.id,
                    "doctor_name": doctor.real_name or doctor.account,
                    "title": doctor.title or "医师",
                    "is_expert": _is_expert(doctor.title),
                    "slots": slots,
                }
            )
        days.append({"date": day.isoformat(), "weekday": _weekday(day), "doctors": doctor_items})

    return {
        "dept_code": dept_code,
        "dept_name": _dept_name(dept, dept_code),
        "dates": days,
    }


async def create_appointment(
    db: AsyncSession,
    *,
    tenant_id: str,
    patient_id: str,
    session_id: str | None,
    dept_code: str,
    doctor_id: str,
    schedule_date: date,
    time_slot: str,
) -> dict:
    if schedule_date not in _dates() or time_slot not in SLOT_TIMES:
        raise BizError(APPT_SLOT_GONE)

    doctor = await db.scalar(
        select(User).where(
            User.id == doctor_id,
            User.tenant_id == tenant_id,
            User.role == "DOCTOR",
            User.status == "1",
            User.dept_code == dept_code,
        )
    )
    if doctor is None:
        raise BizError(APPT_SLOT_GONE)

    if session_id:
        session = await db.scalar(
            select(Session).where(
                Session.id == session_id,
                Session.tenant_id == tenant_id,
                Session.patient_id == patient_id,
            )
        )
        if session is None:
            raise BizError(NOT_FOUND, "会话不存在")

    duplicate = await db.scalar(
        select(Appointment).where(
            Appointment.tenant_id == tenant_id,
            Appointment.patient_id == patient_id,
            Appointment.doctor_id == doctor_id,
            Appointment.schedule_date == schedule_date,
            Appointment.time_slot == time_slot,
            Appointment.status == "BOOKED",
        )
    )
    if duplicate is not None:
        raise BizError(APPT_DUPLICATE)

    # 同一号源串行化：并发请求不能同时看到剩余 1 个号。
    lock_key = f"{tenant_id}:{doctor_id}:{schedule_date.isoformat()}:{time_slot}"
    await db.execute(select(func.pg_advisory_xact_lock(func.hashtext(lock_key))))
    used = await db.scalar(
        select(func.count()).select_from(Appointment).where(
            Appointment.tenant_id == tenant_id,
            Appointment.doctor_id == doctor_id,
            Appointment.schedule_date == schedule_date,
            Appointment.time_slot == time_slot,
            Appointment.status == "BOOKED",
        )
    )
    if (used or 0) >= SLOT_CAPACITY:
        raise BizError(APPT_SLOT_TAKEN)

    appointment = Appointment(
        tenant_id=tenant_id,
        appointment_no=f"A{datetime.now():%Y%m%d%H%M%S}{uuid4().hex[:6]}",
        session_id=session_id,
        patient_id=patient_id,
        dept_code=dept_code,
        doctor_id=doctor_id,
        schedule_date=schedule_date,
        time_slot=time_slot,
        slot_id=f"{doctor_id}:{schedule_date.isoformat()}:{time_slot}",
        status="BOOKED",
    )
    db.add(appointment)
    await db.commit()
    dept = await db.scalar(
        select(Dept).where(Dept.tenant_id == tenant_id, Dept.dept_code == dept_code)
    )
    return _appointment_dict(appointment, doctor, dept)


def _appointment_dict(
    appointment: Appointment, doctor: User | None, dept: Dept | None
) -> dict:
    return {
        "appointment_id": appointment.id,
        "appointment_no": appointment.appointment_no,
        "session_id": appointment.session_id,
        "dept_code": appointment.dept_code,
        "dept_name": dept.dept_name if dept else appointment.dept_code,
        "doctor_id": appointment.doctor_id,
        "doctor_name": (doctor.real_name or doctor.account) if doctor else None,
        "doctor_title": doctor.title if doctor else None,
        "schedule_date": appointment.schedule_date.isoformat(),
        "time_slot": appointment.time_slot,
        "status": appointment.status,
        "status_label": _status_label(appointment.status),
        "can_cancel": appointment.status == "BOOKED",
        "create_time": appointment.create_time.isoformat() if appointment.create_time else None,
    }


async def list_appointments(
    db: AsyncSession, *, tenant_id: str, patient_id: str
) -> dict:
    rows = list(
        (
            await db.scalars(
                select(Appointment)
                .where(
                    Appointment.tenant_id == tenant_id,
                    Appointment.patient_id == patient_id,
                )
                .order_by(Appointment.schedule_date.desc(), Appointment.create_time.desc())
                .limit(20)
            )
        ).all()
    )
    doctor_ids = {r.doctor_id for r in rows if r.doctor_id}
    dept_codes = {r.dept_code for r in rows}
    doctors = {}
    if doctor_ids:
        doctors = {
            u.id: u
            for u in (
                await db.scalars(
                    select(User).where(
                        User.tenant_id == tenant_id, User.id.in_(doctor_ids)
                    )
                )
            ).all()
        }
    depts = {}
    if dept_codes:
        depts = {
            d.dept_code: d
            for d in (
                await db.scalars(
                    select(Dept).where(
                        Dept.tenant_id == tenant_id, Dept.dept_code.in_(dept_codes)
                    )
                )
            ).all()
        }
    return {
        "items": [
            _appointment_dict(
                r,
                doctors.get(r.doctor_id) if r.doctor_id else None,
                depts.get(r.dept_code),
            )
            for r in rows
        ]
    }


async def cancel_appointment(
    db: AsyncSession, *, tenant_id: str, patient_id: str, appointment_id: str
) -> dict:
    appointment = await db.scalar(
        select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.tenant_id == tenant_id,
            Appointment.patient_id == patient_id,
        )
    )
    if appointment is None:
        raise BizError(APPT_NOT_FOUND)
    if appointment.status != "BOOKED":
        raise BizError(APPT_NOT_CANCELLABLE)
    appointment.status = "CANCELLED"
    appointment.cancel_time = datetime.now()
    await db.commit()
    doctor = await db.scalar(select(User).where(User.id == appointment.doctor_id))
    dept = await db.scalar(
        select(Dept).where(
            Dept.tenant_id == tenant_id, Dept.dept_code == appointment.dept_code
        )
    )
    return _appointment_dict(appointment, doctor, dept)
