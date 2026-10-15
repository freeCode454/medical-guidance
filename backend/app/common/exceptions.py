"""业务异常与全局异常处理。

统一响应约定（《04 文档》第 3 章）：
    {code, data, message}，trace_id 通过响应头 X-Trace-ID 返回。

业务错误（10xxx~60xxx）的 HTTP 状态码统一为 200（《04 文档》第 4 章约定），
通用错误（400~599）的 HTTP 状态码与 code 一致。
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.common.error_codes import (
    BAD_REQUEST,
    INTERNAL_ERROR,
    ErrorCode,
)


class BizError(Exception):
    """业务异常：携带错误码。message 可覆盖默认文案（如动态拼剩余次数）。"""

    def __init__(self, code: ErrorCode, message: str | None = None) -> None:
        self.code = code
        self.message = message or code.message
        super().__init__(self.message)


def _response(code: int, message: str, data: object = None, http_status: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=http_status,
        content={"code": code, "data": data, "message": message},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器。"""

    @app.exception_handler(BizError)
    async def _biz_error(request: Request, exc: BizError) -> JSONResponse:
        return _response(exc.code.code, exc.message, http_status=exc.code.http_status)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # 提取 Pydantic 校验错误为字段级错误列表（{field, message}）
        errors = [
            {"field": ".".join(str(loc) for loc in err["loc"][1:]), "message": err["msg"]}
            for err in exc.errors()
        ]
        return _response(
            BAD_REQUEST.code,
            BAD_REQUEST.message,
            data={"errors": errors},
            http_status=BAD_REQUEST.http_status,
        )

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
        # 兜底：不泄露堆栈/SQL/内网地址（《04 文档》错误码约定第 3 条）
        return _response(
            INTERNAL_ERROR.code,
            INTERNAL_ERROR.message,
            http_status=INTERNAL_ERROR.http_status,
        )
