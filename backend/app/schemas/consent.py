"""患者授权 schema：病史调阅授权（F10 / R01 隐私约束）。"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ConsentCreateRequest(BaseModel):
    """患者主动授权医生调阅历史病历。"""

    scope: Literal["EMR_READ"] = Field(default="EMR_READ", description="授权范围")
    session_id: str | None = Field(default=None, max_length=32, description="触发授权的会话")
    expire_days: int = Field(default=180, ge=1, le=3650, description="有效天数")


class ConsentItem(BaseModel):
    """授权记录（患者视图）。"""

    consent_id: str
    scope: str
    consent_time: datetime
    expire_time: datetime | None
    revoke_time: datetime | None
    channel: str | None


class ConsentListResponse(BaseModel):
    items: list[ConsentItem]
