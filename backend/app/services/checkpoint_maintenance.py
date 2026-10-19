"""检查点维护：清理已结束会话的 LangGraph 线程。

业务表里的会话结束后，`checkpoints/checkpoint_blobs/checkpoint_writes` 仍会保留，
长期运行会持续增长。这里提供可调度的清理用例，默认只处理已 FINISHED/CLOSED
且结束时间早于保留期的会话。
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import SessionStatus
from app.models import Session

_TERMINAL_STATUSES = (SessionStatus.FINISHED.value, SessionStatus.CLOSED.value)


async def purge_finished_threads(
    db: AsyncSession,
    saver: Any,
    *,
    days: int = 30,
    limit: int = 500,
    dry_run: bool = False,
) -> dict:
    """删除超过保留期的已结束会话检查点。

    ``saver`` 需要实现 ``adelete_thread(thread_id)``（AsyncPostgresSaver）。
    """
    if days < 1:
        raise ValueError("days 必须 >= 1")
    if not 1 <= limit <= 5000:
        raise ValueError("limit 必须在 1~5000 之间")

    cutoff = datetime.now(UTC) - timedelta(days=days)
    rows = (
        await db.scalars(
            select(Session.id)
            .where(
                Session.status.in_(_TERMINAL_STATUSES),
                Session.finished_time.is_not(None),
                Session.finished_time < cutoff,
            )
            .order_by(Session.finished_time)
            .limit(limit)
        )
    ).all()

    thread_ids = list(rows)
    if not dry_run:
        for thread_id in thread_ids:
            await saver.adelete_thread(thread_id)

    return {
        "cutoff": cutoff.isoformat(),
        "eligible": len(thread_ids),
        "deleted": 0 if dry_run else len(thread_ids),
        "dry_run": dry_run,
        "thread_ids": thread_ids,
    }
