"""图节点事件发射辅助。

节点标识对齐《04 文档》11.3 节。事件只含 ``type`` / ``data``，
``seq`` / ``ts`` 由 WebSocket 连接端转发时按连接内序号包装。
"""
from __future__ import annotations

from app.ws.event_bus import event_bus

# 节点标识常量（04 文档 11.3 节 node_start 的 node 取值）
NODE_SAFETY = "SAFETY_CHECK"
NODE_INQUIRY = "INQUIRY"
NODE_RETRIEVAL = "RETRIEVAL"
NODE_TRIAGE_DECIDE = "TRIAGE_DECIDE"
NODE_MDT_COUNCIL = "MDT_COUNCIL"
NODE_EMR_GENERATE = "EMR_GENERATE"


def emit_node_start(
    session_id: str, node: str, node_label: str, message: str
) -> None:
    """节点开始事件。"""
    event_bus.publish(
        session_id,
        {
            "type": "node_start",
            "data": {"node": node, "node_label": node_label, "message": message},
        },
    )


def emit_node_complete(
    session_id: str, node: str, output: dict, duration_ms: int = 0
) -> None:
    """节点完成事件。"""
    event_bus.publish(
        session_id,
        {
            "type": "node_complete",
            "data": {"node": node, "duration_ms": duration_ms, "output": output},
        },
    )


def emit_node_error(
    session_id: str, node: str, code: int, message: str, degraded: bool = True
) -> None:
    """节点错误/降级事件。"""
    event_bus.publish(
        session_id,
        {
            "type": "node_error",
            "data": {
                "node": node,
                "code": code,
                "message": message,
                "degraded": degraded,
                "recoverable": True,
            },
        },
    )


def emit_emergency(session_id: str, matched_rule: str, message: str) -> None:
    """危重症告警事件。"""
    event_bus.publish(
        session_id,
        {
            "type": "emergency",
            "data": {
                "triggered": True,
                "matched_rule": matched_rule,
                "matched_layer": 1,
                "action": "GUIDE_TO_EMERGENCY",
                "message": message,
                "emergency_phone": "120",
            },
        },
    )


def emit_task_complete(session_id: str, data: dict) -> None:
    """任务完成事件（对话通道）。"""
    event_bus.publish(
        session_id,
        {"type": "task_complete", "data": data},
    )
