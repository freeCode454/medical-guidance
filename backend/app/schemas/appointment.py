from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class AppointmentCreateRequest(BaseModel):
    session_id: str | None = Field(default=None, description="来源会话，可为空")
    dept_code: str = Field(..., max_length=32)
    doctor_id: str = Field(..., max_length=32)
    schedule_date: date = Field(...)
    time_slot: str = Field(..., max_length=32)
