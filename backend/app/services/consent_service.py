"""患者授权服务：病史调阅的授予、查询、撤回与有效性判断。

合规约定（03 文档 mg_patient_consent / AC-F10-1）：
- 医生调阅**历史**病历必须有患者有效授权；本次问诊的治疗关系不在此列
- 授权有范围（scope）、有效期与撤回时间，任一不满足即视为无效
- 没有授权时接口返回空列表 + ``consent_required``，而不是报错（避免泄露"有无病历"）
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.error_codes import NOT_FOUND
from app.common.exceptions import BizError
from app.models import PatientConsent

EMR_READ = "EMR_READ"
DEFAULT_EXPIRE_DAYS = 180


def _serialize(consent: PatientConsent) -> dict:
    return {
        "consent_id": consent.id,
        "scope": consent.consent_scope,
        "consent_time": consent.consent_time,
        "expire_time": consent.expire_time,
        "revoke_time": consent.revoke_time,
        "channel": consent.consent_channel,
    }


async def _active_consent(
    db: AsyncSession, *, tenant_id: str, patient_id: str, scope: str
) -> PatientConsent | None:
    now = datetime.now(UTC)
    return await db.scalar(
        select(PatientConsent)
        .where(
            PatientConsent.tenant_id == tenant_id,
            PatientConsent.patient_id == patient_id,
            PatientConsent.consent_scope == scope,
            PatientConsent.revoke_time.is_(None),
            or_(
                PatientConsent.expire_time.is_(None),
                PatientConsent.expire_time > now,
            ),
        )
        .order_by(PatientConsent.consent_time.desc())
        .limit(1)
    )


async def has_active_consent(
    db: AsyncSession,
    *,
    tenant_id: str,
    patient_id: str,
    scope: str = EMR_READ,
) -> bool:
    """是否存在有效授权（未撤回、未过期）。"""
    return await _active_consent(
        db, tenant_id=tenant_id, patient_id=patient_id, scope=scope
    ) is not None


async def grant_consent(
    db: AsyncSession,
    *,
    tenant_id: str,
    patient_id: str,
    scope: str,
    session_id: str | None = None,
    expire_days: int = DEFAULT_EXPIRE_DAYS,
) -> dict:
    """授予/续期授权。同一 scope 已有有效授权时顺延有效期，不重复创建。"""
    now = datetime.now(UTC)
    expire_time = now + timedelta(days=expire_days)

    existing = await _active_consent(
        db, tenant_id=tenant_id, patient_id=patient_id, scope=scope
    )
    if existing is not None:
        existing.expire_time = expire_time
        await db.commit()
        return _serialize(existing)

    consent = PatientConsent(
        tenant_id=tenant_id,
        patient_id=patient_id,
        session_id=session_id,
        consent_scope=scope,
        consent_time=now,
        expire_time=expire_time,
        consent_channel="PATIENT_H5",
    )
    db.add(consent)
    await db.commit()
    return _serialize(consent)


async def list_consents(
    db: AsyncSession, *, tenant_id: str, patient_id: str
) -> list[dict]:
    """患者查看自己的授权记录（含已撤回/已过期，便于审计）。"""
    rows = (
        await db.scalars(
            select(PatientConsent)
            .where(
                PatientConsent.tenant_id == tenant_id,
                PatientConsent.patient_id == patient_id,
            )
            .order_by(PatientConsent.consent_time.desc())
        )
    ).all()
    return [_serialize(item) for item in rows]


async def revoke_consent(
    db: AsyncSession, *, tenant_id: str, patient_id: str, consent_id: str
) -> dict:
    """撤回授权。重复撤回保持幂等。"""
    consent = await db.scalar(
        select(PatientConsent).where(
            PatientConsent.id == consent_id,
            PatientConsent.tenant_id == tenant_id,
            PatientConsent.patient_id == patient_id,
        )
    )
    if consent is None:
        raise BizError(NOT_FOUND)
    if consent.revoke_time is None:
        consent.revoke_time = datetime.now(UTC)
        await db.commit()
    return _serialize(consent)
