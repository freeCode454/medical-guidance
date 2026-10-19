"""接口层公共依赖：认证与身份解析。

多租户约定：tenant_id 一律从 JWT 解析取得，**不接受客户端传参**（防越权）。

身份载荷（JWT payload）字段：
    sub / role / tenant_id / type / scope / need_verify
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.database import get_db
from app.common.error_codes import AUTH_ACCOUNT_DISABLED, FORBIDDEN, UNAUTHORIZED
from app.common.exceptions import BizError
from app.common.security import decode_token
from app.models import Patient

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
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """获取当前患者；后台停用后即使旧令牌未过期也立即拒绝。"""
    payload = _require_payload(credentials)
    if payload.get("role") != "PATIENT":
        raise BizError(FORBIDDEN, "该接口需要患者身份")
    status = await db.scalar(
        select(Patient.status).where(
            Patient.id == payload.get("sub"),
            Patient.tenant_id == payload.get("tenant_id"),
            Patient.del_flag == "0",
        )
    )
    if status is None or status == "0":
        raise BizError(AUTH_ACCOUNT_DISABLED)
    return payload


async def get_current_doctor(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> dict:
    """获取当前医生，拒绝患者与管理员令牌。"""
    payload = _require_payload(credentials)
    if payload.get("role") != "DOCTOR":
        raise BizError(FORBIDDEN, "该接口需要医生身份")
    return payload


async def get_current_kb_admin(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> dict:
    """获取知识库管理员或机构管理员，拒绝患者与医生令牌。"""
    payload = _require_payload(credentials)
    if payload.get("role") not in {"KB_ADMIN", "ORG_ADMIN"}:
        raise BizError(FORBIDDEN, "该接口需要知识库管理员或机构管理员身份")
    return payload


async def get_current_org_admin(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> dict:
    """获取机构管理员，拒绝其他角色令牌。"""
    payload = _require_payload(credentials)
    if payload.get("role") != "ORG_ADMIN":
        raise BizError(FORBIDDEN, "该接口需要机构管理员身份")
    return payload


# 便捷类型别名
Principal = Annotated[dict, Depends(get_principal)]
CurrentStaff = Annotated[dict, Depends(get_current_staff)]
CurrentPatient = Annotated[dict, Depends(get_current_patient)]
CurrentDoctor = Annotated[dict, Depends(get_current_doctor)]
CurrentKbAdmin = Annotated[dict, Depends(get_current_kb_admin)]
CurrentOrgAdmin = Annotated[dict, Depends(get_current_org_admin)]
