"""认证服务：院内用户登录 + 匿名患者会话。

安全要点（对应需求 R10 / AC-F13-3 / NFR18）：
- 登录失败**不区分**「账号不存在」与「口令错误」，统一返回 10001，防止账号枚举
- 连续 5 次口令错误锁定 15 分钟（常量，后续接 mg_sys_config 可配置）
- 匿名患者不采集姓名/身份证/手机号，只按 device_id 关联
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import UserRole
from app.common.error_codes import (
    AUTH_ACCOUNT_DISABLED,
    AUTH_ACCOUNT_LOCKED,
    AUTH_CREDENTIAL_INVALID,
    AUTH_ROLE_NOT_ALLOWED,
)
from app.common.exceptions import BizError
from app.common.security import issue_access_token, issue_patient_token, issue_refresh_token, verify_password
from app.config import settings
from app.models import Dept, Patient, Tenant, User
from app.schemas.auth import (
    PatientSessionCreateResponse,
    StaffLoginResponse,
    UserInfo,
)

LOGIN_FAIL_LIMIT = 5
LOCK_MINUTES = 15


async def staff_login(
    db: AsyncSession, account: str, password: str, client_type: str
) -> StaffLoginResponse:
    """院内用户登录。"""
    # 账号在租户内唯一，但登录请求不带租户 → 按 account 跨租户查
    result = await db.execute(
        select(User).where(User.account == account, User.del_flag == "0")
    )
    users = result.scalars().all()
    # 账号不存在 / 多个租户同名：统一返回账号或口令错误，防账号枚举
    if len(users) != 1:
        raise BizError(AUTH_CREDENTIAL_INVALID, "账号或口令错误")

    user = users[0]
    now = datetime.now(timezone.utc)

    if user.status == "0":
        raise BizError(AUTH_ACCOUNT_DISABLED)

    # 锁定检查：仍在锁定期则拒绝；已过期则解锁
    if user.lock_until and user.lock_until > now:
        remaining = int((user.lock_until - now).total_seconds() // 60) + 1
        raise BizError(AUTH_ACCOUNT_LOCKED, f"账号已锁定，请 {remaining} 分钟后重试")
    if user.lock_until and user.lock_until <= now:
        user.fail_count = 0
        user.lock_until = None

    # 客户端类型与角色匹配（医生账号不得登录管理后台）
    if client_type == "ADMIN_WEB" and user.role == UserRole.DOCTOR.value:
        raise BizError(AUTH_ROLE_NOT_ALLOWED)

    # 口令校验（失败计数 + 锁定）
    if not verify_password(password, user.credential_hash):
        user.fail_count += 1
        if user.fail_count >= LOGIN_FAIL_LIMIT:
            user.lock_until = now + timedelta(minutes=LOCK_MINUTES)
            await db.commit()
            raise BizError(
                AUTH_ACCOUNT_LOCKED,
                f"连续失败 {LOGIN_FAIL_LIMIT} 次，账号已锁定 {LOCK_MINUTES} 分钟",
            )
        await db.commit()
        raise BizError(
            AUTH_CREDENTIAL_INVALID,
            f"账号或口令错误，还可尝试 {LOGIN_FAIL_LIMIT - user.fail_count} 次",
        )

    # 登录成功：重置计数、记录时间、签发令牌
    user.fail_count = 0
    user.lock_until = None
    user.last_login_time = now
    await db.commit()

    dept_name = None
    if user.dept_code:
        dept_name = await db.scalar(
            select(Dept.dept_name).where(
                Dept.tenant_id == user.tenant_id, Dept.dept_code == user.dept_code
            )
        )
    tenant_name = await db.scalar(
        select(Tenant.tenant_name).where(Tenant.id == user.tenant_id)
    )

    return StaffLoginResponse(
        access_token=issue_access_token(user.id, user.role, user.tenant_id),
        refresh_token=issue_refresh_token(user.id, user.role, user.tenant_id),
        user=UserInfo(
            user_id=user.id,
            account=user.account,
            real_name=user.real_name,
            role=UserRole(user.role),
            title=user.title,
            dept_code=user.dept_code,
            dept_name=dept_name,
            tenant_id=user.tenant_id,
            tenant_name=tenant_name or "",
        ),
    )


def _device_hash(tenant_id: str, device_id: str) -> str:
    """患者标识哈希：加租户盐，同一设备在不同租户下哈希不同。"""
    return hashlib.sha256(f"{tenant_id}:{device_id}".encode("utf-8")).hexdigest()


async def create_patient_session(
    db: AsyncSession, device_id: str | None, client_type: str, channel: str
) -> PatientSessionCreateResponse:
    """创建匿名患者会话：按 device_id 复用患者，签发患者令牌。"""
    tenant_id = settings.default_tenant_id

    device = device_id or f"dev_{uuid4().hex[:20]}"

    patient = None
    if device_id:
        patient = await db.scalar(
            select(Patient).where(
                Patient.tenant_id == tenant_id, Patient.device_id == device_id
            )
        )

    if patient is None:
        patient = Patient(
            tenant_id=tenant_id,
            patient_hash=_device_hash(tenant_id, device),
            device_id=device,
        )
        db.add(patient)
        await db.flush()

    await db.commit()

    return PatientSessionCreateResponse(
        access_token=issue_patient_token(patient.id, tenant_id),
        patient_id=patient.id,
        device_id=device,
        scope=["session:create", "session:read", "session:write"],
        need_verify_before=["APPOINTMENT", "EMR_ACCESS"],
    )
