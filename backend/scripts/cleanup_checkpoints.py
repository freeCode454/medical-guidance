"""清理已结束会话的 LangGraph 检查点。

用法（在 backend 目录）：
    python scripts/cleanup_checkpoints.py --days 30
    python scripts/cleanup_checkpoints.py --days 30 --dry-run
    python scripts/cleanup_checkpoints.py --days 7 --limit 200

建议由 cron / Windows 任务计划程序按天调度；删除前可先用 --dry-run 核对数量。
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from app.common.database import AsyncSessionFactory
from app.config import settings
from app.services.checkpoint_maintenance import purge_finished_threads


def _selector_policy() -> None:
    import asyncio as _asyncio

    if sys.platform == "win32":
        policy_cls = getattr(_asyncio, "WindowsSelectorEventLoopPolicy", None)
        if policy_cls is not None:
            _asyncio.set_event_loop_policy(policy_cls())


async def _run(days: int, limit: int, dry_run: bool) -> None:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    async with (
        AsyncSessionFactory() as db,
        AsyncPostgresSaver.from_conn_string(settings.checkpoint_dsn) as saver,
    ):
        result = await purge_finished_threads(
            db, saver, days=days, limit=limit, dry_run=dry_run
        )
    print(
        f"cutoff={result['cutoff']} eligible={result['eligible']} "
        f"deleted={result['deleted']} dry_run={result['dry_run']}"
    )
    if dry_run and result["thread_ids"]:
        print("待清理会话：")
        for thread_id in result["thread_ids"]:
            print(f"  - {thread_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description="清理已结束会话的 LangGraph 检查点")
    parser.add_argument("--days", type=int, default=30, help="保留天数，默认 30")
    parser.add_argument("--limit", type=int, default=500, help="单次最多处理会话数，默认 500")
    parser.add_argument("--dry-run", action="store_true", help="只统计，不删除")
    args = parser.parse_args()
    _selector_policy()
    asyncio.run(_run(args.days, args.limit, args.dry_run))


if __name__ == "__main__":
    main()
