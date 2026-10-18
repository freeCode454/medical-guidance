"""请求上下文中间件：trace id、访问日志、安全响应头。

约定（与《04 文档》错误码章节一致）：
- 每个响应都带 ``X-Trace-ID``，日志行也带同一个 id，便于按一次请求串起来排查
- 客户端可传 ``X-Request-ID``（限 64 字符）复用链路 id；否则服务端生成
- 未捕获异常在这里兜底成统一响应 ``{code, data, message}`` 并记录堆栈，
  避免异常冒泡到 Starlette 默认处理器后既没有日志也没有统一格式
"""
from __future__ import annotations

import logging
import time
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from app.common.context import get_trace_id, reset_trace_id, set_trace_id
from app.common.error_codes import INTERNAL_ERROR

logger = logging.getLogger("app.access")

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}
_QUIET_PATHS = {"/healthz", "/readyz"}


class RequestContextMiddleware(BaseHTTPMiddleware):
    """给每个请求分配 trace id，并输出一行结构化访问日志。"""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        incoming = request.headers.get("X-Request-ID", "")
        trace_id = incoming if 0 < len(incoming) <= 64 else uuid4().hex[:16]
        token = set_trace_id(trace_id)
        started = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            # 兜底：统一响应格式 + 堆栈落日志；不要把内部细节回传给客户端
            logger.exception(
                "unhandled error trace=%s %s %s",
                trace_id,
                request.method,
                request.url.path,
            )
            response = JSONResponse(
                status_code=INTERNAL_ERROR.http_status,
                content={
                    "code": INTERNAL_ERROR.code,
                    "data": None,
                    "message": INTERNAL_ERROR.message,
                },
            )
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000
            reset_trace_id(token)

        response.headers["X-Trace-ID"] = trace_id
        for key, value in _SECURITY_HEADERS.items():
            response.headers.setdefault(key, value)

        if request.url.path not in _QUIET_PATHS:
            logger.info(
                "trace=%s %s %s status=%s cost=%.1fms",
                trace_id,
                request.method,
                request.url.path,
                response.status_code,
                elapsed_ms,
            )
        return response


def current_trace_id() -> str:
    """给异常处理器/业务日志用：取当前请求的 trace id。"""
    return get_trace_id()
