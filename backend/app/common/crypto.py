"""敏感字段加密：模型服务 API Key 等。

- 使用 Fernet（AES-128-CBC + HMAC）做对称加密，密文带 ``enc:v1:`` 前缀；
- 密钥优先取 ``FIELD_ENCRYPTION_KEY``，留空时从 ``JWT_SECRET`` 派生，
  保证开发环境开箱可用，生产建议独立配置以便轮换；
- 读取旧数据时兼容无前缀的明文（只读兼容，新写入一律加密）。
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings

PREFIX = "enc:v1:"


def _fernet() -> Fernet:
    material = settings.field_encryption_key or settings.jwt_secret
    key = base64.urlsafe_b64encode(hashlib.sha256(material.encode("utf-8")).digest())
    return Fernet(key)


def is_encrypted(value: str | None) -> bool:
    return bool(value and value.startswith(PREFIX))


def encrypt_secret(value: str | None) -> str | None:
    """加密明文；空值返回 None，已加密值幂等返回。"""
    if not value:
        return None
    if is_encrypted(value):
        return value
    token = _fernet().encrypt(value.encode("utf-8")).decode("ascii")
    return f"{PREFIX}{token}"


def decrypt_secret(value: str | None) -> str | None:
    """解密；兼容历史明文。密钥不匹配时抛 ValueError，避免静默返回密文。"""
    if not value:
        return None
    if not is_encrypted(value):
        return value
    try:
        return _fernet().decrypt(value[len(PREFIX):].encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("敏感字段解密失败：FIELD_ENCRYPTION_KEY 与写入时不一致") from exc
