"""认证与安全工具：JWT 签发/校验 + 口令哈希。

JWT payload 约定
----------------
- ``sub``：主体标识（院内用户为 user_id，匿名患者为 patient_id）
- ``role``：角色（DOCTOR / KB_ADMIN / ORG_ADMIN / PATIENT）
- ``tenant_id``：租户标识（多租户隔离的根）
- ``type``：令牌类型（access / refresh）
- ``exp``：过期时间（jwt 库自动由 datetime 转换）

口令：bcrypt 哈希，不可逆。登录失败不区分「账号不存在」与「口令错误」
（统一返回 10001），防止账号枚举。
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import bcrypt
import jwt

from app.common.error_codes import AUTH_TOKEN_EXPIRED, AUTH_TOKEN_INVALID
from app.common.exceptions import BizError
from app.config import settings

# --- 口令 ------------------------------------------------------------------

def hash_password(password: str) -> str:
    """生成 bcrypt 哈希。bcrypt 明文上限 72 字节，超出部分截断。

    直接用 bcrypt 库而非 passlib：passlib 1.7.4 与 bcrypt 4.x 不兼容
    （后者移除了 ``__about__``），会报 ``module 'bcrypt' has no attribute '__about__'``。
    """
    data = password.encode("utf-8")[:72]
    return bcrypt.hashpw(data, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """校验口令。异常（如种子数据的占位符哈希）时返回 False 而非抛异常。"""
    try:
        data = password.encode("utf-8")[:72]
        return bcrypt.checkpw(data, hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# --- JWT -------------------------------------------------------------------

def _issue(subject: str, token_type: str, expires_seconds: int, claims: dict[str, Any]) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + timedelta(seconds=expires_seconds),
        # jti 让每次签发都唯一：刷新令牌轮换才真正换了令牌，
        # 也为后续「单令牌吊销 / token_version」留出锚点。
        "jti": uuid4().hex,
    }
    payload.update(claims)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def issue_access_token(user_id: str, role: str, tenant_id: str) -> str:
    """院内用户访问令牌。"""
    return _issue(
        user_id,
        "access",
        settings.access_token_expires_seconds,
        {"role": role, "tenant_id": tenant_id},
    )


def issue_refresh_token(user_id: str, role: str, tenant_id: str) -> str:
    """院内用户刷新令牌。"""
    return _issue(
        user_id,
        "refresh",
        settings.refresh_token_expires_seconds,
        {"role": role, "tenant_id": tenant_id},
    )


def issue_patient_token(patient_id: str, tenant_id: str) -> str:
    """匿名患者访问令牌。"""
    return _issue(
        patient_id,
        "access",
        settings.patient_token_expires_seconds,
        {
            "role": "PATIENT",
            "tenant_id": tenant_id,
            "scope": ["session:create", "session:read", "session:write"],
            "need_verify": ["APPOINTMENT", "EMR_ACCESS"],
        },
    )


def decode_token(token: str, expected_type: str = "access") -> dict[str, Any]:
    """解码并校验令牌。失败抛出 BizError（10004 过期 / 10005 无效）。"""
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except jwt.ExpiredSignatureError as exc:
        raise BizError(AUTH_TOKEN_EXPIRED) from exc
    except jwt.InvalidTokenError as exc:
        raise BizError(AUTH_TOKEN_INVALID) from exc

    if payload.get("type") != expected_type:
        raise BizError(AUTH_TOKEN_INVALID, "令牌类型不符")
    return payload
