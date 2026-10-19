"""医生接管/确认的并发回归测试（真实 PostgreSQL）。

对应工程质量报告 P1：接管、确认已用条件 UPDATE / 行锁，但缺真实 PG 并发用例。
运行：pytest tests/integration -m integration -q
"""
from __future__ import annotations

import asyncio
import os
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.common.enums import SessionStatus
from app.common.exceptions import BizError
from app.models import AuditLog, Patient, Session, Tenant, TriageResult, User
from app.services import doctor_service

pytestmark = pytest.mark.integration

DSN = os.getenv(
    "INTEGRATION_TEST_DSN",
    "postgresql://medguide:medguide@127.0.0.1:5440/medguide",
).replace("postgresql://", "postgresql+asyncpg://")


def _ids() -> dict[str, str]:
    tenant_id = uuid4().hex
    return {
        "tenant_id": tenant_id,
        "doctor_a": uuid4().hex,
        "doctor_b": uuid4().hex,
        "patient_id": uuid4().hex,
        "session_id": uuid4().hex,
        "triage_id": uuid4().hex,
    }


async def _seed(*, status: str, doctor_id: str | None, with_triage: bool) -> tuple[object, dict[str, str]]:
    engine = create_async_engine(DSN, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    ids = _ids()
    async with factory() as db:
        db.add(
            Tenant(
                id=ids["tenant_id"],
                tenant_code=f"it-{ids['tenant_id'][:12]}",
                tenant_name="并发回归测试机构",
            )
        )
        for key, account in (("doctor_a", "doctor-a"), ("doctor_b", "doctor-b")):
            db.add(
                User(
                    id=ids[key],
                    tenant_id=ids["tenant_id"],
                    account=f"{account}-{ids['tenant_id'][:8]}",
                    real_name=account,
                    role="DOCTOR",
                    title="副主任医师",
                    credential_hash="test-only",
                )
            )
        db.add(
            Patient(
                id=ids["patient_id"],
                tenant_id=ids["tenant_id"],
                patient_hash=uuid4().hex * 2,
                age=35,
                gender="1",
            )
        )
        db.add(
            Session(
                id=ids["session_id"],
                tenant_id=ids["tenant_id"],
                session_no=f"IT-{ids['session_id'][:16]}",
                patient_id=ids["patient_id"],
                doctor_id=doctor_id,
                status=status,
                risk_flag="0",
                inquiry_rounds=1,
                chief_complaint="头痛三天",
            )
        )
        if with_triage:
            db.add(
                TriageResult(
                    id=ids["triage_id"],
                    tenant_id=ids["tenant_id"],
                    session_id=ids["session_id"],
                    candidates_json=[{"dept_code": "NEU", "dept_name": "神经内科", "confidence": 0.91}],
                    confidence=0.91,
                    route="DIRECT",
                    retrieval_mode="HYBRID",
                    doctor_confirmed="0",
                )
            )
        await db.commit()
    return engine, ids


async def _cleanup(engine, ids: dict[str, str]) -> None:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        # mg_audit_log 是只追加表（触发器禁止 DELETE），测试租户的审计记录保留
        await db.execute(delete(TriageResult).where(TriageResult.tenant_id == ids["tenant_id"]))
        await db.execute(delete(Session).where(Session.tenant_id == ids["tenant_id"]))
        await db.execute(delete(Patient).where(Patient.tenant_id == ids["tenant_id"]))
        await db.execute(delete(User).where(User.tenant_id == ids["tenant_id"]))
        await db.execute(delete(Tenant).where(Tenant.id == ids["tenant_id"]))
        await db.commit()
    await engine.dispose()


async def _takeover(factory, *, session_id: str, doctor_id: str, tenant_id: str):
    async with factory() as db:
        try:
            return ("ok", await doctor_service.takeover_session(
                db, session_id=session_id, doctor_id=doctor_id, tenant_id=tenant_id
            ))
        except BizError as exc:
            return ("error", exc.code.code)


async def _confirm(factory, *, session_id: str, doctor_id: str, tenant_id: str):
    async with factory() as db:
        try:
            return ("ok", await doctor_service.confirm_triage(
                db,
                session_id=session_id,
                doctor_id=doctor_id,
                tenant_id=tenant_id,
                note="并发回归",
            ))
        except BizError as exc:
            return ("error", exc.code.code)


def test_concurrent_takeover_only_one_doctor_wins() -> None:
    async def _run() -> None:
        engine, ids = await _seed(
            status=SessionStatus.PENDING_TAKEOVER.value, doctor_id=None, with_triage=False
        )
        factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            results = await asyncio.gather(
                _takeover(factory, session_id=ids["session_id"], doctor_id=ids["doctor_a"], tenant_id=ids["tenant_id"]),
                _takeover(factory, session_id=ids["session_id"], doctor_id=ids["doctor_b"], tenant_id=ids["tenant_id"]),
            )
            winners = [r for r in results if r[0] == "ok"]
            losers = [r for r in results if r[0] == "error"]
            assert len(winners) == 1, results
            assert len(losers) == 1, results
            assert losers[0][1] in {20008, 20009}  # 已被接管 / 不在待接管状态

            winner_id = winners[0][1]["doctor_id"]
            async with factory() as db:
                row = await db.scalar(select(Session).where(Session.id == ids["session_id"]))
                assert row is not None
                assert row.doctor_id == winner_id
                assert row.status == SessionStatus.TAKEN_OVER.value
        finally:
            await _cleanup(engine, ids)

    asyncio.run(_run())


def test_concurrent_confirm_is_idempotent() -> None:
    async def _run() -> None:
        engine, ids = await _seed(
            status=SessionStatus.PENDING_TAKEOVER.value,
            doctor_id=None,
            with_triage=True,
        )
        # 先让 doctor_a 接管
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as db:
            await doctor_service.takeover_session(
                db,
                session_id=ids["session_id"],
                doctor_id=ids["doctor_a"],
                tenant_id=ids["tenant_id"],
            )
        try:
            results = await asyncio.gather(
                _confirm(factory, session_id=ids["session_id"], doctor_id=ids["doctor_a"], tenant_id=ids["tenant_id"]),
                _confirm(factory, session_id=ids["session_id"], doctor_id=ids["doctor_a"], tenant_id=ids["tenant_id"]),
            )
            assert all(r[0] == "ok" for r in results), results
            async with factory() as db:
                row = await db.scalar(
                    select(TriageResult).where(TriageResult.session_id == ids["session_id"])
                )
                assert row is not None
                assert row.doctor_confirmed == "1"
                audits = (
                    await db.scalars(
                        select(AuditLog).where(
                            AuditLog.tenant_id == ids["tenant_id"],
                            AuditLog.action_type == "TRIAGE_CONFIRM",
                        )
                    )
                ).all()
                assert len(audits) == 1
        finally:
            await _cleanup(engine, ids)

    asyncio.run(_run())
