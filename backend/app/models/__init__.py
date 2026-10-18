"""数据模型层：SQLAlchemy ORM 模型，与 init.sql 逐列一致。

23 张表对应 23 个模型类，按领域分文件：
    org.py      → Tenant / Dept / SysConfig / User
    patient.py  → Patient / PatientConsent / Appointment
    session.py  → Session / SessionMessage / TriageResult / TriageCorrection / MdtCouncil
    emr.py      → EmrRecord / EmrDocument
    kb.py       → KbEntry / KbEntryHistory / KbPublish / KbIngestTask / GoldenQuery / GoldenQueryRun
    system.py   → ModelProvider / AuditLog / File

导入本包即完成所有模型向 Base.metadata 的注册（供 Alembic 与运行时建表使用）。
"""
from app.models.base import Base, gen_id
from app.models.emr import EmrDocument, EmrRecord
from app.models.kb import (
    GoldenQuery,
    GoldenQueryRun,
    KbEntry,
    KbEntryHistory,
    KbIngestTask,
    KbPublish,
)
from app.models.mixins import AppendOnlyMixin, AuditMixin, PKMixin, TenantMixin
from app.models.org import Dept, SysConfig, Tenant, User
from app.models.patient import Appointment, Patient, PatientConsent
from app.models.session import (
    MdtCouncil,
    Session,
    SessionMessage,
    TriageCorrection,
    TriageResult,
)
from app.models.system import AuditLog, File, ModelProvider

__all__ = [
    "AppendOnlyMixin",
    "Appointment",
    "AuditLog",
    "AuditMixin",
    "Base",
    "Dept",
    "EmrDocument",
    "EmrRecord",
    "File",
    "GoldenQuery",
    "GoldenQueryRun",
    "KbEntry",
    "KbEntryHistory",
    "KbIngestTask",
    "KbPublish",
    "MdtCouncil",
    "ModelProvider",
    "PKMixin",
    "Patient",
    "PatientConsent",
    "Session",
    "SessionMessage",
    "SysConfig",
    "Tenant",
    "TenantMixin",
    "TriageCorrection",
    "TriageResult",
    "User",
    "gen_id",
]
