"""WebSocket 端点：对话流式通道。

对齐《04 文档》11 章。核心流程：

1. 校验一次性票据（ws_ticket），失败关闭码 4001
2. 订阅事件总线，发送 ``connected``
3. 并发两个协程：接收客户端消息（ping 心跳 / user_message）+ 转发图节点事件
4. 断开时取消订阅

``user_message`` 等价于 REST 发送消息接口：落库 + 触发编排图 resume。
"""
from __future__ import annotations

import asyncio
import itertools
import json
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.common.database import AsyncSessionFactory
from app.common.enums import MessageType
from app.common.ws_ticket import ticket_store
from app.services import session_service
from app.ws.event_bus import event_bus

router = APIRouter()

# 心跳与超时（04 文档 11.1 节）：客户端 30s 心跳，服务端 90s 无消息关闭
_CLIENT_HEARTBEAT_SECONDS = 30
_SERVER_TIMEOUT_SECONDS = 90


@router.websocket("/api/v1/ws/sessions/{session_id}")
async def ws_session(websocket: WebSocket, session_id: str, token: str = "") -> None:
    """对话流式通道：自动订阅该会话的全部事件。"""
    # 1. 校验票据（一次性）
    info = ticket_store.verify(token, resource_type="SESSION", resource_id=session_id)
    if info is None:
        await websocket.close(code=4001, reason="票据无效或已过期")
        return

    await websocket.accept()
    queue = event_bus.subscribe(session_id)
    seq_iter = itertools.count(1)
    last_active = time.time()

    async def send(event_type: str, data: dict) -> None:
        """按连接内序号包装并发送事件。"""
        await websocket.send_json(
            {
                "type": event_type,
                "seq": next(seq_iter),
                "ts": int(time.time()),
                "data": data,
            }
        )

    async def handle_user_message(raw: str) -> None:
        """处理客户端发来的用户消息（等价 REST 发送消息）。"""
        nonlocal last_active
        last_active = time.time()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return
        if data.get("type") != "user_message":
            return
        payload = data.get("data", {})
        content = (payload.get("content") or "").strip()
        if not content:
            return
        try:
            msg_type = MessageType(payload.get("msg_type", "TEXT"))
        except ValueError:
            msg_type = MessageType.TEXT

        # 落库患者消息
        async with AsyncSessionFactory() as db:
            await session_service.send_message(
                db,
                session_id,
                {"sub": info["sub"], "tenant_id": info["tenant_id"]},
                content,
                msg_type,
                None,
            )
        # 触发编排图 resume
        orchestrator = websocket.app.state.orchestrator
        await orchestrator.resume(
            session_id=session_id,
            tenant_id=info["tenant_id"],
            patient_id=info["sub"],
            answer=content,
        )

    async def receiver() -> None:
        """接收客户端消息（心跳 / 用户消息），维护超时。"""
        nonlocal last_active
        while True:
            try:
                raw = await asyncio.wait_for(
                    websocket.receive_text(), timeout=_CLIENT_HEARTBEAT_SECONDS
                )
            except asyncio.TimeoutError:
                if time.time() - last_active > _SERVER_TIMEOUT_SECONDS:
                    return
                continue
            last_active = time.time()
            if raw == "ping":
                await send("pong", {})
            else:
                await handle_user_message(raw)

    async def sender() -> None:
        """转发事件总线里的图节点事件。"""
        while True:
            event = await queue.get()
            await send(event["type"], event.get("data", {}))

    await send("connected", {
        "session_id": session_id,
        "session_status": "IN_PROGRESS",
        "heartbeat_interval": _CLIENT_HEARTBEAT_SECONDS,
    })

    try:
        receive_task = asyncio.create_task(receiver())
        send_task = asyncio.create_task(sender())
        done, pending = await asyncio.wait(
            {receive_task, send_task}, return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
        for task in done:
            task.result()  # 传播异常（如有）
    except WebSocketDisconnect:
        pass
    finally:
        event_bus.unsubscribe(session_id, queue)
