"""WebSocket 一次性票据：过期、一次性、资源绑定与清理。"""
from __future__ import annotations

from app.common.ws_ticket import TicketStore


def _issue(store: TicketStore) -> str:
    return store.issue(
        tenant_id="t1",
        sub="p1",
        resource_type="SESSION",
        resource_id="s1",
    )


def test_ticket_is_one_time() -> None:
    store = TicketStore()
    ticket = _issue(store)
    assert store.verify(ticket, resource_type="SESSION", resource_id="s1")
    assert store.verify(ticket, resource_type="SESSION", resource_id="s1") is None


def test_ticket_bound_to_resource() -> None:
    store = TicketStore()
    ticket = _issue(store)
    assert store.verify(ticket, resource_type="SESSION", resource_id="s2") is None


def test_expired_ticket_rejected_and_purged() -> None:
    store = TicketStore(ttl_seconds=-1)
    expired = _issue(store)
    assert store.verify(expired, resource_type="SESSION", resource_id="s1") is None

    # 新签发票据时会顺手清理过期项，避免只换票不校验导致内存增长
    store.issue(tenant_id="t1", sub="p1", resource_type="SESSION", resource_id="s1")
    assert expired not in store._tickets
