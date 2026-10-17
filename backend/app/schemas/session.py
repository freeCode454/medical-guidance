"""患者端预问诊会话相关 schema：对应 04 文档 12.2 节。

覆盖：创建预问诊会话（12.2.1）、发送消息（12.2.4）。
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.common.enums import MessageType, SessionStatus


class SessionCreateRequest(BaseModel):
    """创建预问诊会话请求体。"""

    chief_complaint: str | None = Field(
        default=None, max_length=500, description="主诉原文，不超过 500 字，为空时先建空会话"
    )
    input_type: Literal["TEXT", "VOICE", "BODY_MAP"] = Field(default="TEXT", description="输入方式")
    device_id: str | None = Field(default=None, max_length=128, description="设备标识")
    gender: Literal["男", "女"] | None = Field(
        default=None, description="性别（用于分诊规则的人群过滤，如妇科/产科仅女性）"
    )
    age: int | None = Field(default=None, ge=0, le=150, description="年龄（用于儿童/老年科室过滤）")


class SessionCreateResponse(BaseModel):
    """创建会话响应。"""

    session_id: str = Field(description="会话标识（32 位无连字符）")
    session_no: str = Field(description="会话业务编号，格式 S+日期+序号")
    status: SessionStatus = Field(description="会话状态")
    started_time: datetime = Field(description="开始时间")
    expire_time: datetime = Field(description="有效期，默认开始时间 + 24 小时")
    ws_url: str = Field(description="WebSocket 连接地址（不含鉴权票据）")


class MessageSendRequest(BaseModel):
    """发送消息请求体。"""

    content: str = Field(min_length=1, max_length=500, description="消息内容，1~500 字")
    msg_type: MessageType = Field(default=MessageType.TEXT, description="消息类型")
    extra: dict = Field(default_factory=dict, description="附加信息")


class MessageSendResponse(BaseModel):
    """发送消息响应（AI 回复经 WebSocket 异步推送，不在此响应返回）。"""

    model_config = ConfigDict(populate_by_name=True)

    message_id: str = Field(description="患者消息标识")
    seq_no: int = Field(description="消息在会话内的序号")
    session_status: SessionStatus = Field(description="会话当前状态")
    async_: bool = Field(
        default=True, alias="async", serialization_alias="async", description="恒为 true"
    )
    ws_hint: str = Field(default="后续内容通过 WebSocket 推送", description="提示信息")
