"""应用启动入口。

Windows 默认的 ProactorEventLoop 不被 psycopg 异步连接支持，
而 LangGraph 的 PostgreSQL 检查点依赖 psycopg 异步驱动。
统一从本入口启动（``python -m app``），在创建事件循环前切到 SelectorEventLoop。

Linux/macOS 上等价于 ``uvicorn app.main:app``。
"""
from __future__ import annotations

import asyncio
import os
import sys


def _configure_event_loop() -> None:
    if sys.platform == "win32":
        policy_cls = getattr(asyncio, "WindowsSelectorEventLoopPolicy", None)
        if policy_cls is not None:
            asyncio.set_event_loop_policy(policy_cls())


def main() -> None:
    _configure_event_loop()
    import uvicorn

    # 不用 uvicorn.run：它在 Windows 上会强制使用 ProactorEventLoop
    # （见 uvicorn.loops.asyncio.asyncio_loop_factory），psycopg 异步连接不支持。
    config = uvicorn.Config(
        "app.main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )
    server = uvicorn.Server(config)
    asyncio.run(server.serve())


if __name__ == "__main__":
    main()
