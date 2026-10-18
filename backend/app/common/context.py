"""请求级上下文：当前请求的 trace id。

放在 contextvars 而不是 request.state，是因为异常处理器、日志过滤器、后台任务
不一定拿得到 Request 对象；contextvars 在同一协程链上自动传递。
"""
from __future__ import annotations

from contextvars import ContextVar, Token

_TRACE_ID: ContextVar[str] = ContextVar("trace_id", default="-")


def get_trace_id() -> str:
    return _TRACE_ID.get()


def set_trace_id(trace_id: str) -> Token[str]:
    """设置当前协程的 trace id，返回用于恢复的 token。"""
    return _TRACE_ID.set(trace_id)


def reset_trace_id(token: Token[str]) -> None:
    _TRACE_ID.reset(token)
