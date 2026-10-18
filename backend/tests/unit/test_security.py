"""认证基础设施：口令哈希、JWT 类型校验、过期、刷新令牌轮换。"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.common.error_codes import AUTH_TOKEN_EXPIRED, AUTH_TOKEN_INVALID
from app.common.exceptions import BizError
from app.common.security import (
    decode_token,
    hash_password,
    issue_access_token,
    issue_refresh_token,
    verify_password,
)
from app.config import settings


def test_password_round_trip_and_reject() -> None:
    hashed = hash_password("correct-horse-battery")
    assert verify_password("correct-horse-battery", hashed)
    assert not verify_password("wrong-password", hashed)
    # 占位符/损坏哈希不抛异常，按校验失败处理
    assert not verify_password("whatever", "not-a-bcrypt-hash")


def test_access_token_round_trip_and_type_guard() -> None:
    token = issue_access_token("user-1", "DOCTOR", "tenant-1")
    payload = decode_token(token)
    assert payload["sub"] == "user-1"
    assert payload["role"] == "DOCTOR"
    assert payload["jti"]

    with pytest.raises(BizError) as exc:
        decode_token(token, expected_type="refresh")
    assert exc.value.code is AUTH_TOKEN_INVALID


def test_expired_token_reports_expired() -> None:
    expired = jwt.encode(
        {
            "sub": "user-1",
            "type": "access",
            "role": "DOCTOR",
            "tenant_id": "tenant-1",
            "exp": datetime.now(UTC) - timedelta(seconds=5),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(BizError) as exc:
        decode_token(expired)
    assert exc.value.code is AUTH_TOKEN_EXPIRED


def test_refresh_tokens_rotate() -> None:
    first = issue_refresh_token("user-1", "DOCTOR", "tenant-1")
    second = issue_refresh_token("user-1", "DOCTOR", "tenant-1")
    assert first != second
    assert decode_token(first, expected_type="refresh")["type"] == "refresh"
