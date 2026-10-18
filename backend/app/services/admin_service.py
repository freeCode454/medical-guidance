"""管理端服务：用户、科室、机构信息、系统配置、模型配置、审计日志查询。

权限：ORG_ADMIN（机构管理员）。知识库管理员调用用户/科室管理返回 403（AC-F55-1）。
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.crypto import encrypt_secret
from app.common.enums import AuditActionType, AuditResult
from app.common.error_codes import (
    CONFIG_NOT_FOUND,
    DEPT_CODE_EXISTS,
    DEPT_NOT_FOUND,
    MODEL_PROVIDER_CODE_EXISTS,
    MODEL_PROVIDER_NOT_FOUND,
    TENANT_NOT_FOUND,
    USER_ACCOUNT_EXISTS,
    USER_NOT_FOUND,
)
from app.common.exceptions import BizError
from app.common.security import hash_password
from app.models import AuditLog, Dept, ModelProvider, SysConfig, Tenant, User

_ROLE_LABELS = {"DOCTOR": "医生", "KB_ADMIN": "知识库管理员", "ORG_ADMIN": "机构管理员"}


async def _write_audit(
    db: AsyncSession,
    *,
    tenant_id: str,
    actor_id: str,
    actor_role: str,
    action_type: str,
    target_type: str,
    target_id: str | None,
    detail: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            tenant_id=tenant_id,
            actor_id=actor_id,
            actor_role=actor_role,
            action_type=action_type,
            target_type=target_type,
            target_id=target_id,
            result=AuditResult.SUCCESS.value,
            detail_json=detail,
        )
    )


# ---- 用户 -----------------------------------------------------------------


async def list_users(
    db: AsyncSession, *, tenant_id: str, page: int, size: int,
    role: str | None, dept_code: str | None, status: str | None, keyword: str | None,
) -> dict:
    conds = [User.tenant_id == tenant_id]
    if role:
        conds.append(User.role == role)
    if dept_code:
        conds.append(User.dept_code == dept_code)
    if status:
        conds.append(User.status == status)
    if keyword:
        conds.append(or_(User.account.ilike(f"%{keyword}%"), User.real_name.ilike(f"%{keyword}%")))

    total = await db.scalar(select(func.count()).select_from(User).where(*conds))
    rows = (
        await db.scalars(
            select(User).where(*conds).order_by(User.create_time.desc())
            .offset((page - 1) * size).limit(size)
        )
    ).all()

    # 科室名
    dept_codes = {u.dept_code for u in rows if u.dept_code}
    dept_names = {
        d.dept_code: d.dept_name
        for d in (await db.scalars(select(Dept).where(Dept.tenant_id == tenant_id, Dept.dept_code.in_(dept_codes)))).all()
    }
    items = [
        {
            "user_id": u.id,
            "account": u.account,
            "real_name": u.real_name,
            "role": u.role,
            "role_label": _ROLE_LABELS.get(u.role, u.role),
            "title": u.title,
            "dept_code": u.dept_code,
            "dept_name": dept_names.get(u.dept_code) if u.dept_code else None,
            "status": u.status,
            "last_login_time": u.last_login_time.isoformat() if u.last_login_time else None,
            "create_time": u.create_time.isoformat() if u.create_time else None,
        }
        for u in rows
    ]
    return {"total": total, "page": page, "size": size, "items": items}


async def create_user(
    db: AsyncSession, *, tenant_id: str, actor_id: str, actor_role: str, payload: dict
) -> dict:
    account = payload["account"]
    role = payload["role"]
    title = payload.get("title")
    dept_code = payload.get("dept_code")
    initial_password = payload["initial_password"]

    exists = await db.scalar(
        select(User).where(User.tenant_id == tenant_id, User.account == account)
    )
    if exists is not None:
        raise BizError(USER_ACCOUNT_EXISTS)

    # 医生必填职称与科室
    if role == "DOCTOR":
        if not title:
            raise BizError(DEPT_NOT_FOUND, "医生必须设置职称")
        if dept_code:
            dept = await db.scalar(
                select(Dept).where(Dept.tenant_id == tenant_id, Dept.dept_code == dept_code)
            )
            if dept is None:
                raise BizError(DEPT_NOT_FOUND)

    user = User(
        tenant_id=tenant_id,
        account=account,
        real_name=payload.get("real_name"),
        role=role,
        title=title if role == "DOCTOR" else None,
        dept_code=dept_code if role == "DOCTOR" else None,
        credential_hash=hash_password(initial_password),
        status="1",
        create_by=actor_id,
        remark=payload.get("remark"),
    )
    db.add(user)
    await db.flush()
    await _write_audit(
        db, tenant_id=tenant_id, actor_id=actor_id, actor_role=actor_role,
        action_type=AuditActionType.PERM_CHANGE.value, target_type="user", target_id=user.id,
        detail={"account": account, "role": role},
    )
    await db.commit()
    return {
        "user_id": user.id,
        "account": account,
        "role": role,
        "status": "1",
        "need_change_password": True,
        "created_time": user.create_time.isoformat() if user.create_time else None,
    }


async def update_user(
    db: AsyncSession, *, tenant_id: str, actor_id: str, actor_role: str, user_id: str, payload: dict
) -> dict:
    user = await db.scalar(
        select(User).where(User.id == user_id, User.tenant_id == tenant_id)
    )
    if user is None:
        raise BizError(USER_NOT_FOUND)

    for field in ("real_name", "title", "dept_code", "remark"):
        if field in payload and payload[field] is not None:
            setattr(user, field, payload[field])
    user.update_by = actor_id
    user.update_time = datetime.now(UTC)
    await _write_audit(
        db, tenant_id=tenant_id, actor_id=actor_id, actor_role=actor_role,
        action_type=AuditActionType.PERM_CHANGE.value, target_type="user", target_id=user.id,
    )
    await db.commit()
    return {"user_id": user_id}


async def toggle_user(
    db: AsyncSession, *, tenant_id: str, actor_id: str, actor_role: str, user_id: str
) -> dict:
    user = await db.scalar(
        select(User).where(User.id == user_id, User.tenant_id == tenant_id)
    )
    if user is None:
        raise BizError(USER_NOT_FOUND)
    user.status = "0" if user.status == "1" else "1"
    user.update_by = actor_id
    user.update_time = datetime.now(UTC)
    await _write_audit(
        db, tenant_id=tenant_id, actor_id=actor_id, actor_role=actor_role,
        action_type=AuditActionType.PERM_CHANGE.value, target_type="user", target_id=user.id,
        detail={"status": user.status},
    )
    await db.commit()
    return {"user_id": user_id, "status": user.status}


# ---- 科室 -----------------------------------------------------------------


async def list_depts(
    db: AsyncSession,
    *,
    tenant_id: str,
    status: str | None,
    keyword: str | None,
    page: int = 1,
    size: int = 20,
) -> dict:
    conds = [Dept.tenant_id == tenant_id]
    if status:
        conds.append(Dept.status == status)
    if keyword:
        conds.append(or_(Dept.dept_code.ilike(f"%{keyword}%"), Dept.dept_name.ilike(f"%{keyword}%")))
    total = await db.scalar(select(func.count()).select_from(Dept).where(*conds))
    rows = (
        await db.scalars(
            select(Dept)
            .where(*conds)
            .order_by(Dept.sort_no.asc())
            .offset((page - 1) * size)
            .limit(size)
        )
    ).all()
    return {
        "total": total or 0,
        "items": [
            {
                "dept_id": d.id,
                "dept_code": d.dept_code,
                "dept_name": d.dept_name,
                "sub_specialty": d.sub_specialty,
                "parent_code": d.parent_code,
                "sort_no": d.sort_no,
                "status": d.status,
            }
            for d in rows
        ],
    }


async def create_dept(db: AsyncSession, *, tenant_id: str, actor_id: str, actor_role: str, payload: dict) -> dict:
    dept_code = payload["dept_code"]
    exists = await db.scalar(
        select(Dept).where(Dept.tenant_id == tenant_id, Dept.dept_code == dept_code)
    )
    if exists is not None:
        raise BizError(DEPT_CODE_EXISTS)
    dept = Dept(
        tenant_id=tenant_id,
        dept_code=dept_code,
        dept_name=payload["dept_name"],
        sub_specialty=payload.get("sub_specialty"),
        common_complaints=payload.get("common_complaints"),
        parent_code=payload.get("parent_code"),
        sort_no=payload.get("sort_no", 0),
        status="1",
        create_by=actor_id,
    )
    db.add(dept)
    await db.commit()
    return {"dept_id": dept.id, "dept_code": dept_code, "dept_name": dept.dept_name}


async def update_dept(db: AsyncSession, *, tenant_id: str, actor_id: str, actor_role: str, dept_id: str, payload: dict) -> dict:
    dept = await db.scalar(
        select(Dept).where(Dept.id == dept_id, Dept.tenant_id == tenant_id)
    )
    if dept is None:
        raise BizError(DEPT_NOT_FOUND)
    for field in ("dept_name", "sub_specialty", "common_complaints", "parent_code", "sort_no"):
        if field in payload and payload[field] is not None:
            setattr(dept, field, payload[field])
    dept.update_by = actor_id
    dept.update_time = datetime.now(UTC)
    await db.commit()
    return {"dept_id": dept_id}


async def toggle_dept(db: AsyncSession, *, tenant_id: str, actor_id: str, actor_role: str, dept_id: str) -> dict:
    dept = await db.scalar(
        select(Dept).where(Dept.id == dept_id, Dept.tenant_id == tenant_id)
    )
    if dept is None:
        raise BizError(DEPT_NOT_FOUND)
    dept.status = "0" if dept.status == "1" else "1"
    dept.update_by = actor_id
    dept.update_time = datetime.now(UTC)
    await db.commit()
    return {"dept_id": dept_id, "status": dept.status}


# ---- 机构信息与系统配置 ---------------------------------------------------


async def get_org(db: AsyncSession, *, tenant_id: str) -> dict:
    tenant = await db.scalar(select(Tenant).where(Tenant.id == tenant_id))
    if tenant is None:
        raise BizError(TENANT_NOT_FOUND)
    return {
        "tenant_id": tenant.id,
        "tenant_code": tenant.tenant_code,
        "tenant_name": tenant.tenant_name,
        "hospital_level": tenant.hospital_level,
        "contact_person": tenant.contact_person,
        "contact_phone": tenant.contact_phone,
        "status": tenant.status,
    }


async def update_org(db: AsyncSession, *, tenant_id: str, actor_id: str, actor_role: str, payload: dict) -> dict:
    tenant = await db.scalar(select(Tenant).where(Tenant.id == tenant_id))
    if tenant is None:
        raise BizError(TENANT_NOT_FOUND)
    for field in ("tenant_name", "hospital_level", "contact_person", "contact_phone"):
        if field in payload and payload[field] is not None:
            setattr(tenant, field, payload[field])
    await db.commit()
    return await get_org(db, tenant_id=tenant_id)


async def list_configs(db: AsyncSession, *, tenant_id: str) -> dict:
    rows = (await db.scalars(select(SysConfig).where(SysConfig.tenant_id == tenant_id))).all()
    return {
        "total": len(rows),
        "items": [
            {
                "config_key": c.config_key,
                "config_value": "******" if c.is_encrypted == "1" else c.config_value,
                "config_type": c.config_type,
                "description": c.description,
            }
            for c in rows
        ],
    }


async def update_config(
    db: AsyncSession, *, tenant_id: str, actor_id: str, actor_role: str, config_key: str, config_value: str
) -> dict:
    config = await db.scalar(
        select(SysConfig).where(SysConfig.tenant_id == tenant_id, SysConfig.config_key == config_key)
    )
    if config is None:
        raise BizError(CONFIG_NOT_FOUND)
    config.config_value = config_value
    config.update_by = actor_id
    config.update_time = datetime.now(UTC)
    await db.commit()
    return {"config_key": config_key, "config_type": config.config_type}


# ---- 模型配置 -------------------------------------------------------------


async def list_model_providers(db: AsyncSession, *, tenant_id: str) -> dict:
    rows = (
        await db.scalars(select(ModelProvider).where(ModelProvider.tenant_id == tenant_id))
    ).all()
    return {
        "total": len(rows),
        "items": [
            {
                "provider_id": p.id,
                "provider_code": p.provider_code,
                "provider_type": p.provider_type,
                "provider_name": p.provider_name,
                "base_url": p.base_url,
                "model_name": p.model_name,
                "is_default": p.is_default == "1",
                "is_on_prem": p.is_on_prem == "1",
                "status": p.status,
                # 只下发"是否已配置"，绝不返回密钥本身或可逆密文
                "api_key_configured": bool(p.api_key_enc),
            }
            for p in rows
        ],
    }


async def create_model_provider(db: AsyncSession, *, tenant_id: str, actor_id: str, payload: dict) -> dict:
    exists = await db.scalar(
        select(ModelProvider).where(
            ModelProvider.tenant_id == tenant_id,
            ModelProvider.provider_code == payload["provider_code"],
        )
    )
    if exists is not None:
        raise BizError(MODEL_PROVIDER_CODE_EXISTS)
    p = ModelProvider(
        tenant_id=tenant_id,
        provider_code=payload["provider_code"],
        provider_type=payload["provider_type"],
        provider_name=payload.get("provider_name"),
        base_url=payload["base_url"],
        model_name=payload.get("model_name"),
        api_key_enc=encrypt_secret(payload.get("api_key_enc")),
        is_on_prem="1" if payload.get("is_on_prem") else "0",
        timeout_seconds=payload.get("timeout_seconds", 60),
        extra_json=payload.get("extra_json"),
        status="1",
        create_by=actor_id,
    )
    db.add(p)
    await db.commit()
    return {"provider_id": p.id, "provider_code": p.provider_code}


async def update_model_provider(db: AsyncSession, *, tenant_id: str, actor_id: str, provider_id: str, payload: dict) -> dict:
    p = await db.scalar(
        select(ModelProvider).where(ModelProvider.id == provider_id, ModelProvider.tenant_id == tenant_id)
    )
    if p is None:
        raise BizError(MODEL_PROVIDER_NOT_FOUND)
    for field in ("provider_name", "base_url", "model_name", "api_key_enc", "timeout_seconds", "extra_json"):
        if field in payload and payload[field] is not None:
            value = payload[field]
            if field == "api_key_enc":
                value = encrypt_secret(value)
            setattr(p, field, value)
    p.update_by = actor_id
    p.update_time = datetime.now(UTC)
    await db.commit()
    return {"provider_id": provider_id}


async def set_default_model_provider(db: AsyncSession, *, tenant_id: str, actor_id: str, provider_id: str) -> dict:
    p = await db.scalar(
        select(ModelProvider).where(ModelProvider.id == provider_id, ModelProvider.tenant_id == tenant_id)
    )
    if p is None:
        raise BizError(MODEL_PROVIDER_NOT_FOUND)
    # 同类型取消默认，本配置设为默认
    others = (await db.scalars(
        select(ModelProvider).where(
            ModelProvider.tenant_id == tenant_id, ModelProvider.provider_type == p.provider_type
        )
    )).all()
    for o in others:
        o.is_default = "0"
    p.is_default = "1"
    await db.commit()
    return {"provider_id": provider_id, "provider_type": p.provider_type, "is_default": True}


# ---- 审计日志 -------------------------------------------------------------


async def list_audit_logs(
    db: AsyncSession, *, tenant_id: str, page: int, size: int,
    action_type: str | None, actor_id: str | None, target_type: str | None,
) -> dict:
    conds = [AuditLog.tenant_id == tenant_id]
    if action_type:
        conds.append(AuditLog.action_type == action_type)
    if actor_id:
        conds.append(AuditLog.actor_id == actor_id)
    if target_type:
        conds.append(AuditLog.target_type == target_type)
    total = await db.scalar(select(func.count()).select_from(AuditLog).where(*conds))
    rows = (
        await db.scalars(
            select(AuditLog).where(*conds).order_by(AuditLog.action_time.desc())
            .offset((page - 1) * size).limit(size)
        )
    ).all()
    return {
        "total": total,
        "page": page,
        "size": size,
        "items": [
            {
                "audit_id": a.id,
                "actor_id": a.actor_id,
                "actor_role": a.actor_role,
                "action_type": a.action_type,
                "target_type": a.target_type,
                "target_id": a.target_id,
                "session_id": a.session_id,
                "result": a.result,
                "detail": a.detail_json,
                "action_time": a.action_time.isoformat() if a.action_time else None,
            }
            for a in rows
        ],
    }
