"""业务枚举字典：与 init.sql 的 COMMENT 及《04-API 接口设计说明书》一致。

采用 ``enum.StrEnum``（Python 3.11+），成员即字符串值：
    - 可直接用于 ORM 赋值与 JSON 序列化
    - 与数据库中的字符串字面量（如 ``"IN_PROGRESS"``）``==`` 相等

约定：所有枚举值以数据库存储的字面量为唯一真相，禁止别名分裂。
"""
from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    """用户角色（mg_user.role）。患者不落 mg_user 表，其身份由会话匿名承载。"""

    DOCTOR = "DOCTOR"          # 医生
    KB_ADMIN = "KB_ADMIN"      # 知识库管理员
    ORG_ADMIN = "ORG_ADMIN"    # 机构管理员


class SessionStatus(StrEnum):
    """预问诊会话状态（mg_session.status）。"""

    IN_PROGRESS = "IN_PROGRESS"            # 进行中
    FINISHED = "FINISHED"                  # 已出结论
    PENDING_TAKEOVER = "PENDING_TAKEOVER"  # 待接管
    TAKEN_OVER = "TAKEN_OVER"              # 已接管
    CLOSED = "CLOSED"                      # 已结束
    EMERGENCY = "EMERGENCY"                # 已触发急诊


class TriageRoute(StrEnum):
    """分诊路由去向（mg_triage_result.route）。"""

    DIRECT = "DIRECT"        # 直接推荐
    MDT = "MDT"              # 多科会诊
    MANUAL = "MANUAL"        # 转人工
    EMERGENCY = "EMERGENCY"  # 急诊


class RetrievalMode(StrEnum):
    """检索模式（mg_triage_result.retrieval_mode / mg_golden_query_run.retrieval_mode）。"""

    DENSE = "DENSE"    # 仅语义（稠密向量）
    SPARSE = "SPARSE"  # 仅词元（稀疏/BM25）
    HYBRID = "HYBRID"  # 融合


class MessageRole(StrEnum):
    """会话消息角色（mg_session_message.role）。"""

    PATIENT = "PATIENT"
    AI = "AI"
    DOCTOR = "DOCTOR"
    SYSTEM = "SYSTEM"


class MessageType(StrEnum):
    """会话消息类型（mg_session_message.msg_type）。"""

    TEXT = "TEXT"          # 文字
    VOICE = "VOICE"        # 语音
    BODY_MAP = "BODY_MAP"  # 部位点选
    RESULT = "RESULT"      # 结果
    EMERGENCY = "EMERGENCY"  # 急诊告警


class KbType(StrEnum):
    """知识类型（mg_kb_entry.kb_type）。"""

    DEPT_EXPERTISE = "DEPT_EXPERTISE"  # 科室专长
    SYMPTOM_DISEASE = "SYMPTOM_DISEASE"  # 症状疾病
    GUIDELINE = "GUIDELINE"            # 诊疗指南
    ICD10 = "ICD-10"                   # ICD-10 编码对照
    DRUG_SAFETY = "DRUG_SAFETY"        # 用药禁忌
    CASE = "CASE"                      # 脱敏病例


class DocType(StrEnum):
    """病历文书类型（mg_emr_document.doc_type）。"""

    OUTPATIENT = "OUTPATIENT"  # 门诊病历
    ADMISSION = "ADMISSION"    # 入院记录
    PROGRESS = "PROGRESS"      # 病程记录
    DISCHARGE = "DISCHARGE"    # 出院小结
    CONSULT = "CONSULT"        # 会诊记录


class ProviderType(StrEnum):
    """模型服务类型（mg_model_provider.provider_type）。"""

    LLM = "LLM"              # 内容生成
    EMBEDDING = "EMBEDDING"  # 向量化
    RERANK = "RERANK"        # 精排
    ASR = "ASR"              # 语音识别


