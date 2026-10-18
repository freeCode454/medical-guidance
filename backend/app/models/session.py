"""会话域模型：会话、消息、分诊结论、分诊修正、MDT 会诊。

覆盖 init.sql 中 5 张表：
    mg_session / mg_session_message / mg_triage_result /
    mg_triage_correction / mg_mdt_council
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Index, Integer, Numeric, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.mixins import AuditMixin, PKMixin, TenantMixin


class Session(Base, PKMixin, TenantMixin, AuditMixin):
    """预问诊会话：一次预问诊的全过程。id 同时作为编排层会话标识与检查点线程标识。"""

    __tablename__ = "mg_session"

    session_no: Mapped[str] = mapped_column(String(64), nullable=False, comment="会话业务编号，租户内唯一")
    patient_id: Mapped[str] = mapped_column(String(32), nullable=False, comment="患者标识")
    doctor_id: Mapped[str | None] = mapped_column(String(32), comment="接诊医生标识")
    dept_code: Mapped[str | None] = mapped_column(String(32), comment="最终建议科室编码")
    chief_complaint: Mapped[str | None] = mapped_column(String, comment="主诉原文")
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="IN_PROGRESS",
        server_default="IN_PROGRESS",
        comment="状态：IN_PROGRESS / FINISHED / PENDING_TAKEOVER / TAKEN_OVER / CLOSED / EMERGENCY",
    )
    risk_flag: Mapped[str] = mapped_column(
        String(1), nullable=False, default="0", server_default="0", comment="风险标记：1 高风险 / 0 正常"
    )
    inquiry_rounds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0", comment="已追问轮次"
    )
    sufficiency_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4), comment="最后一次信息充分度评分"
    )
    device_id: Mapped[str | None] = mapped_column(String(128), comment="设备密钥指纹，用于匿名会话恢复")
    started_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), comment="会话开始时间"
    )
    finished_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), comment="会话结束时间")
    expire_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), comment="会话有效期")

    __table_args__ = (
        UniqueConstraint("tenant_id", "session_no", name="uk_mg_session_tenant_no"),
        Index("idx_mg_session_tenant_patient", "tenant_id", "patient_id", text("started_time DESC")),
        Index("idx_mg_session_tenant_doctor", "tenant_id", "doctor_id", "status"),
        Index(
            "idx_mg_session_tenant_takeover",
            "tenant_id",
            "started_time",
            postgresql_where=text("status = 'PENDING_TAKEOVER'"),
        ),
        Index("idx_mg_session_tenant_device", "tenant_id", "device_id", "status"),
    )


class SessionMessage(Base, PKMixin, TenantMixin, AuditMixin):
    """会话消息：对话逐条记录，全库行数最多的表。"""

    __tablename__ = "mg_session_message"

    session_id: Mapped[str] = mapped_column(String(32), nullable=False, comment="会话标识")
    seq_no: Mapped[int] = mapped_column(Integer, nullable=False, comment="会话内序号，从 1 递增")
    role: Mapped[str] = mapped_column(String(16), nullable=False, comment="消息角色：PATIENT / AI / DOCTOR / SYSTEM")
    content: Mapped[str] = mapped_column(String, nullable=False, comment="消息内容")
    msg_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="TEXT",
        server_default="TEXT",
        comment="消息类型：TEXT / VOICE / BODY_MAP / RESULT / EMERGENCY",
    )
    extra_json: Mapped[dict | None] = mapped_column(JSONB, comment="附加信息")
    send_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), comment="发送时间"
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "session_id", "seq_no", name="uk_mg_msg_tenant_session_seq"),
        Index("idx_mg_msg_tenant_session_time", "tenant_id", "session_id", "send_time"),
    )


class TriageResult(Base, PKMixin, TenantMixin, AuditMixin):
    """分诊结论：会话产出的科室建议与路由结果。候选科室与依据用 JSONB 快照存储。"""

    __tablename__ = "mg_triage_result"

    session_id: Mapped[str] = mapped_column(String(32), nullable=False, comment="会话标识")
    candidates_json: Mapped[list] = mapped_column(JSONB, nullable=False, comment="候选科室列表")
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), comment="整体置信度")
    route: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="路由去向：DIRECT / MDT / MANUAL / EMERGENCY"
    )
    retrieval_mode: Mapped[str | None] = mapped_column(
        String(16), comment="检索模式：DENSE / SPARSE / HYBRID"
    )
    evidence_json: Mapped[dict | None] = mapped_column(JSONB, comment="判断依据")
    kb_version: Mapped[str | None] = mapped_column(String(64), comment="决策依据的知识库版本")
    doctor_confirmed: Mapped[str] = mapped_column(
        String(1), nullable=False, default="0", server_default="0", comment="医生是否已确认：1 是 / 0 否"
    )
    confirmed_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), comment="医生确认时间")

    __table_args__ = (
        UniqueConstraint("session_id", name="uk_mg_triage_session"),
        Index("idx_mg_triage_tenant_route", "tenant_id", "route", text("create_time DESC")),
        Index("idx_mg_triage_tenant_confirm", "tenant_id", "doctor_confirmed"),
        Index("idx_mg_triage_candidates_gin", "candidates_json", postgresql_using="gin"),
    )


class TriageCorrection(Base, PKMixin, TenantMixin, AuditMixin):
    """分诊修正记录：医生修正留痕，评测样本来源。职称采用快照存储。"""

    __tablename__ = "mg_triage_correction"

    triage_id: Mapped[str] = mapped_column(String(32), nullable=False, comment="分诊结论标识")
    session_id: Mapped[str] = mapped_column(String(32), nullable=False, comment="会话标识，冗余存储")
    before_dept: Mapped[str] = mapped_column(String(32), nullable=False, comment="修正前科室编码")
    after_dept: Mapped[str] = mapped_column(String(32), nullable=False, comment="修正后科室编码")
    reason: Mapped[str] = mapped_column(String(500), nullable=False, comment="修正理由，不少于 10 字")
    doctor_id: Mapped[str] = mapped_column(String(32), nullable=False, comment="修正人标识")
    doctor_title: Mapped[str] = mapped_column(String(32), nullable=False, comment="修正人职称快照")
    usable_for_eval: Mapped[str] = mapped_column(
        String(1), nullable=False, default="0", server_default="0", comment="是否可用于评测：1 是 / 0 否"
    )

    __table_args__ = (
        Index("idx_mg_corr_tenant_triage", "tenant_id", "triage_id"),
        Index(
            "idx_mg_corr_tenant_eval",
            "tenant_id",
            text("create_time DESC"),
            postgresql_where=text("usable_for_eval = '1'"),
        ),
    )


class MdtCouncil(Base, PKMixin, TenantMixin, AuditMixin):
    """多学科会诊记录：多个专科角色并行判断与汇总结果。分歧必须显式保留。"""

    __tablename__ = "mg_mdt_council"

    session_id: Mapped[str] = mapped_column(String(32), nullable=False, comment="会话标识")
    trigger_reason: Mapped[str] = mapped_column(String(255), nullable=False, comment="触发原因")
    candidate_depts: Mapped[list[str]] = mapped_column(
        ARRAY(String(32)), nullable=False, comment="参与会诊的候选科室编码列表"
    )
    opinions_json: Mapped[list] = mapped_column(JSONB, nullable=False, comment="各专科意见")
    consensus_dept: Mapped[str | None] = mapped_column(String(32), comment="综合推荐科室编码")
    consensus_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), comment="综合置信度")
    divergence_flag: Mapped[str] = mapped_column(
        String(1), nullable=False, default="0", server_default="0", comment="是否存在分歧：1 是 / 0 否"
    )
    divergence_json: Mapped[dict | None] = mapped_column(JSONB, comment="分歧点明细")
    missing_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0", comment="未返回结论的专科角色数量"
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, comment="会诊总耗时（毫秒）")

    __table_args__ = (
        Index("idx_mg_mdt_tenant_session", "tenant_id", "session_id", "create_time"),
        Index(
            "idx_mg_mdt_tenant_divergence",
            "tenant_id",
            text("create_time DESC"),
            postgresql_where=text("divergence_flag = '1'"),
        ),
        Index("idx_mg_mdt_opinions_gin", "opinions_json", postgresql_using="gin"),
    )
