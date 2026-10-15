"""组织域模型：租户、科室、系统配置、用户。

覆盖 init.sql 中 4 张表：
    mg_tenant / mg_dept / mg_sys_config / mg_user
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.mixins import AuditMixin, PKMixin, TenantMixin


class Tenant(Base, PKMixin, AuditMixin):
    """租户（机构）：数据隔离的边界。唯一不含 tenant_id 的表。"""

    __tablename__ = "mg_tenant"

    tenant_code: Mapped[str] = mapped_column(String(64), nullable=False, comment="租户编码，全局唯一")
    tenant_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="租户名称（医院名称）")
    hospital_level: Mapped[str | None] = mapped_column(String(32), comment="医院等级，如“三级甲等”")
    contact_person: Mapped[str | None] = mapped_column(String(64), comment="联系人")
    contact_phone: Mapped[str | None] = mapped_column(String(32), comment="联系电话")
    status: Mapped[str] = mapped_column(
        String(1), nullable=False, default="1", server_default="1", comment="状态：1 启用 / 0 停用"
    )
    expire_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), comment="到期时间")

    __table_args__ = (
        UniqueConstraint("tenant_code", name="uk_mg_tenant_code"),
        Index("idx_mg_tenant_status", "status", postgresql_where=text("del_flag = '0'")),
    )


class Dept(Base, PKMixin, TenantMixin, AuditMixin):
    """科室：分诊目标与知识库归属维度。"""

    __tablename__ = "mg_dept"

    dept_code: Mapped[str] = mapped_column(String(32), nullable=False, comment="科室编码，租户内唯一")
    dept_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="科室名称")
    sub_specialty: Mapped[list[str] | None] = mapped_column(ARRAY(String(32)), comment="亚专科列表")
    common_complaints: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(64)), comment="常见主诉列表"
    )
    parent_code: Mapped[str | None] = mapped_column(String(32), comment="上级科室编码，空表示一级科室")
    sort_no: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0", comment="排序号"
    )
    status: Mapped[str] = mapped_column(
        String(1), nullable=False, default="1", server_default="1", comment="状态：1 启用 / 0 停用"
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "dept_code", name="uk_mg_dept_tenant_code"),
        Index(
            "idx_mg_dept_tenant_status",
            "tenant_id",
            "status",
            postgresql_where=text("del_flag = '0'"),
        ),
    )


class SysConfig(Base, PKMixin, TenantMixin, AuditMixin):
    """系统配置：租户级可调参数。"""

    __tablename__ = "mg_sys_config"

    config_key: Mapped[str] = mapped_column(String(128), nullable=False, comment="配置键，租户内唯一")
    config_value: Mapped[str | None] = mapped_column(String, comment="配置值")
    config_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="string",
        server_default="string",
        comment="值类型：string / number / boolean / json",
    )
    is_encrypted: Mapped[str] = mapped_column(
        String(1), nullable=False, default="0", server_default="0", comment="值是否加密存储：1 是 / 0 否"
    )
    description: Mapped[str | None] = mapped_column(String(255), comment="配置项说明")
    status: Mapped[str] = mapped_column(
        String(1), nullable=False, default="1", server_default="1", comment="状态：1 启用 / 0 停用"
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "config_key", name="uk_mg_sys_config_tenant_key"),
    )


class User(Base, PKMixin, TenantMixin, AuditMixin):
    """用户：医生与管理员统一存储，以 role 区分。口令只存哈希。"""

    __tablename__ = "mg_user"

    account: Mapped[str] = mapped_column(String(64), nullable=False, comment="登录账号，租户内唯一")
    real_name: Mapped[str | None] = mapped_column(String(64), comment="真实姓名")
    role: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="角色：DOCTOR / KB_ADMIN / ORG_ADMIN"
    )
    title: Mapped[str | None] = mapped_column(String(32), comment="医师职称")
    dept_code: Mapped[str | None] = mapped_column(String(32), comment="所属科室编码，仅医生有值")
    credential_hash: Mapped[str] = mapped_column(String(255), nullable=False, comment="口令哈希，不可逆存储")
    fail_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0", comment="连续登录失败次数"
    )
    lock_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), comment="锁定截止时间")
    last_login_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), comment="最后登录时间")
    status: Mapped[str] = mapped_column(
        String(1), nullable=False, default="1", server_default="1", comment="状态：1 启用 / 0 停用"
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "account", name="uk_mg_user_tenant_account"),
        Index("idx_mg_user_tenant_dept", "tenant_id", "dept_code", "status"),
        Index("idx_mg_user_tenant_role", "tenant_id", "role", "status"),
    )
