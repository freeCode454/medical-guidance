"""病史调阅授权：授予/续期/撤回，以及医生侧无授权时的空结果。"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models import EmrRecord, Patient, PatientConsent
from app.services import consent_service, doctor_service


def _patient() -> Patient:
    return Patient(
        id="p1",
        tenant_id="t1",
        patient_hash="h1",
        patient_no="P0001",
        device_id="f" * 64,
    )


def _consent(expires_in_days: int = 30) -> PatientConsent:
    now = datetime.now(UTC)
    return PatientConsent(
        id="c1",
        tenant_id="t1",
        patient_id="p1",
        consent_scope="EMR_READ",
        consent_time=now,
        expire_time=now + timedelta(days=expires_in_days),
        consent_channel="PATIENT_H5",
    )


def _scalars(items: list[object]) -> AsyncMock:
    result = MagicMock()
    result.all.return_value = items
    return AsyncMock(return_value=result)


@pytest.mark.asyncio
async def test_grant_creates_consent_when_none_exists() -> None:
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=None)
    db.add = MagicMock()
    db.commit = AsyncMock()

    data = await consent_service.grant_consent(
        db, tenant_id="t1", patient_id="p1", scope="EMR_READ", expire_days=90
    )

    added: PatientConsent = db.add.call_args.args[0]
    assert added.consent_scope == "EMR_READ"
    assert added.consent_channel == "PATIENT_H5"
    assert added.expire_time is not None
    assert data["scope"] == "EMR_READ"


@pytest.mark.asyncio
async def test_grant_extends_existing_consent() -> None:
    existing = _consent(expires_in_days=1)
    old_expire = existing.expire_time
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=existing)
    db.commit = AsyncMock()

    await consent_service.grant_consent(
        db, tenant_id="t1", patient_id="p1", scope="EMR_READ", expire_days=180
    )

    assert existing.expire_time is not None
    assert existing.expire_time > old_expire


@pytest.mark.asyncio
async def test_revoke_is_idempotent() -> None:
    consent = _consent()
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=consent)
    db.commit = AsyncMock()

    first = await consent_service.revoke_consent(
        db, tenant_id="t1", patient_id="p1", consent_id="c1"
    )
    first_time = consent.revoke_time
    second = await consent_service.revoke_consent(
        db, tenant_id="t1", patient_id="p1", consent_id="c1"
    )

    assert first["revoke_time"] is not None
    assert second["revoke_time"] == first_time
    assert db.commit.await_count == 1  # 第二次无需再提交


@pytest.mark.asyncio
async def test_doctor_history_requires_consent() -> None:
    db = AsyncMock()
    db.scalar = AsyncMock(side_effect=[_patient(), None])
    db.add = MagicMock()
    db.commit = AsyncMock()

    data = await doctor_service.get_patient_emr(
        db, patient_id="p1", doctor_id="d1", tenant_id="t1"
    )

    assert data["consent_required"] is True
    assert data["records"] == []
    db.scalars.assert_not_called()


@pytest.mark.asyncio
async def test_doctor_history_returns_records_with_consent() -> None:
    emr = EmrRecord(
        id="e1",
        tenant_id="t1",
        session_id="s1",
        patient_id="p1",
        subjective="腹痛三天",
        generate_status="SUCCESS",
        schema_version="1.0",
        create_time=datetime.now(UTC),
    )
    db = AsyncMock()
    db.scalar = AsyncMock(side_effect=[_patient(), _consent()])
    db.scalars = _scalars([emr])
    db.add = MagicMock()
    db.commit = AsyncMock()

    data = await doctor_service.get_patient_emr(
        db, patient_id="p1", doctor_id="d1", tenant_id="t1"
    )

    assert data["consent_required"] is False
    assert data["records"][0]["emr_record_id"] == "e1"


@pytest.mark.asyncio
async def test_summaries_require_consent() -> None:
    db = AsyncMock()
    db.scalar = AsyncMock(side_effect=[_patient(), None])
    db.add = MagicMock()
    db.commit = AsyncMock()

    data = await doctor_service.list_patient_summaries(
        db, patient_id="p1", doctor_id="d1", tenant_id="t1", page=1, size=10
    )

    assert data["consent_required"] is True
    assert data["items"] == []
