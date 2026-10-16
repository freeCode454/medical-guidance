"""WebSocket 事件总线：session_id → 订阅队列。

图节点执行时 ``publish`` 事件，WebSocket 端点 ``subscribe`` 后把事件转发给客户端。
事件不含 ``seq`` / ``ts``（由连接端转发时按连接内序号包装），只含 ``type`` / ``data``。

单进程内所有协程共享同一个事件循环，用 ``asyncio.Queue`` 即可，无需额外锁。
缓冲上限防止慢客户端堆积拖垮进程；溢出丢弃（客户端断线重连后由 ``resync_required`` 补发）。
"""
from __future__ import annotations

import asyncio

_QUEUE_MAXSIZE = 500


class EventBus:
    """进程内事件总线（单例）。"""

    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue]] = {}

    def subscribe(self, session_id: str) -> asyncio.Queue:
        """订阅某会话的事件，返回接收队列。"""
        queue: asyncio.Queue = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
        self._subscribers.setdefault(session_id, set()).add(queue)
        return queue

    def unsubscribe(self, session_id: str, queue: asyncio.Queue) -> None:
        """取消订阅（连接断开时调用）。"""
        subs = self._subscribers.get(session_id)
        if subs is None:
            return
        subs.discard(queue)
        if not subs:
            self._subscribers.pop(session_id, None)

    def publish(self, session_id: str, event: dict) -> None:
        """广播事件给该会话的所有订阅者。无订阅者时静默丢弃。"""
        for queue in list(self._subscribers.get(session_id, ())):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # 慢客户端堆积：丢弃最旧事件，保持进程不被打爆
                try:
                    queue.get_nowait()
                    queue.put_nowait(event)
                except asyncio.QueueEmpty:
                    pass


# 全局单例：图节点、编排器、WebSocket 端点共享
event_bus = EventBus()
