"""知识库域模型：条目、变更记录、发布版本、入库任务、黄金查询、回归执行。

覆盖 init.sql 中 6 张表：
    mg_kb_entry / mg_kb_entry_history / mg_kb_publish /
    mg_kb_ingest_task / mg_golden_query / mg_golden_query_run

其中 3 张只追加表（不含 update_* / del_flag / remark）：
    mg_kb_entry_history / mg_kb_publish / mg_golden_query_run
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Index, Integer, Numeric, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.mixins import AppendOnlyMixin, AuditMixin, PKMixin, TenantMixin


class KbEntry(Base, PKMixin, TenantMixin, AuditMixin):
    """知识库条目：知识库的唯一真相，向量库由此派生。"""

    __tablename__ = "mg_kb_entry"

    kb_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="知识类型：DEPT_EXPERTISE / SYMPTOM_DISEASE / GUIDELINE / ICD-10 / DRUG_SAFETY / CASE",
    )
    entry_code: Mapped[str] = mapped_column(String(128), nullable=False, comment="条目标识，入库幂等键")
    title: Mapped[str | None] = mapped_column(String(255), comment="标题")
    content: Mapped[str] = mapped_column(String, nullable=False, comment="正文内容，用于向量化与全文检索")
    content_json: Mapped[dict | None] = mapped_column(JSONB, comment="结构化附加内容")
    dept_code: Mapped[str | None] = mapped_column(String(32), comment="归属科室编码")
    icd10_codes: Mapped[list[str] | None] = mapped_column(ARRAY(String(16)), comment="涉及疾病编码列表")
    age_group: Mapped[str | None] = mapped_column(String(16), comment="适用年龄段：child / adult / elderly / all")
    gender: Mapped[str | None] = mapped_column(String(1), comment="适用性别：1 男 / 2 女 / 0 通用")
    source: Mapped[str | None] = mapped_column(String(255), comment="来源说明")
    entry_version: Mapped[str | None] = mapped_column(String(32), comment="条目版本")
    status: Mapped[str] = mapped_column(
        String(1), nullable=False, default="0", server_default="0", comment="状态：0 草稿 / 1 已发布 / 2 已停用"
    )
    is_active: Mapped[str] = mapped_column(
        String(1), nullable=False, default="0", server_default="0", comment="是否参与检索：1 参与 / 0 不参与"
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "entry_code", name="uk_mg_kb_tenant_code"),
        Index("idx_mg_kb_tenant_type_status", "tenant_id", "kb_type", "status", "is_active"),
        Index("idx_mg_kb_tenant_dept", "tenant_id", "dept_code", postgresql_where=text("del_flag = '0'")),
        Index("idx_mg_kb_content_json_gin", "content_json", postgresql_using="gin"),
        Index(
            "idx_mg_kb_content_gin",
            text("to_tsvector('simple', coalesce(title, '') || ' ' || content)"),
            postgresql_using="gin",
        ),
    )


class KbEntryHistory(Base, PKMixin, TenantMixin, AppendOnlyMixin):
    """知识库变更记录：只追加，不设软删除标记。"""

    __tablename__ = "mg_kb_entry_history"

    entry_id: Mapped[str] = mapped_column(String(32), nullable=False, comment="条目标识")
    entry_code: Mapped[str] = mapped_column(String(128), nullable=False, comment="条目标识编码，冗余存储")
    change_type: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="变更类型：CREATE / UPDATE / ENABLE / DISABLE"
    )
    before_json: Mapped[dict | None] = mapped_column(JSONB, comment="变更前内容")
    after_json: Mapped[dict | None] = mapped_column(JSONB, comment="变更后内容")
    changed_fields: Mapped[list[str] | None] = mapped_column(ARRAY(String(32)), comment="本次变更涉及的字段名列表")
    operator: Mapped[str] = mapped_column(String(32), nullable=False, comment="操作人标识")
    operator_name: Mapped[str | None] = mapped_column(String(64), comment="操作人姓名快照")
    kb_version: Mapped[str | None] = mapped_column(String(64), comment="变更后的知识库版本标识")

    __table_args__ = (
        Index("idx_mg_kbh_tenant_entry", "tenant_id", "entry_id", text("create_time DESC")),
        Index("idx_mg_kbh_tenant_time", "tenant_id", text("create_time DESC")),
    )


class KbPublish(Base, PKMixin, TenantMixin, AppendOnlyMixin):
    """知识库发布版本：发布留痕与跨环境迁移介质。一期不支持回滚。"""

    __tablename__ = "mg_kb_publish"

    version_tag: Mapped[str] = mapped_column(String(64), nullable=False, comment="版本标识，租户内唯一")
    entry_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0", comment="发布的条目数"
    )
    snapshot_path: Mapped[str | None] = mapped_column(String(500), comment="快照文件位置")
    snapshot_hash: Mapped[str | None] = mapped_column(String(64), comment="快照内容哈希")
    published_by: Mapped[str] = mapped_column(String(32), nullable=False, comment="发布人标识")
    published_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()", comment="发布时间"
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "version_tag", name="uk_mg_kbpub_tenant_tag"),
        Index("idx_mg_kbpub_tenant_time", "tenant_id", text("published_time DESC")),
    )


class KbIngestTask(Base, PKMixin, TenantMixin, AuditMixin):
    """知识库入库任务：异步任务的执行记录与统计。"""

    __tablename__ = "mg_kb_ingest_task"

    task_no: Mapped[str] = mapped_column(String(64), nullable=False, comment="任务编号，租户内唯一")
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="PENDING", server_default="PENDING",
        comment="状态：PENDING / RUNNING / SUCCESS / FAILED / ABORTED",
    )
    stage: Mapped[str | None] = mapped_column(
        String(32), comment="当前阶段：VALIDATE / DIFF / EMBED / WRITE / VERIFY"
    )
    progress: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0", comment="进度百分比，0 到 100"
    )
    total_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0", comment="总条目数"
    )
    added_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0", comment="新增条目数"
    )
    updated_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0", comment="修改条目数"
    )
    disabled_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0", comment="停用条目数"
    )
    failed_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0", comment="校验失败条目数"
    )
    error_json: Mapped[dict | None] = mapped_column(JSONB, comment="失败条目明细")
    triggered_by: Mapped[str | None] = mapped_column(String(32), comment="触发人标识")
    started_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), comment="开始时间")
    finished_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), comment="完成时间")

    __table_args__ = (
        UniqueConstraint("tenant_id", "task_no", name="uk_mg_kbing_tenant_no"),
        Index(
            "idx_mg_kbing_tenant_status",
            "tenant_id",
            text("create_time DESC"),
            postgresql_where=text("status IN ('PENDING', 'RUNNING')"),
        ),
        Index("idx_mg_kbing_tenant_time", "tenant_id", text("create_time DESC")),
    )


class GoldenQuery(Base, PKMixin, TenantMixin, AuditMixin):
    """黄金查询集：知识库变更后的回归验证用例。"""

    __tablename__ = "mg_golden_query"

    query_code: Mapped[str] = mapped_column(String(64), nullable=False, comment="用例编号，租户内唯一")
    query_text: Mapped[str] = mapped_column(String, nullable=False, comment="查询文本，模拟患者主诉")
    expect_depts: Mapped[list[str] | None] = mapped_column(ARRAY(String(32)), comment="期望召回的科室编码列表")
    expect_not_depts: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(32)), comment="期望不应出现的科室编码列表"
    )
    expect_route: Mapped[str | None] = mapped_column(String(32), comment="期望的路由去向")
    category: Mapped[str | None] = mapped_column(String(64), comment="用例分类")
    is_active: Mapped[str] = mapped_column(
        String(1), nullable=False, default="1", server_default="1", comment="是否启用：1 启用 / 0 停用"
    )
    description: Mapped[str | None] = mapped_column(String(500), comment="用例说明")

    __table_args__ = (
        UniqueConstraint("tenant_id", "query_code", name="uk_mg_gq_tenant_code"),
        Index(
            "idx_mg_gq_tenant_active",
            "tenant_id",
            "category",
            postgresql_where=text("is_active = '1'"),
        ),
    )


class GoldenQueryRun(Base, PKMixin, TenantMixin, AppendOnlyMixin):
    """回归执行记录：黄金查询集的执行结果。"""

    __tablename__ = "mg_golden_query_run"

    run_no: Mapped[str] = mapped_column(String(64), nullable=False, comment="执行批次编号，租户内唯一")
    kb_version: Mapped[str | None] = mapped_column(String(64), comment="本次回归对应的知识库版本")
    retrieval_mode: Mapped[str | None] = mapped_column(String(16), comment="检索模式：DENSE / SPARSE / HYBRID")
    total_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0", comment="用例总数"
    )
    passed_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0", comment="通过数"
    )
    failed_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0", comment="失败数"
    )
    pass_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), comment="通过率")
    baseline_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), comment="基线通过率")
    is_regression: Mapped[str] = mapped_column(
        String(1), nullable=False, default="0", server_default="0", comment="是否低于基线：1 是 / 0 否"
    )
    failed_json: Mapped[dict | None] = mapped_column(JSONB, comment="失败用例明细")
    duration_ms: Mapped[int | None] = mapped_column(Integer, comment="总耗时（毫秒）")
    triggered_by: Mapped[str | None] = mapped_column(String(32), comment="触发人标识")

    __table_args__ = (
        UniqueConstraint("tenant_id", "run_no", name="uk_mg_gqr_tenant_no"),
        Index("idx_mg_gqr_tenant_time", "tenant_id", text("create_time DESC")),
        Index("idx_mg_gqr_tenant_mode", "tenant_id", "retrieval_mode", text("create_time DESC")),
    )
