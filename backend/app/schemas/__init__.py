"""Pydantic schema 层：04 文档的请求/响应契约。

已覆盖（主链路核心）：
    common.py  → 统一响应 / 分页 / 字段错误
    auth.py    → 匿名会话创建 / 院内用户登录
    session.py → 创建会话 / 发送消息
    triage.py  → 分诊结果（患者视图）

后续阶段补充：医生端（MDT / 鉴别诊断 / 病历）、知识库、机构、系统配置等。
"""
from app.schemas.auth import (
    PatientSessionCreateRequest,
    PatientSessionCreateResponse,
    StaffLoginRequest,
    StaffLoginResponse,
    UserInfo,
)
from app.schemas.common import (
    ApiResponse,
    ErrorData,
    FieldError,
    PageData,
    PageQuery,
)
from app.schemas.session import (
    MessageSendRequest,
    MessageSendResponse,
    SessionCreateRequest,
    SessionCreateResponse,
)
from app.schemas.triage import (
    EmergencyGuidance,
    RecommendedDept,
    SymptomSummary,
    TriageResultResponse,
)

__all__ = [
    "ApiResponse",
    "EmergencyGuidance",
    "ErrorData",
    "FieldError",
    "MessageSendRequest",
    "MessageSendResponse",
    "PageData",
    "PageQuery",
    "PatientSessionCreateRequest",
    "PatientSessionCreateResponse",
    "RecommendedDept",
    "SessionCreateRequest",
    "SessionCreateResponse",
    "StaffLoginRequest",
    "StaffLoginResponse",
    "SymptomSummary",
    "TriageResultResponse",
    "UserInfo",
]
