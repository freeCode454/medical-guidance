"""匿名患者身份：设备密钥只存指纹、低熵凭证被拒绝、旧明文记录自动迁移。"""
from __future__ import annotations

import hashlib
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.common.error_codes import BAD_REQUEST
from app.common.exceptions import BizError
from app.common.security import device_fingerprint
from app.config import settings
from app.models import Patient
from app.services import auth_service

SECRET = "a" * 64  # 模拟前端 32 字节随机数的十六进制串


def _db(existing: Patient | None = None) -> AsyncMock:
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=existing)
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    def _add(obj: object) -> None:
        if isinstance(obj, Patient):
            obj.id = "patient-1"

    db.add = MagicMock(side_effect=_add)
    return db


@pytest.mark.asyncio
async def test_new_device_is_stored_as_fingerprint_only() -> None:
    db = _db()
    result = await auth_service.create_patient_session(
        db, SECRET, client_type="H5", channel="DIRECT"
    )

    added: Patient = db.add.call_args.args[0]
    assert added.device_id == device_fingerprint(SECRET)
    assert added.device_id != SECRET
    assert added.patient_hash == hashlib.sha256(
        f"{settings.default_tenant_id}:{SECRET}".encode()
    ).hexdigest()
    assert result.device_id == SECRET  # 明文只回给客户端，不落库


@pytest.mark.asyncio
async def test_short_legacy_device_id_is_rejected() -> None:
    db = _db()
    with pytest.raises(BizError) as exc:
        await auth_service.create_patient_session(
            db, "dev_abc123", client_type="H5", channel="DIRECT"
        )
    assert exc.value.code is BAD_REQUEST
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_existing_plaintext_device_record_is_migrated() -> None:
    patient = Patient(
        id="patient-1",
        tenant_id=settings.default_tenant_id,
        patient_hash="h",
        device_id="dev_legacy_plaintext_value_should_be_replaced",
    )
    db = _db(existing=patient)
    result = await auth_service.create_patient_session(
        db, SECRET, client_type="H5", channel="DIRECT"
    )

    assert patient.device_id == device_fingerprint(SECRET)
    assert result.patient_id == "patient-1"
