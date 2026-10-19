"""患者个人资料更新入参。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class PatientProfileUpdateRequest(BaseModel):
    """患者可自行维护的最少资料：性别与年龄。"""

    gender: Literal["男", "女"] | None = Field(default=None, description="性别")
    age: int | None = Field(default=None, ge=0, le=120, description="年龄")
