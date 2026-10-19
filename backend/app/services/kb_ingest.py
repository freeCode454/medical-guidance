"""知识库入库 worker：把启用的科室专长条目同步到 Milvus。

当前分诊候选科室召回依赖 ``KB_DEPT`` 向量集合，而该集合原先由导入脚本从
Excel 生成。这里把「启用的 DEPT_EXPERTISE 条目」作为真相源，重建对应向量，
并删除已停用/已删除科室的旧向量，避免停用条目继续被召回。
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.database import AsyncSessionFactory
from app.common.error_codes import KB_ENTRY_INVALID
from app.common.exceptions import BizError
from app.models import KbEntry, KbIngestTask
from app.retrieval import KB_DEPT

_ACTIVE_DEPT_ENTRY = (
    KbEntry.kb_type == "DEPT_EXPERTISE",
    KbEntry.is_active == "1",
    KbEntry.del_flag == "0",
    KbEntry.dept_code.is_not(None),
    ~KbEntry.dept_code.contains("-"),  # 只索引一级科室，分诊不推荐亚专科
)


async def rebuild_dept_vectors(
    db: AsyncSession,
    *,
    tenant_id: str,
    embedder: Any,
    store: Any,
    progress_cb: Callable[[int], Awaitable[None]] | None = None,
) -> dict:
    """按启用的科室专长条目重建 KB_DEPT 向量。"""
    rows = (
        await db.scalars(
            select(KbEntry)
            .where(KbEntry.tenant_id == tenant_id, *_ACTIVE_DEPT_ENTRY)
            .order_by(KbEntry.entry_code)
        )
    ).all()

    by_dept: dict[str, KbEntry] = {}
    for entry in rows:
        if entry.dept_code:
            by_dept[entry.dept_code] = entry

    if not by_dept:
        raise BizError(KB_ENTRY_INVALID, "没有启用的科室专长条目，无法重建索引")

    codes = list(by_dept)
    entries = [by_dept[code] for code in codes]
    texts = [
        f"{e.title or e.dept_code}\n{(e.content or '')[:3800]}" for e in entries
    ]
    embeddings = []
    batch_size = 16
    for start in range(0, len(texts), batch_size):
        batch = await embedder.embed(texts[start : start + batch_size])
        embeddings.extend(batch)
        if progress_cb is not None:
            done = min(len(texts), start + len(batch))
            await progress_cb(20 + int(60 * done / len(texts)))

    vectors = []
    for idx, (code, entry, emb) in enumerate(zip(codes, entries, embeddings, strict=False)):
        dept_name = entry.title or code
        vectors.append(
            {
                "id": f"dept_{code}",
                "dense": emb.dense,
                "sparse": emb.sparse or {},
                "text": texts[idx][:4000],
                "dept_code": code,
                "dept_name": dept_name[:64],
                "tenant_id": tenant_id,
            }
        )

    await asyncio.to_thread(store.upsert, KB_DEPT, vectors)
    existing = await asyncio.to_thread(
        store.list_ids, KB_DEPT, f'tenant_id == "{tenant_id}"'
    )
    active_ids = {v["id"] for v in vectors}
    stale = sorted(set(existing) - active_ids)
    if stale:
        await asyncio.to_thread(store.delete, KB_DEPT, stale)
        await asyncio.to_thread(store.flush, KB_DEPT)

    return {
        "total": len(vectors),
        "upserted": len(vectors),
        "deleted": len(stale),
    }


async def run_ingest_task(
    task_id: str, *, tenant_id: str, embedder: Any, store: Any
) -> None:
    """后台执行入库任务，状态写回 mg_kb_ingest_task。"""
    async with AsyncSessionFactory() as db:
        task = await db.scalar(
            select(KbIngestTask).where(
                KbIngestTask.id == task_id, KbIngestTask.tenant_id == tenant_id
            )
        )
        if task is None:
            return
        current_task = task
        current_task.status = "RUNNING"
        current_task.stage = "EMBED"
        current_task.started_time = datetime.now(UTC)
        current_task.progress = 20
        await db.commit()

        async def _progress(value: int) -> None:
            current_task.progress = value
            await db.commit()

        try:
            result = await rebuild_dept_vectors(
                db,
                tenant_id=tenant_id,
                embedder=embedder,
                store=store,
                progress_cb=_progress,
            )
            current_task.status = "SUCCESS"
            current_task.stage = "VERIFY"
            current_task.progress = 100
            current_task.total_count = result["total"]
            current_task.added_count = result["upserted"]
            current_task.disabled_count = result["deleted"]
            current_task.finished_time = datetime.now(UTC)
            await db.commit()
        except Exception as exc:
            await db.rollback()
            task = await db.scalar(
                select(KbIngestTask).where(
                    KbIngestTask.id == task_id, KbIngestTask.tenant_id == tenant_id
                )
            )
            if task is not None:
                task.status = "FAILED"
                task.stage = "FAILED"
                task.progress = 100
                task.failed_count = 1
                task.error_json = {"message": str(exc)[:500]}
                task.finished_time = datetime.now(UTC)
                await db.commit()
