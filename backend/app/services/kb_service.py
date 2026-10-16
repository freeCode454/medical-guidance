"""知识库管理服务：条目 CRUD、变更历史、检索测试台、黄金查询、发布与入库。

知识库条目是唯一真相，向量库（Milvus）由此派生。变更写历史（只追加）与审计。
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import AuditActionType, AuditResult, ChangeType
from app.common.error_codes import (
    KB_ENTRY_CODE_EXISTS,
    KB_ENTRY_INVALID,
    KB_ENTRY_NOT_FOUND,
    KB_ENTRY_REF_MISSING,
    KB_GOLDEN_NOT_FOUND,
    KB_SEARCH_EMPTY,
)
from app.common.exceptions import BizError
from app.models import (
    AuditLog,
    Dept,
    GoldenQuery,
    KbEntry,
    KbEntryHistory,
    KbIngestTask,
    KbPublish,
)

_SORT_WHITELIST = {"update_time", "entry_code", "create_time"}


async def _write_audit(
    db: AsyncSession,
    *,
    tenant_id: str,
    actor_id: str,
    actor_role: str,
    target_type: str,
    target_id: str | None,
    detail: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            tenant_id=tenant_id,
            actor_id=actor_id,
            actor_role=actor_role,
            action_type=AuditActionType.KB_CHANGE.value,
            target_type=target_type,
            target_id=target_id,
            result=AuditResult.SUCCESS.value,
            detail_json=detail,
        )
    )


def _entry_to_dict(e: KbEntry) -> dict:
    return {
        "entry_id": e.id,
        "entry_code": e.entry_code,
        "kb_type": e.kb_type,
        "title": e.title,
        "dept_code": e.dept_code,
        "status": e.status,
        "is_active": e.is_active == "1",
        "entry_version": e.entry_version,
        "update_time": e.update_time.isoformat() if e.update_time else None,
    }


# ---- 条目 CRUD -----------------------------------------------------------


async def list_entries(
    db: AsyncSession,
    *,
    tenant_id: str,
    page: int,
    size: int,
    kb_type: str | None,
    dept_code: str | None,
    status: str | None,
    is_active: bool | None,
    keyword: str | None,
    sort_by: str,
    sort_order: str,
) -> dict:
    if sort_by not in _SORT_WHITELIST:
        sort_by = "update_time"
    order_col = getattr(KbEntry, sort_by)
    order = order_col.desc() if sort_order == "desc" else order_col.asc()

    conds = [KbEntry.tenant_id == tenant_id]
    if kb_type:
        conds.append(KbEntry.kb_type == kb_type)
    if dept_code:
        conds.append(KbEntry.dept_code == dept_code)
    if status:
        conds.append(KbEntry.status == status)
    if is_active is not None:
        conds.append(KbEntry.is_active == ("1" if is_active else "0"))
    if keyword:
        conds.append(or_(KbEntry.title.ilike(f"%{keyword}%"), KbEntry.content.ilike(f"%{keyword}%")))

    total = await db.scalar(select(func.count()).select_from(KbEntry).where(*conds))
    rows = (
        await db.scalars(
            select(KbEntry).where(*conds).order_by(order).offset((page - 1) * size).limit(size)
        )
    ).all()
    return {
        "total": total,
        "page": page,
        "size": size,
        "items": [_entry_to_dict(e) for e in rows],
    }


async def create_entry(
    db: AsyncSession, *, tenant_id: str, actor_id: str, actor_role: str, payload: dict
) -> dict:
    entry_code = payload["entry_code"]
    kb_type = payload["kb_type"]
    content = payload["content"]
    dept_code = payload.get("dept_code")

    # 条目标识唯一
    exists = await db.scalar(
        select(KbEntry).where(KbEntry.tenant_id == tenant_id, KbEntry.entry_code == entry_code)
    )
    if exists is not None:
        raise BizError(KB_ENTRY_CODE_EXISTS)

    # 引用完整性：dept_code 须存在
    if dept_code:
        dept = await db.scalar(
            select(Dept).where(Dept.tenant_id == tenant_id, Dept.dept_code == dept_code)
        )
        if dept is None:
            raise BizError(KB_ENTRY_REF_MISSING)

    if not content.strip():
        raise BizError(KB_ENTRY_INVALID, "正文内容不能为空")

    entry = KbEntry(
        tenant_id=tenant_id,
        kb_type=kb_type,
        entry_code=entry_code,
        title=payload.get("title"),
        content=content,
        content_json=payload.get("content_json"),
        dept_code=dept_code,
        icd10_codes=payload.get("icd10_codes"),
        age_group=payload.get("age_group", "all"),
        gender=payload.get("gender", "0"),
        source=payload.get("source"),
        entry_version=payload.get("entry_version"),
        status="0",  # 草稿
        is_active="0",
        create_by=actor_id,
    )
    db.add(entry)
    await db.flush()

    # 变更历史（CREATE）
    history = KbEntryHistory(
        tenant_id=tenant_id,
        entry_id=entry.id,
        entry_code=entry_code,
        change_type=ChangeType.CREATE.value,
        after_json={"kb_type": kb_type, "title": payload.get("title"), "content": content},
        operator=actor_id,
    )
    db.add(history)

    await _write_audit(
        db, tenant_id=tenant_id, actor_id=actor_id, actor_role=actor_role,
        target_type="kb_entry", target_id=entry.id, detail={"entry_code": entry_code},
    )
    await db.commit()

    return {
        "entry_id": entry.id,
        "entry_code": entry_code,
        "status": "0",
        "is_active": False,
        "history_id": history.id,
        "created_time": entry.create_time.isoformat() if entry.create_time else None,
    }


async def get_entry(db: AsyncSession, *, tenant_id: str, entry_id: str) -> dict:
    entry = await db.scalar(
        select(KbEntry).where(KbEntry.id == entry_id, KbEntry.tenant_id == tenant_id)
    )
    if entry is None:
        raise BizError(KB_ENTRY_NOT_FOUND)
    return {
        **_entry_to_dict(entry),
        "content": entry.content,
        "content_json": entry.content_json,
        "icd10_codes": entry.icd10_codes,
        "age_group": entry.age_group,
        "gender": entry.gender,
        "source": entry.source,
    }


async def update_entry(
    db: AsyncSession, *, tenant_id: str, actor_id: str, actor_role: str, entry_id: str, payload: dict
) -> dict:
    entry = await db.scalar(
        select(KbEntry).where(KbEntry.id == entry_id, KbEntry.tenant_id == tenant_id)
    )
    if entry is None:
        raise BizError(KB_ENTRY_NOT_FOUND)

    before = _entry_to_dict(entry)
    changed_fields: list[str] = []
    for field in ("title", "content", "content_json", "dept_code", "icd10_codes", "age_group", "gender", "source", "entry_version"):
        if field in payload and getattr(entry, field) != payload[field]:
            setattr(entry, field, payload[field])
            changed_fields.append(field)

    if not changed_fields:
        return {"entry_id": entry_id, "changed_fields": [], "message": "无变更"}

    entry.update_by = actor_id
    entry.update_time = datetime.now(timezone.utc)

    history = KbEntryHistory(
        tenant_id=tenant_id,
        entry_id=entry.id,
        entry_code=entry.entry_code,
        change_type=ChangeType.UPDATE.value,
        before_json=before,
        after_json=_entry_to_dict(entry),
        changed_fields=changed_fields,
        operator=actor_id,
    )
    db.add(history)
    await _write_audit(
        db, tenant_id=tenant_id, actor_id=actor_id, actor_role=actor_role,
        target_type="kb_entry", target_id=entry.id,
        detail={"changed_fields": changed_fields},
    )
    await db.commit()
    return {"entry_id": entry_id, "changed_fields": changed_fields}


async def toggle_entry(
    db: AsyncSession, *, tenant_id: str, actor_id: str, actor_role: str, entry_id: str
) -> dict:
    entry = await db.scalar(
        select(KbEntry).where(KbEntry.id == entry_id, KbEntry.tenant_id == tenant_id)
    )
    if entry is None:
        raise BizError(KB_ENTRY_NOT_FOUND)

    # 启停：is_active 翻转（0 ↔ 1）
    entry.is_active = "0" if entry.is_active == "1" else "1"
    entry.update_by = actor_id
    entry.update_time = datetime.now(timezone.utc)

    history = KbEntryHistory(
        tenant_id=tenant_id,
        entry_id=entry.id,
        entry_code=entry.entry_code,
        change_type=ChangeType.ENABLE.value if entry.is_active == "1" else ChangeType.DISABLE.value,
        operator=actor_id,
    )
    db.add(history)
    await _write_audit(
        db, tenant_id=tenant_id, actor_id=actor_id, actor_role=actor_role,
        target_type="kb_entry", target_id=entry.id, detail={"is_active": entry.is_active},
    )
    await db.commit()
    return {"entry_id": entry_id, "is_active": entry.is_active == "1"}


async def list_entry_history(
    db: AsyncSession, *, tenant_id: str, entry_id: str, page: int, size: int
) -> dict:
    conds = [KbEntryHistory.tenant_id == tenant_id, KbEntryHistory.entry_id == entry_id]
    total = await db.scalar(select(func.count()).select_from(KbEntryHistory).where(*conds))
    rows = (
        await db.scalars(
            select(KbEntryHistory)
            .where(*conds)
            .order_by(KbEntryHistory.create_time.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
    ).all()
    return {
        "total": total,
        "page": page,
        "size": size,
        "items": [
            {
                "history_id": h.id,
                "change_type": h.change_type,
                "changed_fields": h.changed_fields,
                "operator": h.operator,
                "create_time": h.create_time.isoformat() if h.create_time else None,
            }
            for h in rows
        ],
    }


# ---- 检索测试台与黄金查询 -----------------------------------------------


async def retrieval_test(
    db: AsyncSession,
    *,
    tenant_id: str,
    query: str,
    mode: str,
    embedder,
    store,
    limit: int,
) -> dict:
    """检索测试台：主诉 → 候选科室召回（三路结果可对比）。"""
    if not query.strip():
        raise BizError(KB_SEARCH_EMPTY)

    from app.services.triage_service import recall_depts

    depts = await recall_depts(
        embedder, store, complaint=query, tenant_id=tenant_id, mode=mode, limit=limit
    )
    return {
        "query": query,
        "retrieval_mode": mode,
        "candidates": [
            {"dept_code": d["dept_code"], "dept_name": d.get("dept_name", ""), "score": round(d["score"], 4)}
            for d in depts
        ],
    }


async def list_golden_queries(
    db: AsyncSession, *, tenant_id: str, page: int, size: int, category: str | None, is_active: bool | None
) -> dict:
    conds = [GoldenQuery.tenant_id == tenant_id]
    if category:
        conds.append(GoldenQuery.category == category)
    if is_active is not None:
        conds.append(GoldenQuery.is_active == ("1" if is_active else "0"))
    total = await db.scalar(select(func.count()).select_from(GoldenQuery).where(*conds))
    rows = (
        await db.scalars(
            select(GoldenQuery).where(*conds).order_by(GoldenQuery.create_time.desc())
            .offset((page - 1) * size).limit(size)
        )
    ).all()
    return {
        "total": total,
        "page": page,
        "size": size,
        "items": [
            {
                "query_id": q.id,
                "query_code": q.query_code,
                "query_text": q.query_text,
                "expect_depts": q.expect_depts,
                "expect_route": q.expect_route,
                "category": q.category,
                "is_active": q.is_active == "1",
            }
            for q in rows
        ],
    }


async def create_golden_query(
    db: AsyncSession, *, tenant_id: str, actor_id: str, payload: dict
) -> dict:
    query_code = payload.get("query_code") or f"GQ-{uuid4().hex[:8]}"
    gq = GoldenQuery(
        tenant_id=tenant_id,
        query_code=query_code,
        query_text=payload["query_text"],
        expect_depts=payload.get("expect_depts"),
        expect_not_depts=payload.get("expect_not_depts"),
        expect_route=payload.get("expect_route"),
        category=payload.get("category"),
        description=payload.get("description"),
        is_active="1",
        create_by=actor_id,
    )
    db.add(gq)
    await db.commit()
    return {
        "query_id": gq.id,
        "query_code": gq.query_code,
        "is_active": True,
    }


# ---- 发布与入库（简化：记录型） -----------------------------------------


async def publish_kb(
    db: AsyncSession, *, tenant_id: str, actor_id: str, version_tag: str | None
) -> dict:
    """发布知识库：生成版本快照记录（实际向量化入库由 ingest 任务承担）。"""
    tag = version_tag or f"kb-v{datetime.now(timezone.utc):%Y.%m.%d.%H%M%S}"
    exists = await db.scalar(
        select(KbPublish).where(KbPublish.tenant_id == tenant_id, KbPublish.version_tag == tag)
    )
    if exists is not None:
        from app.common.error_codes import KB_VERSION_EXISTS
        raise BizError(KB_VERSION_EXISTS)

    entry_count = await db.scalar(
        select(func.count()).select_from(KbEntry).where(
            KbEntry.tenant_id == tenant_id, KbEntry.status == "1"
        )
    )
    publish = KbPublish(
        tenant_id=tenant_id,
        version_tag=tag,
        entry_count=entry_count or 0,
        published_by=actor_id,
    )
    db.add(publish)
    await db.commit()
    return {
        "publish_id": publish.id,
        "version_tag": tag,
        "entry_count": publish.entry_count,
        "published_time": publish.published_time.isoformat() if publish.published_time else None,
    }


async def list_publishes(db: AsyncSession, *, tenant_id: str, page: int, size: int) -> dict:
    conds = [KbPublish.tenant_id == tenant_id]
    total = await db.scalar(select(func.count()).select_from(KbPublish).where(*conds))
    rows = (
        await db.scalars(
            select(KbPublish).where(*conds).order_by(KbPublish.published_time.desc())
            .offset((page - 1) * size).limit(size)
        )
    ).all()
    return {
        "total": total,
        "page": page,
        "size": size,
        "items": [
            {
                "publish_id": p.id,
                "version_tag": p.version_tag,
                "entry_count": p.entry_count,
                "published_by": p.published_by,
                "published_time": p.published_time.isoformat() if p.published_time else None,
            }
            for p in rows
        ],
    }


async def trigger_ingest(db: AsyncSession, *, tenant_id: str, actor_id: str) -> dict:
    """触发知识库入库：创建异步任务记录（实际向量化入库后续接入 Celery）。"""
    task_no = f"ING{datetime.now(timezone.utc):%Y%m%d%H%M%S}{uuid4().hex[:4]}"
    total = await db.scalar(
        select(func.count()).select_from(KbEntry).where(
            KbEntry.tenant_id == tenant_id, KbEntry.is_active == "1"
        )
    )
    task = KbIngestTask(
        tenant_id=tenant_id,
        task_no=task_no,
        status="PENDING",
        stage="VALIDATE",
        total_count=total or 0,
        triggered_by=actor_id,
    )
    db.add(task)
    await db.commit()
    return {"task_id": task.id, "task_no": task_no, "status": "PENDING", "total_count": task.total_count}


async def list_ingest_tasks(db: AsyncSession, *, tenant_id: str, page: int, size: int) -> dict:
    conds = [KbIngestTask.tenant_id == tenant_id]
    total = await db.scalar(select(func.count()).select_from(KbIngestTask).where(*conds))
    rows = (
        await db.scalars(
            select(KbIngestTask).where(*conds).order_by(KbIngestTask.create_time.desc())
            .offset((page - 1) * size).limit(size)
        )
    ).all()
    return {
        "total": total,
        "page": page,
        "size": size,
        "items": [
            {
                "task_id": t.id,
                "task_no": t.task_no,
                "status": t.status,
                "stage": t.stage,
                "progress": t.progress,
                "total_count": t.total_count,
                "added_count": t.added_count,
                "failed_count": t.failed_count,
            }
            for t in rows
        ],
    }


async def get_ingest_task(db: AsyncSession, *, tenant_id: str, task_id: str) -> dict:
    task = await db.scalar(
        select(KbIngestTask).where(KbIngestTask.id == task_id, KbIngestTask.tenant_id == tenant_id)
    )
    if task is None:
        from app.common.error_codes import KB_INGEST_NOT_FOUND
        raise BizError(KB_INGEST_NOT_FOUND)
    return {
        "task_id": task.id,
        "task_no": task.task_no,
        "status": task.status,
        "stage": task.stage,
        "progress": task.progress,
        "total_count": task.total_count,
        "added_count": task.added_count,
        "updated_count": task.updated_count,
        "failed_count": task.failed_count,
        "error_json": task.error_json,
        "started_time": task.started_time.isoformat() if task.started_time else None,
        "finished_time": task.finished_time.isoformat() if task.finished_time else None,
    }
