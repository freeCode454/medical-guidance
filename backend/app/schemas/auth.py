"""认证与用户相关 schema：对应 04 文档 12.1 节。

覆盖：患者匿名会话创建（12.1.1）、院内用户登录（12.1.4）。
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.common.enums import UserRole

# --- 患者匿名会话创建（12.1.1） -----------------------------------------


class PatientSessionCreateRequest(BaseModel):
    """创建匿名会话的请求体。"""

    device_id: str | None = Field(
        default=None,
        min_length=32,
        max_length=128,
        description="设备密钥（客户端生成的高熵随机串，等价于匿名身份凭证）",
    )
    client_type: Literal["H5", "MINIPROGRAM", "APP"] = Field(default="H5", description="客户端类型")
    channel: Literal["WECHAT_MP", "GUIDE_MACHINE", "SMS_LINK", "DIRECT"] = Field(
        default="DIRECT", description="进入渠道"
    )


class PatientSessionCreateResponse(BaseModel):
    """匿名会话令牌响应。"""

    access_token: str = Field(description="访问令牌，有效期 30 分钟")
    token_type: str = Field(default="Bearer", description="令牌类型")
    expires_in: int = Field(default=1800, description="有效期（秒）")
    patient_id: str = Field(description="患者标识（32 位无连字符）")
    device_id: str = Field(description="设备密钥（客户端持久化；服务端只保存指纹）")
    scope: list[str] = Field(default_factory=list, description="匿名身份允许的操作范围")
    need_verify_before: list[str] = Field(default_factory=list, description="需实名验证才能执行的操作")


class PatientRegisterRequest(BaseModel):
    """患者注册：账号 + 口令 + 姓名。"""

    account: str = Field(min_length=4, max_length=64, pattern=r"^[A-Za-z0-9_]+$")
    password: str = Field(min_length=8, max_length=64)
    real_name: str | None = Field(default=None, max_length=64, description="患者姓名")


class PatientLoginRequest(BaseModel):
    """患者账号登录。"""

    account: str = Field(min_length=4, max_length=64)
    password: str = Field(min_length=8, max_length=64)


class PatientAuthResponse(BaseModel):
    """患者登录/注册后的账号令牌。"""

    access_token: str = Field(description="访问令牌，有效期 30 分钟")
    refresh_token: str = Field(description="刷新令牌")
    token_type: str = Field(default="Bearer")
    expires_in: int = Field(default=1800)
    patient_id: str = Field(description="患者标识")
    account: str = Field(description="登录账号")
    scope: list[str] = Field(default_factory=lambda: ["session:create", "session:read", "session:write"])
    need_verify_before: list[str] = Field(default_factory=lambda: ["APPOINTMENT", "EMR_ACCESS"])


class UnifiedLoginRequest(BaseModel):
    """统一登录：账号密码由后端判断患者 / 医生 / 管理员。"""

    account: str = Field(min_length=4, max_length=64)
    password: str = Field(min_length=8, max_length=64)


# --- 院内用户登录（12.1.4） ---------------------------------------------


class StaffLoginRequest(BaseModel):
    """院内用户登录请求体。"""

    account: str = Field(min_length=4, max_length=64, description="登录账号")
    password: str = Field(min_length=8, max_length=64, description="口令")
    client_type: Literal["WEB", "ADMIN_WEB"] = Field(default="WEB", description="客户端类型")


class StaffRefreshRequest(BaseModel):
    """刷新访问令牌请求体。"""

    refresh_token: str = Field(min_length=20, max_length=1024, description="登录时下发的刷新令牌")


class UserInfo(BaseModel):
    """用户身份信息。"""

    user_id: str = Field(description="用户标识")
    account: str = Field(description="登录账号")
    real_name: str | None = Field(default=None, description="真实姓名")
    role: UserRole = Field(description="角色")
    title: str | None = Field(default=None, description="医师职称，非医生角色为 null")
    dept_code: str | None = Field(default=None, description="所属科室，非医生角色为 null")
    dept_name: str | None = Field(default=None, description="所属科室名称")
    tenant_id: str = Field(description="租户标识")
    tenant_name: str = Field(description="租户名称")


class StaffLoginResponse(BaseModel):
    """院内用户登录响应。"""

    model_config = ConfigDict(populate_by_name=True)

    access_token: str = Field(description="访问令牌，有效期 2 小时")
    refresh_token: str = Field(description="刷新令牌，有效期 8 小时")
    token_type: str = Field(default="Bearer", description="令牌类型")
    expires_in: int = Field(default=7200, description="访问令牌有效期（秒）")
    refresh_expires_in: int = Field(default=28800, description="刷新令牌有效期（秒）")
    user: UserInfo = Field(description="用户身份信息")


class UnifiedLoginResponse(BaseModel):
    """统一登录响应：前端据 role 跳转对应端。"""

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = 1800
    role: str
    account: str
    patient_id: str | None = None
    user: UserInfo | None = None
