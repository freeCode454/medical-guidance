"""系统支撑模型：模型服务配置、审计记录、文件。

覆盖 init.sql 中 3 张表：
    mg_model_provider / mg_audit_log / mg_file

mg_audit_log 为只追加表：不设 update_* / del_flag / remark，由数据库触发器防篡改。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.mixins import AppendOnlyMixin, AuditMixin, PKMixin, TenantMixin


class ModelProvider(Base, PKMixin, TenantMixin, AuditMixin):
    """模型服务配置：推理后端的可配置信息，密钥加密存储。"""

    __tablename__ = "mg_model_provider"

    provider_code: Mapped[str] = mapped_column(String(64), nullable=False, comment="配置编码，租户内唯一")
    provider_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="类型：LLM / EMBEDDING / RERANK / ASR"
    )
    provider_name: Mapped[str | None] = mapped_column(String(128), comment="配置名称")
    base_url: Mapped[str] = mapped_column(String(500), nullable=False, comment="服务地址")
    model_name: Mapped[str | None] = mapped_column(String(128), comment="模型名称")
    api_key_enc: Mapped[str | None] = mapped_column(String(500), comment="访问密钥，加密存储")
    is_default: Mapped[str] = mapped_column(
        String(1), nullable=False, default="0", server_default="0", comment="是否同类型默认：1 是 / 0 否"
    )
    is_on_prem: Mapped[str] = mapped_column(
        String(1), nullable=False, default="0", server_default="0", comment="是否院内地址：1 是 / 0 否"
    )
    timeout_seconds: Mapped[int | None] = mapped_column(Integer, server_default="60", comment="调用超时（秒）")
    extra_json: Mapped[dict | None] = mapped_column(JSONB, comment="扩展参数")
    status: Mapped[str] = mapped_column(
        String(1), nullable=False, default="1", server_default="1", comment="状态：1 启用 / 0 停用"
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "provider_code", name="uk_mg_model_tenant_code"),
        Index(
            "idx_mg_model_tenant_type",
            "tenant_id",
            "provider_type",
            "is_default",
            postgresql_where=text("del_flag = '0'"),
        ),
    )


class AuditLog(Base, PKMixin, TenantMixin, AppendOnlyMixin):
    """审计记录：只追加、不可修改、不可删除。不与其他表建立逻辑关联。"""

    __tablename__ = "mg_audit_log"

    actor_id: Mapped[str | None] = mapped_column(String(32), comment="操作人标识，系统操作填 system")
    actor_role: Mapped[str | None] = mapped_column(String(32), comment="操作人角色")
    action_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="操作类型：EMR_READ / EXTERNAL_CALL / TRIAGE_CONFIRM / TRIAGE_CORRECT / "
        "PERM_CHANGE / KB_CHANGE / EGRESS_BLOCK / DATA_ARCHIVE",
    )
    target_type: Mapped[str | None] = mapped_column(String(64), comment="操作对象类型")
    target_id: Mapped[str | None] = mapped_column(String(32), comment="操作对象标识")
    patient_hash: Mapped[str | None] = mapped_column(String(64), comment="涉及的患者标识哈希，不存明文")
    session_id: Mapped[str | None] = mapped_column(String(32), comment="关联会话标识")
    result: Mapped[str] = mapped_column(
        String(16), nullable=False, default="SUCCESS", server_default="SUCCESS", comment="结果：SUCCESS / FAILURE"
    )
    fail_reason: Mapped[str | None] = mapped_column(String(255), comment="失败原因")
    detail_json: Mapped[dict | None] = mapped_column(JSONB, comment="附加信息")
    client_ip: Mapped[str | None] = mapped_column(String(64), comment="客户端地址")
    trace_id: Mapped[str | None] = mapped_column(String(64), comment="追踪标识，用于关联可观测链路")
    action_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), comment="操作时间"
    )

    __table_args__ = (
        Index("idx_mg_audit_tenant_time", "tenant_id", text("action_time DESC")),
        Index("idx_mg_audit_tenant_patient", "tenant_id", "patient_hash", text("action_time DESC")),
        Index("idx_mg_audit_tenant_actor", "tenant_id", "actor_id", text("action_time DESC")),
        Index("idx_mg_audit_tenant_action", "tenant_id", "action_type", text("action_time DESC")),
        Index("idx_mg_audit_trace", "tenant_id", "trace_id"),
    )


class File(Base, PKMixin, TenantMixin, AuditMixin):
    """文件与对象：上传文件元信息，二进制内容存对象存储。"""

    __tablename__ = "mg_file"

    file_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="原始文件名（含扩展名）")
    file_ext: Mapped[str | None] = mapped_column(String(16), comment="扩展名，小写且不含点")
    mime_type: Mapped[str | None] = mapped_column(String(128), comment="MIME 类型")
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="文件字节数")
    file_hash: Mapped[str | None] = mapped_column(String(64), comment="内容 SHA-256")
    bucket_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="对象存储桶名")
    object_key: Mapped[str] = mapped_column(String(500), nullable=False, comment="对象键")
    biz_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="业务类型：EMR_ATTACHMENT / VOICE_INPUT / OTHER"
    )
    session_id: Mapped[str | None] = mapped_column(String(32), comment="关联会话标识")
    patient_id: Mapped[str | None] = mapped_column(String(32), comment="关联患者标识")
    biz_ref_id: Mapped[str | None] = mapped_column(String(32), comment="关联业务对象标识")
    upload_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="DONE", server_default="DONE",
        comment="上传状态：UPLOADING / DONE / FAILED",
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "object_key", name="uk_mg_file_tenant_object"),
        Index("idx_mg_file_tenant_session", "tenant_id", "session_id", postgresql_where=text("del_flag = '0'")),
        Index(
            "idx_mg_file_tenant_biz",
            "tenant_id",
            "biz_type",
            "biz_ref_id",
            postgresql_where=text("del_flag = '0'"),
        ),
        Index("idx_mg_file_tenant_hash", "tenant_id", "file_hash"),
    )
