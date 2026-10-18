"""认证服务：院内用户登录 + 匿名患者会话。

安全要点（对应需求 R10 / AC-F13-3 / NFR18）：
- 登录失败**不区分**「账号不存在」与「口令错误」，统一返回 10001，防止账号枚举
- 连续 5 次口令错误锁定 15 分钟（常量，后续接 mg_sys_config 可配置）
- 匿名患者不采集姓名/身份证/手机号，只按 device_id 关联
"""
from __future__ import annotations

import asyncio
import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import UserRole
from app.common.error_codes import (
    AUTH_ACCOUNT_DISABLED,
    AUTH_ACCOUNT_LOCKED,
    AUTH_CREDENTIAL_INVALID,
    AUTH_ROLE_NOT_ALLOWED,
    BAD_REQUEST,
)
from app.common.exceptions import BizError
from app.common.security import (
    decode_token,
    device_fingerprint,
    hash_password,
    issue_access_token,
    issue_patient_token,
    issue_refresh_token,
    verify_password,
)
from app.config import settings
from app.models import Dept, Patient, Tenant, User
from app.schemas.auth import (
    PatientSessionCreateResponse,
    StaffLoginResponse,
    UserInfo,
)

LOGIN_FAIL_LIMIT = 5
LOCK_MINUTES = 15
# 账号不存在时也跑一次 bcrypt，避免通过响应时间枚举账号（恒定耗时）
_DUMMY_HASH = hash_password("medical-guidance-dummy-password")


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
        await asyncio.to_thread(verify_password, password, _DUMMY_HASH)
        raise BizError(AUTH_CREDENTIAL_INVALID, "账号或口令错误")

    user = users[0]
    now = datetime.now(UTC)

    # 锁定检查：仍在锁定期则拒绝；已过期则解锁
    if user.lock_until and user.lock_until > now:
        raise BizError(AUTH_ACCOUNT_LOCKED, "登录失败次数过多，请稍后重试")
    if user.lock_until and user.lock_until <= now:
        user.fail_count = 0
        user.lock_until = None

    # bcrypt 是 CPU 密集同步调用，阻塞事件循环会让全站卡住，必须放线程池
    if not await asyncio.to_thread(verify_password, password, user.credential_hash):
        user.fail_count += 1
        if user.fail_count >= LOGIN_FAIL_LIMIT:
            user.lock_until = now + timedelta(minutes=LOCK_MINUTES)
        await db.commit()
        # 不返回剩余次数：否则可据此确认账号存在
        raise BizError(AUTH_CREDENTIAL_INVALID, "账号或口令错误")

    # 口令正确后才暴露账号状态，避免用「已停用 / 角色不符」探测账号
    if user.status == "0":
        raise BizError(AUTH_ACCOUNT_DISABLED)
    if client_type == "ADMIN_WEB" and user.role == UserRole.DOCTOR.value:
        raise BizError(AUTH_ROLE_NOT_ALLOWED)

    # 登录成功：重置计数、记录时间、签发令牌
    user.fail_count = 0
    user.lock_until = None
    user.last_login_time = now
    await db.commit()

    return await _build_staff_response(db, user)


async def _build_staff_response(db: AsyncSession, user: User) -> StaffLoginResponse:
    """组装登录/刷新响应：令牌 + 用户与科室/租户信息。"""
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


async def refresh_staff_session(
    db: AsyncSession, refresh_token: str
) -> StaffLoginResponse:
    """用刷新令牌换一对新令牌（轮换：每次刷新同时下发新的 refresh_token）。

    - 令牌必须未过期、类型为 refresh（decode_token 校验）
    - 用户必须仍存在、启用，且角色/租户与令牌一致（防越权与降权后旧令牌续命）
    """
    payload = decode_token(refresh_token, expected_type="refresh")
    user = await db.scalar(
        select(User).where(User.id == payload.get("sub"), User.del_flag == "0")
    )
    if user is None or user.status == "0":
        raise BizError(AUTH_CREDENTIAL_INVALID, "登录状态已失效，请重新登录")
    if payload.get("role") != user.role or payload.get("tenant_id") != user.tenant_id:
        raise BizError(AUTH_CREDENTIAL_INVALID, "登录状态已失效，请重新登录")
    return await _build_staff_response(db, user)


def _device_hash(tenant_id: str, device_id: str) -> str:
    """患者标识哈希：加租户盐，同一设备在不同租户下哈希不同。"""
    return hashlib.sha256(f"{tenant_id}:{device_id}".encode()).hexdigest()


# 设备密钥最小长度：32 字符（约 128 bit 以上），低熵旧 ID 一律拒绝
DEVICE_SECRET_MIN_LENGTH = 32


async def create_patient_session(
    db: AsyncSession, device_id: str | None, client_type: str, channel: str
) -> PatientSessionCreateResponse:
    """创建匿名患者会话。

    ``device_id`` 是客户端持有的**设备密钥**（不是可猜测的编号）：
    - 服务端只保存 SHA-256 指纹（``patient_hash`` / ``device_id`` 两列），不存明文；
    - 未提供时由服务端生成高熵密钥，客户端负责持久化；
    - 低于 32 字符的旧格式/伪造格式直接拒绝，避免低熵凭证被枚举。
    """
    tenant_id = settings.default_tenant_id

    if device_id is not None:
        device_id = device_id.strip()
        if len(device_id) < DEVICE_SECRET_MIN_LENGTH:
            raise BizError(BAD_REQUEST, "设备标识无效，请重新进入")
    else:
        device_id = secrets.token_hex(32)

    patient_hash = _device_hash(tenant_id, device_id)
    fingerprint = device_fingerprint(device_id)

    patient = await db.scalar(
        select(Patient).where(
            Patient.tenant_id == tenant_id,
            Patient.patient_hash == patient_hash,
        )
    )

    if patient is None:
        patient = Patient(
            tenant_id=tenant_id,
            patient_hash=patient_hash,
            device_id=fingerprint,
        )
        db.add(patient)
        await db.flush()
    elif patient.device_id != fingerprint:
        # 旧数据迁移：历史记录里的明文设备标识替换为指纹
        patient.device_id = fingerprint

    await db.commit()

    return PatientSessionCreateResponse(
        access_token=issue_patient_token(patient.id, tenant_id),
        patient_id=patient.id,
        device_id=device_id,
        scope=["session:create", "session:read", "session:write"],
        need_verify_before=["APPOINTMENT", "EMR_ACCESS"],
    )
