"""患者视图：病历与分诊结果必须返回真实生成内容，而不是写死的占位符。"""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.models import EmrRecord, Session, TriageResult
from app.services import session_service


def _session() -> Session:
    return Session(
        id="s1",
        tenant_id="t1",
        patient_id="p1",
        session_no="S20261018001",
        chief_complaint="肚子疼三天了，还拉肚子",
        status="FINISHED",
        risk_flag="0",
        inquiry_rounds=2,
    )


def _emr() -> EmrRecord:
    return EmrRecord(
        id="e1",
        tenant_id="t1",
        session_id="s1",
        patient_id="p1",
        subjective="S：脐周绞痛三天，伴腹泻。",
        objective="O：体温 36.8℃，无脱水貌。",
        assessment="A：鉴别消化系统疾病。",
        plan="P：建议消化内科就诊，完善血常规。",
        soap_json={
            "entities": {
                "allergy": ["青霉素"],
                "past_history": ["慢性胃炎"],
            }
        },
        generate_status="SUCCESS",
        schema_version="1.0",
        create_time=datetime.now(UTC),
    )


def _triage(route: str = "DIRECT") -> TriageResult:
    return TriageResult(
        id="tr1",
        tenant_id="t1",
        session_id="s1",
        candidates_json=[{"dept_code": "DIG", "dept_name": "消化内科", "confidence": 0.92}],
        confidence=0.92,
        route=route,
        evidence_json={
            "symptom_summary": {
                "chief_complaint": "肚子疼三天了，还拉肚子",
                "duration": "三天",
                "location": "肚脐周围",
                "nature": "绞痛",
                "accompanying": ["腹泻"],
            },
            "risk_reason": "命中胸痛伴出汗",
        },
        create_time=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_patient_emr_uses_generated_sections() -> None:
    db = AsyncMock()
    db.scalar = AsyncMock(side_effect=[_session(), _emr(), _triage()])

    data = await session_service.get_emr(db, "s1", {"sub": "p1", "tenant_id": "t1"})

    assert data["subjective"]["chief_complaint"] == "肚子疼三天了，还拉肚子"
    assert "脐周绞痛" in data["subjective"]["present_illness"]
    assert data["subjective"]["allergy"] == ["青霉素"]
    assert data["subjective"]["past_history"] == ["慢性胃炎"]
    assert "36.8" in data["objective"]["note"]
    assert "消化内科" in data["plan"]["recommended_depts"]
    assert "血常规" in data["plan"]["note"]
    assert data["assessment"] is None  # R01：患者视图不得出现评估段


@pytest.mark.asyncio
async def test_patient_triage_returns_summary_and_rounds() -> None:
    db = AsyncMock()
    db.scalar = AsyncMock(side_effect=[_session(), _triage()])

    data = await session_service.get_triage_result(
        db, "s1", {"sub": "p1", "tenant_id": "t1"}
    )

    assert data.inquiry_rounds == 2
    assert data.symptom_summary.duration == "三天"
    assert data.symptom_summary.accompanying == ["腹泻"]
    assert data.recommended_depts[0].dept_code == "DIG"
    assert data.emergency_guidance is None


@pytest.mark.asyncio
async def test_emergency_triage_exposes_guidance() -> None:
    db = AsyncMock()
    db.scalar = AsyncMock(side_effect=[_session(), _triage(route="EMERGENCY")])

    data = await session_service.get_triage_result(
        db, "s1", {"sub": "p1", "tenant_id": "t1"}
    )

    assert data.emergency_guidance is not None
    assert data.emergency_guidance.triggered is True
    assert data.emergency_guidance.emergency_phone == "120"
    assert data.emergency_guidance.recommended_dept == "急诊科"
