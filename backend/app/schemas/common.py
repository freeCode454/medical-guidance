"""通用响应与分页模型：与《04-API 接口设计说明书》第 3 章一致。

统一响应结构：``{code, data, message}``。
分页结构：``{total, page, size, items}``（字段名为 size，不是 page_size）。
trace_id 通过响应头 ``X-Trace-ID`` 返回，不进响应体。
"""
from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """统一响应包装。code 见《04 文档》第 4 章。"""

    code: int = Field(default=200, description="业务码，见 04 文档第 4 章")
    data: T | None = Field(default=None, description="响应数据")
    message: str = Field(default="成功", description="提示信息")


class FieldError(BaseModel):
    """字段级校验错误。"""

    field: str = Field(description="出错的字段名（snake_case）")
    message: str = Field(description="该字段的具体错误原因")


class ErrorData(BaseModel):
    """参数校验失败时的 data 结构。"""

    errors: list[FieldError] = Field(default_factory=list, description="字段级错误列表")


class PageData(BaseModel, Generic[T]):
    """统一分页结构。"""

    total: int = Field(description="满足条件的总记录数（不受分页限制）")
    page: int = Field(default=1, description="当前页码，从 1 开始")
    size: int = Field(default=20, description="每页条数")
    items: list[T] = Field(default_factory=list, description="当前页数据；无数据时为 []")


# 分页查询公共参数（接口的 query 参数）
class PageQuery(BaseModel):
    """列表接口的分页 query 参数。"""

    page: int = Field(default=1, ge=1, description="页码，从 1 开始")
    size: int = Field(default=20, ge=1, le=100, description="每页条数，最大 100")
