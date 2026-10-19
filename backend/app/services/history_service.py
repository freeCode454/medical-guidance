"""既往病历上下文：在患者授权后，把历史就诊摘要提供给问诊/病历生成。

只读取患者已授权（EMR_READ）的本院病历，不跨租户、不返回未授权数据。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EmrDocument, EmrRecord, Session
from app.services.consent_service import has_active_consent


async def load_history_context(
    db: AsyncSession,
    *,
    tenant_id: str,
    patient_id: str,
    exclude_session_id: str | None = None,
) -> dict | None:
    """返回 {summary, past_history, allergy, visits}；未授权或无历史返回 None。"""
    if not await has_active_consent(db, tenant_id=tenant_id, patient_id=patient_id):
        return None

    stmt = (
        select(EmrRecord)
        .where(EmrRecord.tenant_id == tenant_id, EmrRecord.patient_id == patient_id)
        .order_by(EmrRecord.create_time.desc())
        .limit(3)
    )
    if exclude_session_id:
        stmt = stmt.where(EmrRecord.session_id != exclude_session_id)
    records = list((await db.scalars(stmt)).all())
    docs = list(
        (
            await db.scalars(
                select(EmrDocument)
                .where(
                    EmrDocument.tenant_id == tenant_id,
                    EmrDocument.patient_id == patient_id,
                )
                .order_by(EmrDocument.record_time.desc())
                .limit(2)
            )
        ).all()
    )
    if not records and not docs:
        return None

    session_ids = [r.session_id for r in records]
    sessions = {}
    if session_ids:
        rows = (
            await db.scalars(
                select(Session).where(
                    Session.tenant_id == tenant_id, Session.id.in_(session_ids)
                )
            )
        ).all()
        sessions = {s.id: s for s in rows}

    past_history: list[str] = []
    allergy: list[str] = []
    visits: list[dict] = []
    lines: list[str] = []

    for rec in records:
        soap = rec.soap_json or {}
        entities = soap.get("entities") or {}
        for item in entities.get("past_history") or []:
            if item and item not in past_history:
                past_history.append(str(item))
        for item in entities.get("allergy") or []:
            if item and item not in allergy:
                allergy.append(str(item))
        session = sessions.get(rec.session_id)
        complaint = (session.chief_complaint if session else None) or ""
        when = rec.create_time.strftime("%Y-%m-%d") if rec.create_time else "历史"
        visits.append(
            {
                "date": when,
                "chief_complaint": complaint,
                "generate_status": rec.generate_status,
            }
        )
        subjective = str(soap.get("subjective") or "")[:300]
        lines.append(f"- {when} 主诉：{complaint or '未记录'}")
        if subjective:
            lines.append(f"  主观资料摘要：{subjective}")

    for doc in docs:
        when = doc.record_time.strftime("%Y-%m-%d") if doc.record_time else "历史"
        content = (doc.doc_content or "")[:300]
        lines.append(f"- {when} {doc.doc_title or doc.doc_type}：{content}")

    if past_history:
        lines.append(f"既往史：{'、'.join(past_history[:10])}")
    if allergy:
        lines.append(f"过敏史：{'、'.join(allergy[:10])}")

    summary = "\n".join(lines)[:1500]
    return {
        "summary": summary,
        "past_history": past_history,
        "allergy": allergy,
        "visits": visits,
    }