class AuditActionType(StrEnum):
    """审计操作类型（mg_audit_log.action_type）。"""

    EMR_READ = "EMR_READ"              # 病历读取
    EXTERNAL_CALL = "EXTERNAL_CALL"    # 外部调用
    TRIAGE_CONFIRM = "TRIAGE_CONFIRM"  # 分诊确认
    TRIAGE_CORRECT = "TRIAGE_CORRECT"  # 分诊修正
    PERM_CHANGE = "PERM_CHANGE"        # 权限变更
    KB_CHANGE = "KB_CHANGE"            # 知识库变更
    EGRESS_BLOCK = "EGRESS_BLOCK"      # 出域拦截
    DATA_ARCHIVE = "DATA_ARCHIVE"      # 数据归档


class AuditResult(StrEnum):
    """审计结果（mg_audit_log.result）。"""

    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


class AppointmentStatus(StrEnum):
    """挂号状态（mg_appointment.status）。"""

    BOOKED = "BOOKED"        # 已预约
    CANCELLED = "CANCELLED"  # 已取消
    COMPLETED = "COMPLETED"  # 已完成
    NOSHOW = "NOSHOW"        # 爽约


class IngestTaskStatus(StrEnum):
    """入库任务状态（mg_kb_ingest_task.status）。"""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    ABORTED = "ABORTED"


class IngestStage(StrEnum):
    """入库任务阶段（mg_kb_ingest_task.stage）。"""

    VALIDATE = "VALIDATE"  # 校验
    DIFF = "DIFF"          # 差异比对
    EMBED = "EMBED"        # 向量化
    WRITE = "WRITE"        # 写入
    VERIFY = "VERIFY"      # 验证


class ChangeType(StrEnum):
    """知识库变更类型（mg_kb_entry_history.change_type）。"""

    CREATE = "CREATE"    # 新增
    UPDATE = "UPDATE"    # 修改
    ENABLE = "ENABLE"    # 启用
    DISABLE = "DISABLE"  # 停用


class GenerateStatus(StrEnum):
    """病历生成状态（mg_emr_record.generate_status）。"""

    SUCCESS = "SUCCESS"  # 成功
    PARTIAL = "PARTIAL"  # 部分缺失
    FAILED = "FAILED"    # 失败


class FileBizType(StrEnum):
    """文件业务类型（mg_file.biz_type）。"""

    EMR_ATTACHMENT = "EMR_ATTACHMENT"  # 病历附件
    VOICE_INPUT = "VOICE_INPUT"        # 语音输入
    OTHER = "OTHER"                    # 其他


class UploadStatus(StrEnum):
    """文件上传状态（mg_file.upload_status）。"""

    UPLOADING = "UPLOADING"
    DONE = "DONE"
    FAILED = "FAILED"


class Gender(StrEnum):
    """性别。mg_patient 中 0 表示未知；mg_kb_entry 中 0 表示通用。"""

    MALE = "1"
    FEMALE = "2"
    UNKNOWN = "0"


class AgeGroup(StrEnum):
    """适用年龄段（mg_kb_entry.age_group）。"""

    CHILD = "child"
    ADULT = "adult"
    ELDERLY = "elderly"
    ALL = "all"


class KbEntryStatus(StrEnum):
    """知识条目状态（mg_kb_entry.status）。"""

    DRAFT = "0"        # 草稿
    PUBLISHED = "1"    # 已发布
    DISABLED = "2"     # 已停用


# --- char(1) 通用标志（1 / 0） -------------------------------------------

class DeleteFlag(StrEnum):
    """软删除标记（del_flag）。"""

    NORMAL = "0"
    DELETED = "1"


class EnableStatus(StrEnum):
    """启用/停用状态（status 等）。"""

    ENABLED = "1"
    DISABLED = "0"


class Flag(StrEnum):
    """通用布尔标志（risk_flag / divergence_flag / usable_for_eval 等）。"""

    YES = "1"
    NO = "0"
