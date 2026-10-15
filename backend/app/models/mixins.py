"""字段混入：主键、租户、审计、只追加。

审计字段体系（与 init.sql 严格一致）
-------------------------------------
标准表含 7 项审计字段：
    tenant_id / create_by / create_time / update_by / update_time / del_flag / remark

只追加表（4 张，不设 ``update_*`` / ``del_flag`` / ``remark``）：
    mg_kb_entry_history / mg_kb_publish / mg_golden_query_run / mg_audit_log
    → 使用 :class:`AppendOnlyMixin`（仅 ``create_by`` / ``create_time``）

mg_tenant 是唯一**不含** tenant_id 的表（数据隔离的根）。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import gen_id


class PKMixin:
    """32 位无连字符主键。"""

    id: Mapped[str] = mapped_column(
        String(32), primary_key=True, default=gen_id, comment="主键，32 位无连字符字符串"
    )


class TenantMixin:
    """租户标识（mg_tenant 自身不含该字段）。"""

    tenant_id: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="租户标识，所有复合索引首列"
    )


class AuditMixin:
    """标准审计字段（不含 tenant_id，由 TenantMixin 提供）。"""

    create_by: Mapped[str | None] = mapped_column(String(32), comment="创建人标识")
    create_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), comment="创建时间"
    )
    update_by: Mapped[str | None] = mapped_column(String(32), comment="最后更新人标识")
    update_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="最后更新时间，由应用层维护"
    )
    del_flag: Mapped[str] = mapped_column(
        String(1), nullable=False, server_default="0", comment="软删除标记：0 正常 / 1 已删除"
    )
    remark: Mapped[str | None] = mapped_column(String(500), comment="备注")


class AppendOnlyMixin:
    """只追加表审计字段（无 update_* / del_flag / remark）。"""

    create_by: Mapped[str | None] = mapped_column(String(32), comment="创建人标识")
    create_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), comment="创建时间"
    )
