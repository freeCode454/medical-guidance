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
from app.retrieval.collections import KB_CASE, KB_DRUG, KB_GUIDELINE, KB_ICD10, KB_SYMPTOM

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


_PLANS: tuple[tuple[Any, tuple[str, ...], str], ...] = (
    (KB_DEPT, ("DEPT_EXPERTISE",), "dept"),
    (KB_SYMPTOM, ("SYMPTOM_DISEASE",), "symptom"),
    (KB_GUIDELINE, ("GUIDELINE", "GUIDELINE_REC"), "guideline"),
    (KB_ICD10, ("ICD-10",), "icd10"),
    (KB_DRUG, ("DRUG_SAFETY",), "drug"),
    (KB_CASE, ("CASE",), "case"),
)


def _vector_id(kind: str, entry: KbEntry) -> str:
    if kind == "dept":
        return f"dept_{entry.dept_code}"
    return f"kb_{entry.id}"


def _row_for(kind: str, entry: KbEntry, text: str, embedding: Any, tenant_id: str) -> dict:
    meta = entry.content_json or {}
    base = {
        "id": _vector_id(kind, entry),
        "dense": embedding.dense,
        "sparse": embedding.sparse or {},
        "text": text[:4000],
        "tenant_id": tenant_id,
    }
    if kind == "dept":
        base.update(dept_code=entry.dept_code, dept_name=(entry.title or entry.dept_code or "")[:64])
    elif kind == "symptom":
        base.update(
            dept_code=(entry.dept_code or "")[:32],
            icd10_code=((entry.icd10_codes or [""])[0])[:16],
            age_group=(entry.age_group or "all")[:16],
            gender=(entry.gender or "0")[:1],
        )
    elif kind == "guideline":
        base.update(
            icd10_code=((entry.icd10_codes or [""])[0])[:16],
            evidence_level=str(meta.get("evidence_level", ""))[:16],
            pub_year=str(meta.get("year", ""))[:8],
        )
    elif kind == "icd10":
        base.pop("tenant_id", None)  # ICD-10 全局共享，不分区
        base.update(chapter=str(meta.get("chapter", ""))[:64], alias=(entry.title or "")[:64])
    elif kind == "drug":
        base.update(
            drug_name=str(meta.get("drug_name") or entry.title or "")[:64],
            taboo_type=str(meta.get("severity", ""))[:16],
        )
    elif kind == "case":
        base.update(dept_code=(entry.dept_code or "")[:32], diagnosis=(entry.title or "")[:64])
    return base


async def _load_entries(
    db: AsyncSession, tenant_id: str, types: tuple[str, ...], dept_only: bool = False
) -> list[KbEntry]:
    conds = [
        KbEntry.tenant_id == tenant_id,
        KbEntry.kb_type.in_(types),
        KbEntry.is_active == "1",
        KbEntry.del_flag == "0",
    ]
    if dept_only:
        conds.extend([KbEntry.dept_code.is_not(None), ~KbEntry.dept_code.contains("-")])
    return list(
        (
            await db.scalars(
                select(KbEntry).where(*conds).order_by(KbEntry.entry_code)
            )
        ).all()
    )


async def rebuild_all_vectors(
    db: AsyncSession,
    *,
    tenant_id: str,
    embedder: Any,
    store: Any,
    progress_cb: Callable[[int], Awaitable[None]] | None = None,
) -> dict:
    """按知识类型重建全部向量集合（科室/疾病症状/指南/ICD/用药/病例）。"""
    plans: list[tuple[Any, str, list[KbEntry]]] = []
    for spec, types, kind in _PLANS:
        entries = await _load_entries(db, tenant_id, types, dept_only=kind == "dept")
        if entries:
            plans.append((spec, kind, entries))

    total = sum(len(entries) for _, _, entries in plans)
    if total == 0:
        raise BizError(KB_ENTRY_INVALID, "没有启用的知识条目，无法重建索引")

    upserted = deleted = done = 0
    for spec, kind, entries in plans:
        texts = [f"{e.title or e.entry_code}\n{(e.content or '')[:3800]}" for e in entries]
        # 只把前 240 字送进模型：知识条目的核心语义集中在开头，
        # 避免对 3000+ 字长文做完整 tokenize 导致入库耗时失控。
        embed_texts = [text[:240] for text in texts]
        embeddings = []
        for start in range(0, len(embed_texts), 32):
            batch = await embedder.embed(embed_texts[start : start + 32])
            embeddings.extend(batch)
            done += len(batch)
            if progress_cb is not None:
                await progress_cb(20 + int(60 * done / total))

        rows = [
            _row_for(kind, entry, texts[idx], emb, tenant_id)
            for idx, (entry, emb) in enumerate(zip(entries, embeddings, strict=False))
        ]
        if not spec.has_sparse:
            for row in rows:
                row.pop("sparse", None)
        await asyncio.to_thread(store.ensure_ready, spec)
        await asyncio.to_thread(store.upsert, spec, rows)
        filter_expr = "" if kind == "icd10" else f'tenant_id == "{tenant_id}"'
        existing = await asyncio.to_thread(store.list_ids, spec, filter_expr)
        active_ids = {row["id"] for row in rows}
        stale = sorted(set(existing) - active_ids)
        if stale:
            await asyncio.to_thread(store.delete, spec, stale)
            await asyncio.to_thread(store.flush, spec)
        upserted += len(rows)
        deleted += len(stale)

    return {
        "total": total,
        "upserted": upserted,
        "deleted": deleted,
        "collections": [spec.name for spec, _, _ in plans],
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
            result = await rebuild_all_vectors(
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
