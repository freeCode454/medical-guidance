"""WebSocket 一次性票据（ws_ticket）。

对齐《04 文档》11.1 节：
- 有效期 60 秒，超时未使用即失效
- 一次性：连接建立后立即作废
- 绑定 tenant_id / 主体标识 / 目标资源（session_id 或 task_id），用于其他资源即拒绝

开发期用进程内存存储（单实例足够）；交付期多实例部署需换 Redis。
"""
from __future__ import annotations

import secrets
import time

TICKET_TTL_SECONDS = 60


class TicketStore:
    """一次性票据存储（单例）。"""

    def __init__(self, ttl_seconds: int = TICKET_TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._tickets: dict[str, dict] = {}

    def issue(
        self,
        *,
        tenant_id: str,
        sub: str,
        resource_type: str,
        resource_id: str,
    ) -> str:
        """签发票据，返回 ``wt_`` 前缀的随机串。"""
        ticket = "wt_" + secrets.token_hex(16)
        self._tickets[ticket] = {
            "tenant_id": tenant_id,
            "sub": sub,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "expires_at": time.time() + self._ttl,
        }
        return ticket

    def verify(
        self, ticket: str, *, resource_type: str, resource_id: str
    ) -> dict | None:
        """校验并作废票据（一次性）。

        返回票据绑定的信息（tenant_id/sub/resource_*），校验失败返回 None。
        """
        info = self._tickets.pop(ticket, None)
        if info is None:
            return None
        if time.time() > info["expires_at"]:
            return None
        if info["resource_type"] != resource_type or info["resource_id"] != resource_id:
            return None
        return info


# 全局单例
ticket_store = TicketStore()
