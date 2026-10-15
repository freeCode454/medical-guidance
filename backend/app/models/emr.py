"""病历域模型：预问诊病历、既往病历文书。

覆盖 init.sql 中 2 张表：
    mg_emr_record / mg_emr_document
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Index, Numeric, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.mixins import AuditMixin, PKMixin, TenantMixin


class EmrRecord(Base, PKMixin, TenantMixin, AuditMixin):
    """预问诊病历：SOAP 结构化病历。SOAP 四段独立字段存储，便于按端控制返回。"""

    __tablename__ = "mg_emr_record"

    session_id: Mapped[str] = mapped_column(String(32), nullable=False, comment="会话标识")
    patient_id: Mapped[str] = mapped_column(String(32), nullable=False, comment="患者标识")
    subjective: Mapped[str | None] = mapped_column(String, comment="S 段：主观资料")
    objective: Mapped[str | None] = mapped_column(String, comment="O 段：客观资料")
    assessment: Mapped[str | None] = mapped_column(String, comment="A 段：评估，仅医生端可见")
    plan: Mapped[str | None] = mapped_column(String, comment="P 段：计划，不得含用药建议")
    soap_json: Mapped[dict | None] = mapped_column(JSONB, comment="SOAP 四段结构化版本")
    source_refs_json: Mapped[dict | None] = mapped_column(JSONB, comment="各段内容的来源引用")
    schema_version: Mapped[str] = mapped_column(
        String(16), nullable=False, default="1.0", server_default="1.0", comment="病历结构版本"
    )
    completeness_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), comment="字段完整率")
    generate_status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="SUCCESS",
        server_default="SUCCESS",
        comment="生成状态：SUCCESS / PARTIAL / FAILED",
    )

    __table_args__ = (
        UniqueConstraint("session_id", name="uk_mg_emr_record_session"),
        Index("idx_mg_emr_record_tenant_patient", "tenant_id", "patient_id", text("create_time DESC")),
        Index("idx_mg_emr_record_tenant_status", "tenant_id", "generate_status"),
    )


class EmrDocument(Base, PKMixin, TenantMixin, AuditMixin):
    """既往病历文书：门诊/入院/病程/出院小结等。section_json 是分块检索的前提。"""

    __tablename__ = "mg_emr_document"

    patient_id: Mapped[str] = mapped_column(String(32), nullable=False, comment="患者标识")
    doc_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="文书类型：OUTPATIENT / ADMISSION / PROGRESS / DISCHARGE / CONSULT",
    )
    doc_title: Mapped[str | None] = mapped_column(String(255), comment="文书标题")
    dept_code: Mapped[str | None] = mapped_column(String(32), comment="所属科室编码")
    record_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="记录日期，用于时间衰减重排"
    )
    doc_content: Mapped[str] = mapped_column(String, nullable=False, comment="文书正文")
    section_json: Mapped[dict | None] = mapped_column(JSONB, comment="按语义小节切分的内容")
    icd10_codes: Mapped[list[str] | None] = mapped_column(ARRAY(String(16)), comment="涉及疾病编码列表")
    source_system: Mapped[str | None] = mapped_column(String(64), comment="来源系统标识")
    doc_no: Mapped[str | None] = mapped_column(String(64), comment="院内文书编号")

    __table_args__ = (
        Index("idx_mg_emrdoc_tenant_patient_time", "tenant_id", "patient_id", text("record_time DESC")),
        Index("idx_mg_emrdoc_tenant_type", "tenant_id", "patient_id", "doc_type"),
        Index("idx_mg_emrdoc_section_gin", "section_json", postgresql_using="gin"),
    )
