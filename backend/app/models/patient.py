"""患者域模型：患者、授权记录、挂号。

覆盖 init.sql 中 3 张表：
    mg_patient / mg_patient_consent / mg_appointment
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.mixins import AuditMixin, PKMixin, TenantMixin


class Patient(Base, PKMixin, TenantMixin, AuditMixin):
    """患者：不含身份信息，仅存哈希与分诊特征。"""

    __tablename__ = "mg_patient"

    patient_hash: Mapped[str] = mapped_column(String(64), nullable=False, comment="患者标识哈希，加盐后计算")
    patient_no: Mapped[str | None] = mapped_column(String(64), comment="院内患者编号，用于脱敏展示")
    account: Mapped[str | None] = mapped_column(String(64), comment="患者登录账号，租户内唯一")
    credential_hash: Mapped[str | None] = mapped_column(String(255), comment="患者口令哈希，可空表示匿名患者")
    fail_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0", comment="连续登录失败次数"
    )
    lock_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), comment="锁定截止时间")
    last_login_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), comment="最后登录时间")
    age: Mapped[int | None] = mapped_column(Integer, comment="年龄")
    gender: Mapped[str | None] = mapped_column(String(1), comment="性别：1 男 / 2 女 / 0 未知")
    phone_masked: Mapped[str | None] = mapped_column(String(32), comment="手机号脱敏形式")
    phone_hash: Mapped[str | None] = mapped_column(String(64), comment="手机号哈希，不存明文")
    device_id: Mapped[str | None] = mapped_column(String(128), comment="设备密钥指纹（不存明文）")
    status: Mapped[str] = mapped_column(
        String(1), nullable=False, default="1", server_default="1", comment="状态：1 正常 / 0 停用"
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "patient_hash", name="uk_mg_patient_tenant_hash"),
        UniqueConstraint("tenant_id", "account", name="uk_mg_patient_tenant_account"),
        Index("idx_mg_patient_tenant_phone", "tenant_id", "phone_hash"),
        Index("idx_mg_patient_tenant_device", "tenant_id", "device_id"),
    )


class PatientConsent(Base, PKMixin, TenantMixin, AuditMixin):
    """患者授权记录：既往病历调阅授权。"""

    __tablename__ = "mg_patient_consent"

    patient_id: Mapped[str] = mapped_column(String(32), nullable=False, comment="患者标识")
    session_id: Mapped[str | None] = mapped_column(String(32), comment="触发授权的会话标识")
    consent_scope: Mapped[str] = mapped_column(String(255), nullable=False, comment="授权范围说明")
    consent_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()", comment="授权时间"
    )
    expire_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), comment="失效时间，空表示长期有效")
    consent_channel: Mapped[str | None] = mapped_column(String(32), comment="授权渠道：患者端 / 线下")
    revoke_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), comment="撤回时间，空表示未撤回")

    __table_args__ = (
        Index(
            "idx_mg_consent_tenant_patient",
            "tenant_id",
            "patient_id",
            text("consent_time DESC"),
        ),
        Index("idx_mg_consent_tenant_session", "tenant_id", "session_id"),
    )


class Appointment(Base, PKMixin, TenantMixin, AuditMixin):
    """挂号记录：号源预约结果。appointment_no 是幂等键。"""

    __tablename__ = "mg_appointment"

    appointment_no: Mapped[str] = mapped_column(String(64), nullable=False, comment="预约单号，幂等键")
    session_id: Mapped[str | None] = mapped_column(String(32), comment="来源会话标识")
    patient_id: Mapped[str | None] = mapped_column(String(32), comment="患者标识")
    dept_code: Mapped[str] = mapped_column(String(32), nullable=False, comment="挂号科室编码")
    doctor_id: Mapped[str | None] = mapped_column(String(32), comment="医生标识")
    schedule_date: Mapped[date] = mapped_column(Date, nullable=False, comment="就诊日期")
    time_slot: Mapped[str | None] = mapped_column(String(32), comment="就诊时段")
    slot_id: Mapped[str | None] = mapped_column(String(64), comment="外部系统号源标识")
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="BOOKED",
        server_default="BOOKED",
        comment="状态：BOOKED / CANCELLED / COMPLETED / NOSHOW",
    )
    cancel_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), comment="取消时间")
    external_order_id: Mapped[str | None] = mapped_column(String(64), comment="外部系统返回的订单标识")

    __table_args__ = (
        UniqueConstraint("tenant_id", "appointment_no", name="uk_mg_appt_tenant_no"),
        Index("idx_mg_appt_tenant_session", "tenant_id", "session_id"),
        Index("idx_mg_appt_tenant_patient", "tenant_id", "patient_id", text("schedule_date DESC")),
        Index("idx_mg_appt_tenant_slot", "tenant_id", "slot_id", "status"),
    )
