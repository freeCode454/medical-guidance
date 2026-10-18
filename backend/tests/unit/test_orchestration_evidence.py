"""编排落库证据：症状摘要/风险/图谱路径必须在进程重启后仍可还原。"""
from __future__ import annotations

from app.services.orchestration import _build_evidence


def test_build_evidence_keeps_collected_slots() -> None:
    result = {
        "chief_complaint": "肚子疼三天了",
        "entities": {
            "duration": "三天",
            "location": "肚脐周围",
            "nature": "绞痛",
            "accompanying": ["腹泻"],
            "allergy": [],
        },
        "risk_flag": False,
        "triage_result": {
            "recommended_depts": [
                {"dept_code": "DIG", "kg_paths": [{"path": "腹痛→胃炎→消化内科"}]}
            ]
        },
    }
    evidence = _build_evidence(result)

    assert evidence["symptom_summary"]["duration"] == "三天"
    assert evidence["symptom_summary"]["accompanying"] == ["腹泻"]
    assert "allergy" not in evidence["symptom_summary"]  # 空值不落快照
    assert evidence["kg_paths"] == [{"path": "腹痛→胃炎→消化内科"}]
    assert evidence["risk_flag"] is False


def test_build_evidence_marks_risk_reason() -> None:
    evidence = _build_evidence(
        {
            "chief_complaint": "胸口疼冒冷汗",
            "risk_flag": True,
            "risk_reason": "命中胸痛伴出汗",
            "triage_result": {},
        }
    )
    assert evidence["risk_flag"] is True
    assert evidence["risk_reason"] == "命中胸痛伴出汗"
    assert evidence["kg_paths"] == []
