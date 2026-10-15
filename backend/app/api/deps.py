"""接口层公共依赖：认证与身份解析。

多租户约定：tenant_id 一律从 JWT 解析取得，**不接受客户端传参**（防越权）。

身份载荷（JWT payload）字段：
    sub / role / tenant_id / type / scope / need_verify
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.common.error_codes import FORBIDDEN, UNAUTHORIZED
from app.common.exceptions import BizError
from app.common.security import decode_token

_bearer = HTTPBearer(auto_error=False)


def _require_payload(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> dict:
    """解析并校验令牌，返回 payload。"""
    if credentials is None:
        raise BizError(UNAUTHORIZED)
    return decode_token(credentials.credentials, expected_type="access")


async def get_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> dict:
    """获取当前身份载荷（患者或院内用户，不区分角色）。"""
    return _require_payload(credentials)


async def get_current_staff(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> dict:
    """获取当前院内用户（医生/管理员），拒绝患者令牌。"""
    payload = _require_payload(credentials)
    if payload.get("role") == "PATIENT":
        raise BizError(FORBIDDEN, "该接口需要院内用户身份")
    return payload


async def get_current_patient(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> dict:
    """获取当前匿名患者，拒绝院内用户令牌。"""
    payload = _require_payload(credentials)
    if payload.get("role") != "PATIENT":
        raise BizError(FORBIDDEN, "该接口需要患者身份")
    return payload


# 便捷类型别名
Principal = Annotated[dict, Depends(get_principal)]
CurrentStaff = Annotated[dict, Depends(get_current_staff)]
CurrentPatient = Annotated[dict, Depends(get_current_patient)]
