"""换取 WebSocket 一次性票据（F05 / F29 通道鉴权）。

对应 04 文档 12.7.12 节。两段式鉴权：
先走 REST（带 Authorization 头）换取 ws_ticket，再用票据建立 WebSocket 连接。
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal
from app.common.database import get_db
from app.common.error_codes import BAD_REQUEST, NOT_FOUND
from app.common.exceptions import BizError
from app.common.ws_ticket import TICKET_TTL_SECONDS, ticket_store
from app.models import Session
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/api/v1", tags=["WebSocket"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


class WsTicketRequest(BaseModel):
    resource_type: str = Field(..., description="SESSION 对话通道 / TASK 任务通道")
    resource_id: str = Field(..., description="目标资源标识（会话标识或任务标识）")


async def _check_session_access(
    db: AsyncSession, session_id: str, payload: dict
) -> None:
    """校验会话存在且当前身份有权访问（本人或已接诊医生或机构管理员）。"""
    session = await db.scalar(
        select(Session).where(
            Session.id == session_id,
            Session.tenant_id == payload["tenant_id"],
        )
    )
    if session is None:
        raise BizError(NOT_FOUND)
    sub = payload["sub"]
    role = payload.get("role", "")
    allowed = (
        session.patient_id == sub
        or session.doctor_id == sub
        or role in {"ORG_ADMIN", "KB_ADMIN"}
    )
    if not allowed:
        raise BizError(NOT_FOUND)  # 统一 404，不泄露资源存在性


@router.post("/ws/ticket", response_model=ApiResponse[dict])
async def get_ws_ticket(
    req: WsTicketRequest, db: DbSession, principal: Principal, request: Request
) -> ApiResponse[dict]:
    """换取一次性 WebSocket 票据。"""
    if req.resource_type not in {"SESSION", "TASK"}:
        raise BizError(BAD_REQUEST, "resource_type 必须为 SESSION 或 TASK")

    if req.resource_type == "SESSION":
        await _check_session_access(db, req.resource_id, principal)
    else:
        # 任务进度通道：知识库入库任务尚未实现，暂返回资源不存在
        raise BizError(NOT_FOUND)

    ticket = ticket_store.issue(
        tenant_id=principal["tenant_id"],
        sub=principal["sub"],
        resource_type=req.resource_type,
        resource_id=req.resource_id,
    )

    # 构造完整连接地址（协议随请求，开发期 ws，生产经网关 wss）
    base = str(request.base_url).replace("http://", "ws://").replace("https://", "wss://")
    path = f"api/v1/ws/sessions/{req.resource_id}?token={ticket}"
    ws_url = base.rstrip("/") + "/" + path

    return ApiResponse(
        data={
            "ws_ticket": ticket,
            "expires_in": TICKET_TTL_SECONDS,
            "ws_url": ws_url,
        }
    )
