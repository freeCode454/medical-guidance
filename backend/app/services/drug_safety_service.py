"""用药禁忌校验（F47）。

只做事实比对，不输出处方或替代用药建议。数据来源：
- mg_kb_entry.kb_type = DRUG_SAFETY（当前启用条目）
- 本次预问诊病历中的过敏史/既往史
- 患者已授权历史病历中的过敏史/既往史
"""
from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EmrRecord, KbEntry, Patient
from app.services import history_service

_SEVERITY_RANK = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
_NEGATIVE_PREFIXES = ("否认", "无", "未发现", "没有")


def _normalize(value: object) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    # 去掉括号中的补充说明，避免“青霉素（皮试阳性）”无法匹配
    text = re.sub(r"[（(].*?[）)]", "", text)
    for token in ("过敏者", "过敏史", "过敏", "患者", "病史", "史"):
        text = text.replace(token, "")
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]", "", text)


def _as_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _terms(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if any(value.startswith(prefix) for prefix in _NEGATIVE_PREFIXES):
            continue
        normalized = _normalize(value)
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def _matches(value: object, terms: list[str]) -> str | None:
    normalized = _normalize(value)
    if not normalized:
        return None
    for term in terms:
        if len(term) < 2:
            continue
        if term == normalized or term in normalized or normalized in term:
            return term
    return None


def _age_matches(value: object, age: int | None) -> bool:
    if age is None:
        return False
    text = _normalize(value)
    if not text:
        return False
    if "儿童" in text and age < 18:
        return True
    if "老年" in text and age >= 65:
        return True
    under = re.search(r"(\d+)岁以下", text)
    if under and age < int(under.group(1)):
        return True
    above = re.search(r"(\d+)岁以上", text)
    if above and age >= int(above.group(1)):
        return True
    return False


async def _patient_context(
    db: AsyncSession,
    *,
    tenant_id: str,
    patient_id: str,
    session_id: str,
) -> tuple[list[str], list[str], Patient | None]:
    """返回（过敏史、基础疾病、患者）。"""
    allergies: list[str] = []
    conditions: list[str] = []

    current = await db.scalar(
        select(EmrRecord).where(
            EmrRecord.tenant_id == tenant_id,
            EmrRecord.session_id == session_id,
        )
    )
    if current and current.soap_json:
        entities = (current.soap_json or {}).get("entities") or {}
        allergies.extend(_as_list(entities.get("allergy")))
        conditions.extend(_as_list(entities.get("past_history")))

    try:
        history = await history_service.load_history_context(
            db,
            tenant_id=tenant_id,
            patient_id=patient_id,
            exclude_session_id=session_id,
        )
    except Exception:
        history = None
    if history:
        allergies.extend(history.get("allergy") or [])
        conditions.extend(history.get("past_history") or [])

    patient = await db.scalar(
        select(Patient).where(
            Patient.id == patient_id,
            Patient.tenant_id == tenant_id,
            Patient.del_flag == "0",
        )
    )
    return _terms(allergies), _terms(conditions), patient


def _note(checked: bool, allergy_known: bool, hits: int) -> str:
    if not checked:
        return "用药禁忌知识库暂不可用，请医生自行核对患者过敏史。"
    notes = [
        f"已完成过敏史与基础疾病比对，发现 {hits} 项禁忌提示。"
        if hits
        else "已完成过敏史与基础疾病比对，未发现已知禁忌冲突。",
        "校验结果仅供参考，最终用药决策由医生负责。",
    ]
    if not allergy_known:
        notes.append("患者过敏史未记录，请人工核对。")
    return "".join(notes)


async def check_drug_safety(
    db: AsyncSession,
    *,
    tenant_id: str,
    patient_id: str,
    session_id: str,
) -> dict:
    entries = list(
        (
            await db.scalars(
                select(KbEntry)
                .where(
                    KbEntry.tenant_id == tenant_id,
                    KbEntry.kb_type == "DRUG_SAFETY",
                    KbEntry.is_active == "1",
                    KbEntry.del_flag == "0",
                )
                .order_by(KbEntry.entry_code)
            )
        ).all()
    )
    if not entries:
        return {
            "checked": False,
            "allergy_known": False,
            "allergy_hits": [],
            "contraindication_hits": [],
            "note": _note(False, False, 0),
        }

    allergies, conditions, patient = await _patient_context(
        db, tenant_id=tenant_id, patient_id=patient_id, session_id=session_id
    )
    age = patient.age if patient else None

    allergy_hits: list[dict] = []
    contraindication_hits: list[dict] = []
    seen: set[tuple[str, str, str]] = set()

    for entry in entries:
        meta = entry.content_json or {}
        drug_name = str(meta.get("drug_name") or entry.title or "").strip()
        item = str(meta.get("allergy_item") or "").strip()
        population = str(meta.get("population") or "").strip()
        severity = str(meta.get("severity") or "MEDIUM").upper()
        suggestion = str(meta.get("suggestion") or "").strip()
        note = str(meta.get("note") or "").strip()
        if not drug_name or not (item or population):
            continue

        matched_allergy = _matches(item, allergies) or _matches(population, allergies)
        matched_condition = _matches(item, conditions) or _matches(population, conditions)
        matched_age = _age_matches(item, age) or _age_matches(population, age)

        if matched_allergy:
            bucket = allergy_hits
            kind = "allergy"
            matched = matched_allergy
        elif matched_condition or matched_age:
            bucket = contraindication_hits
            kind = "condition"
            matched = matched_condition or "年龄/人群"
        else:
            continue

        key = (drug_name, item or population, severity)
        if key in seen:
            continue
        seen.add(key)
        bucket.append(
            {
                "drug_name": drug_name,
                "allergy_item": item or population,
                "population": population or None,
                "severity": severity,
                "suggestion": suggestion or "请核对",
                "note": note or None,
                "entry_code": entry.entry_code,
                "match_type": kind,
                "matched": matched,
            }
        )

    def sort_hits(hits: list[dict]) -> list[dict]:
        return sorted(
            hits,
            key=lambda hit: (
                _SEVERITY_RANK.get(hit["severity"], 9),
                hit["drug_name"],
                hit["allergy_item"],
            ),
        )[:50]

    allergy_hits = sort_hits(allergy_hits)
    contraindication_hits = sort_hits(contraindication_hits)
    total = len(allergy_hits) + len(contraindication_hits)
    allergy_known = bool(allergies)

    return {
        "checked": True,
        "allergy_known": allergy_known,
        "allergy_hits": allergy_hits,
        "contraindication_hits": contraindication_hits,
        "note": _note(True, allergy_known, total),
    }
