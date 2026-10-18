"""PostgreSQL 检查点：挂起状态必须跨连接/进程实例恢复。

需要真实 PostgreSQL；默认 CI 只跑 tests/unit。
运行：pytest tests/integration -m integration -q
"""
from __future__ import annotations

import asyncio
import os
from typing import TypedDict
from uuid import uuid4

import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

pytestmark = pytest.mark.integration

# 单测 conftest 会把 DATABASE_URL 指向假地址；集成测试显式用本机真实库
DSN = os.getenv(
    "CHECKPOINT_TEST_DSN",
    "postgresql://medguide:medguide@127.0.0.1:5440/medguide",
)


class State(TypedDict):
    value: int


def _node(state: State) -> dict:
    answer = interrupt("continue?")
    return {"value": state["value"] + int(answer)}


def _build(saver: AsyncPostgresSaver):
    graph = StateGraph(State)
    graph.add_node("ask", _node)
    graph.add_edge(START, "ask")
    graph.add_edge("ask", END)
    return graph.compile(checkpointer=saver)


def test_interrupt_survives_new_saver_instance() -> None:
    """用独立 asyncio.run 起 Selector 循环，避免 pytest-asyncio 自建 Proactor 循环。"""

    async def _run() -> None:
        config = {"configurable": {"thread_id": f"test-{uuid4().hex}"}}

        async with AsyncPostgresSaver.from_conn_string(DSN) as saver:
            await saver.setup()
            app = _build(saver)
            first = await app.ainvoke({"value": 1}, config)
            assert "__interrupt__" in first
            snapshot = await app.aget_state(config)
            assert snapshot.interrupts

        # 新连接 + 新编译实例，模拟服务重启
        async with AsyncPostgresSaver.from_conn_string(DSN) as saver:
            app = _build(saver)
            resumed = await app.ainvoke(Command(resume=5), config)
            assert resumed["value"] == 6

    asyncio.run(_run())
