"""错误码常量：与《04-API 接口设计说明书》第 4 章一致。

编码规则
--------
- ``200`` 成功
- ``400``~``599`` 通用错误，HTTP 状态码与 code 一致
- ``10xxx`` 认证与账号 / ``20xxx`` 会话与分诊 / ``30xxx`` 挂号与号源
- ``40xxx`` 知识库与检索 / ``50xxx`` 机构与配置 / ``60xxx`` 外部依赖与系统

三条设计约定
------------
1. ``404`` 不区分"不存在"与"无权访问"（避免探测其他租户资源是否存在）
2. 业务错误（``10xxx``~``60xxx``）的 HTTP 状态码统一为 ``200``
3. ``message`` 不含内部信息（不返回堆栈/SQL/内网地址），排查依赖 ``X-Trace-ID``
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorCode:
    """错误码定义。业务错误的 http_status 统一为 200。"""

    code: int
    message: str
    http_status: int = 200


# --- 通用错误码（HTTP 状态码与 code 一致） --------------------------------

OK = ErrorCode(200, "成功", 200)
BAD_REQUEST = ErrorCode(400, "参数校验失败", 400)
UNAUTHORIZED = ErrorCode(401, "未认证", 401)
FORBIDDEN = ErrorCode(403, "无权限", 403)
NOT_FOUND = ErrorCode(404, "资源不存在", 404)
CONFLICT = ErrorCode(409, "资源冲突", 409)
GONE = ErrorCode(410, "资源已失效", 410)
UNPROCESSABLE = ErrorCode(422, "业务规则校验失败", 422)
TOO_MANY_REQUESTS = ErrorCode(429, "请求过于频繁", 429)
INTERNAL_ERROR = ErrorCode(500, "服务器内部错误", 500)
UPSTREAM_FAILED = ErrorCode(502, "外部依赖调用失败", 502)
SERVICE_UNAVAILABLE = ErrorCode(503, "服务暂不可用", 503)
UPSTREAM_TIMEOUT = ErrorCode(504, "外部依赖超时", 504)


# --- 认证与账号（10xxx） --------------------------------------------------

AUTH_CREDENTIAL_INVALID = ErrorCode(10001, "账号或口令错误")
AUTH_ACCOUNT_LOCKED = ErrorCode(10002, "账号已锁定")
AUTH_ACCOUNT_DISABLED = ErrorCode(10003, "账号已停用")
AUTH_TOKEN_EXPIRED = ErrorCode(10004, "访问令牌已过期")
AUTH_TOKEN_INVALID = ErrorCode(10005, "令牌无效")
AUTH_REFRESH_EXPIRED = ErrorCode(10006, "刷新令牌已过期")
AUTH_CAPTCHA_INVALID = ErrorCode(10007, "验证码错误或已过期")
AUTH_PHONE_INVALID = ErrorCode(10008, "手机号格式不正确")
AUTH_ROLE_NOT_ALLOWED = ErrorCode(10009, "角色不允许访问该端")
AUTH_OLD_PASSWORD_WRONG = ErrorCode(10010, "原口令不正确")


# --- 会话与分诊（20xxx） --------------------------------------------------

SESSION_NOT_FOUND = ErrorCode(20001, "会话不存在")
SESSION_ALREADY_CLOSED = ErrorCode(20002, "会话已结束")
SESSION_EXPIRED = ErrorCode(20003, "会话已过期")
SESSION_ALREADY_FINISHED = ErrorCode(20004, "会话已完成预问诊")
SESSION_TRIAGE_EXISTS = ErrorCode(20005, "该会话已存在分诊结论")
SESSION_TRIAGE_NOT_READY = ErrorCode(20006, "分诊结论尚未生成")
SESSION_ROUND_LIMIT = ErrorCode(20007, "追问轮次已达上限")
SESSION_TAKEN_BY_OTHER = ErrorCode(20008, "该会话已被其他医生接管")
SESSION_NOT_TAKEOVER = ErrorCode(20009, "会话不在待接管状态")
SESSION_CORRECTION_REASON = ErrorCode(20010, "修正理由不满足要求")
SESSION_CORRECTION_SAME = ErrorCode(20011, "修正前后科室相同")
SESSION_NO_CONSENT = ErrorCode(20012, "患者未授权调阅既往病历")
SESSION_EMERGENCY_TRIGGERED = ErrorCode(20013, "危重症已触发急诊通道")
SESSION_MESSAGE_EMPTY = ErrorCode(20014, "消息内容为空或超长")
SESSION_MESSAGE_TYPE = ErrorCode(20015, "不支持的消息类型")


# --- 挂号与号源（30xxx） --------------------------------------------------

APPT_SLOT_GONE = ErrorCode(30001, "号源不存在或已过期")
APPT_SLOT_TAKEN = ErrorCode(30002, "号源已被占用")
APPT_NO_SLOT = ErrorCode(30003, "该科室近期无号源")
APPT_DUPLICATE = ErrorCode(30004, "已存在相同预约")
APPT_NOT_FOUND = ErrorCode(30005, "预约不存在")
APPT_NOT_CANCELLABLE = ErrorCode(30006, "该预约不可取消")
APPT_QUERY_TIMEOUT = ErrorCode(30007, "号源查询服务超时")


# --- 知识库与检索（40xxx） --------------------------------------------------

KB_ENTRY_NOT_FOUND = ErrorCode(40001, "知识库条目不存在")
KB_ENTRY_CODE_EXISTS = ErrorCode(40002, "条目标识已存在")
KB_ENTRY_REF_MISSING = ErrorCode(40003, "条目标识不存在")
KB_ENTRY_REFERENCED = ErrorCode(40004, "该条目已被引用，不可停用")
KB_ENTRY_INVALID = ErrorCode(40005, "条目校验失败")
KB_INGEST_RUNNING = ErrorCode(40006, "存在未完成的入库任务")
KB_INGEST_NOT_FOUND = ErrorCode(40007, "入库任务不存在")
KB_INGEST_NOT_ABORTABLE = ErrorCode(40008, "入库任务不可中止")
KB_SEARCH_EMPTY = ErrorCode(40009, "检索查询为空")
KB_GOLDEN_NOT_FOUND = ErrorCode(40010, "黄金查询用例不存在")
KB_GOLDEN_NONE = ErrorCode(40011, "无启用中的黄金查询用例")
KB_SEARCH_TIMEOUT = ErrorCode(40012, "知识库检索超时")
KB_PUBLISH_SNAPSHOT = ErrorCode(40013, "发布快照生成失败")
KB_VERSION_EXISTS = ErrorCode(40014, "版本标识已存在")


# --- 机构与配置（50xxx） --------------------------------------------------

DEPT_NOT_FOUND = ErrorCode(50001, "科室不存在")
DEPT_CODE_EXISTS = ErrorCode(50002, "科室编码已存在")
DEPT_REFERENCED = ErrorCode(50003, "该科室已被引用，不可停用")
USER_NOT_FOUND = ErrorCode(50004, "用户不存在")
USER_ACCOUNT_EXISTS = ErrorCode(50005, "登录账号已存在")
USER_HAS_ACTIVE_SESSION = ErrorCode(50006, "该医生存在未完成接诊")
CONFIG_NOT_FOUND = ErrorCode(50007, "配置项不存在")
CONFIG_VALUE_INVALID = ErrorCode(50008, "配置项取值非法")
MODEL_PROVIDER_NOT_FOUND = ErrorCode(50009, "模型配置不存在")
MODEL_DEFAULT_EXISTS = ErrorCode(50010, "该类型已有默认配置")
TENANT_NOT_FOUND = ErrorCode(50011, "机构信息不存在")


# --- 外部依赖与系统（60xxx） ------------------------------------------------

EMR_UNAVAILABLE = ErrorCode(60001, "病历系统不可用")
EMR_FETCH_FAILED = ErrorCode(60002, "病历调阅失败")
ASR_UNAVAILABLE = ErrorCode(60003, "语音识别服务不可用")
LLM_UNAVAILABLE = ErrorCode(60004, "内容生成服务不可用")
EMBEDDING_UNAVAILABLE = ErrorCode(60005, "向量化服务不可用")
RERANK_UNAVAILABLE = ErrorCode(60006, "精排服务不可用")
EGRESS_BLOCKED = ErrorCode(60007, "数据出域被拦截")
AUDIT_WRITE_FAILED = ErrorCode(60008, "审计写入失败")
FILE_TYPE_UNSUPPORTED = ErrorCode(60009, "文件格式不支持")
FILE_SIZE_EXCEEDED = ErrorCode(60010, "文件大小超限")
SYSTEM_DEGRADED = ErrorCode(60011, "系统处于降级状态")


# --- 汇总与查询 ------------------------------------------------------------

ALL_CODES: dict[int, ErrorCode] = {
    c.code: c
    for c in list(globals().values())
    if isinstance(c, ErrorCode)
}


def get_error(code: int) -> ErrorCode:
    """按 code 查错误码定义；未命中返回 500。"""
    return ALL_CODES.get(code, INTERNAL_ERROR)


__all__ = [
    "ALL_CODES",
    "APPT_DUPLICATE",
    "APPT_NOT_CANCELLABLE",
    "APPT_NOT_FOUND",
    "APPT_NO_SLOT",
    "APPT_QUERY_TIMEOUT",
    "APPT_SLOT_GONE",
    "APPT_SLOT_TAKEN",
    "ASR_UNAVAILABLE",
    "AUDIT_WRITE_FAILED",
    "AUTH_ACCOUNT_DISABLED",
    "AUTH_ACCOUNT_LOCKED",
    "AUTH_CAPTCHA_INVALID",
    "AUTH_CREDENTIAL_INVALID",
    "AUTH_OLD_PASSWORD_WRONG",
    "AUTH_PHONE_INVALID",
    "AUTH_REFRESH_EXPIRED",
    "AUTH_ROLE_NOT_ALLOWED",
    "AUTH_TOKEN_EXPIRED",
    "AUTH_TOKEN_INVALID",
    "BAD_REQUEST",
    "CONFIG_NOT_FOUND",
    "CONFIG_VALUE_INVALID",
    "CONFLICT",
    "DEPT_CODE_EXISTS",
    "DEPT_NOT_FOUND",
    "DEPT_REFERENCED",
    "EGRESS_BLOCKED",
    "EMBEDDING_UNAVAILABLE",
    "EMR_FETCH_FAILED",
    "EMR_UNAVAILABLE",
    "FILE_SIZE_EXCEEDED",
    "FILE_TYPE_UNSUPPORTED",
    "FORBIDDEN",
    "GONE",
    "INTERNAL_ERROR",
    "KB_ENTRY_CODE_EXISTS",
    "KB_ENTRY_INVALID",
    "KB_ENTRY_NOT_FOUND",
    "KB_ENTRY_REFERENCED",
    "KB_ENTRY_REF_MISSING",
    "KB_GOLDEN_NONE",
    "KB_GOLDEN_NOT_FOUND",
    "KB_INGEST_NOT_ABORTABLE",
    "KB_INGEST_NOT_FOUND",
    "KB_INGEST_RUNNING",
    "KB_PUBLISH_SNAPSHOT",
    "KB_SEARCH_EMPTY",
    "KB_SEARCH_TIMEOUT",
    "KB_VERSION_EXISTS",
    "LLM_UNAVAILABLE",
    "MODEL_DEFAULT_EXISTS",
    "MODEL_PROVIDER_NOT_FOUND",
    "NOT_FOUND",
    "OK",
    "RERANK_UNAVAILABLE",
    "SERVICE_UNAVAILABLE",
    "SESSION_ALREADY_CLOSED",
    "SESSION_ALREADY_FINISHED",
    "SESSION_CORRECTION_REASON",
    "SESSION_CORRECTION_SAME",
    "SESSION_EMERGENCY_TRIGGERED",
    "SESSION_EXPIRED",
    "SESSION_MESSAGE_EMPTY",
    "SESSION_MESSAGE_TYPE",
    "SESSION_NOT_FOUND",
    "SESSION_NOT_TAKEOVER",
    "SESSION_NO_CONSENT",
    "SESSION_ROUND_LIMIT",
    "SESSION_TAKEN_BY_OTHER",
    "SESSION_TRIAGE_EXISTS",
    "SESSION_TRIAGE_NOT_READY",
    "SYSTEM_DEGRADED",
    "TENANT_NOT_FOUND",
    "TOO_MANY_REQUESTS",
    "UNAUTHORIZED",
    "UNPROCESSABLE",
    "UPSTREAM_FAILED",
    "UPSTREAM_TIMEOUT",
    "USER_ACCOUNT_EXISTS",
    "USER_HAS_ACTIVE_SESSION",
    "USER_NOT_FOUND",
    "ErrorCode",
    "get_error",
]
