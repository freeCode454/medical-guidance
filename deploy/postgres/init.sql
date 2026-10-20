-- =============================================================================
-- MedicalGuidance 医疗智能导诊分诊与多学科会诊多智能体系统
-- 数据库初始化脚本（PostgreSQL）
-- 版本：v1.0    编制日期：2026-10-15
-- 说明：可重复执行。不使用触发器，不使用物理外键。
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS vector;

-- =============================================================================
-- 表：mg_tenant  租户（机构）
-- 说明：数据隔离边界。本表不含 tenant_id，是唯一例外。
-- =============================================================================
CREATE TABLE IF NOT EXISTS mg_tenant (
    id              varchar(32)  NOT NULL DEFAULT replace(gen_random_uuid()::text, '-', ''),
    tenant_code     varchar(64)  NOT NULL,
    tenant_name     varchar(128) NOT NULL,
    hospital_level  varchar(32),
    contact_person  varchar(64),
    contact_phone   varchar(32),
    status          char(1)      NOT NULL DEFAULT '1',
    expire_time     timestamptz,
    create_by       varchar(32),
    create_time     timestamptz  NOT NULL DEFAULT now(),
    update_by       varchar(32),
    update_time     timestamptz,
    del_flag        char(1)      NOT NULL DEFAULT '0',
    remark          varchar(500),
    CONSTRAINT pk_mg_tenant PRIMARY KEY (id)
);
COMMENT ON TABLE  mg_tenant                 IS '租户（机构）：系统数据隔离的边界';
COMMENT ON COLUMN mg_tenant.id              IS '主键，32 位无连字符字符串';
COMMENT ON COLUMN mg_tenant.tenant_code     IS '租户编码，全局唯一';
COMMENT ON COLUMN mg_tenant.tenant_name     IS '租户名称（医院名称）';
COMMENT ON COLUMN mg_tenant.hospital_level  IS '医院等级，如“三级甲等”';
COMMENT ON COLUMN mg_tenant.contact_person  IS '联系人';
COMMENT ON COLUMN mg_tenant.contact_phone   IS '联系电话';
COMMENT ON COLUMN mg_tenant.status          IS '状态：1 启用 / 0 停用';
COMMENT ON COLUMN mg_tenant.expire_time     IS '到期时间';
COMMENT ON COLUMN mg_tenant.create_by       IS '创建人标识';
COMMENT ON COLUMN mg_tenant.create_time     IS '创建时间';
COMMENT ON COLUMN mg_tenant.update_by       IS '最后更新人标识';
COMMENT ON COLUMN mg_tenant.update_time     IS '最后更新时间，由应用层维护';
COMMENT ON COLUMN mg_tenant.del_flag        IS '软删除标记：0 正常 / 1 已删除';
COMMENT ON COLUMN mg_tenant.remark          IS '备注';

CREATE UNIQUE INDEX IF NOT EXISTS uk_mg_tenant_code   ON mg_tenant (tenant_code);
CREATE INDEX IF NOT EXISTS idx_mg_tenant_status       ON mg_tenant (status) WHERE del_flag = '0';
COMMENT ON INDEX uk_mg_tenant_code IS '租户编码全局唯一';
COMMENT ON INDEX idx_mg_tenant_status IS '部分索引：仅索引未删除租户，用于查询启用中的租户';

-- =============================================================================
-- 表：mg_dept  科室
-- 说明：分诊结果的目标，也是知识库条目的归属维度。
-- =============================================================================
CREATE TABLE IF NOT EXISTS mg_dept (
    id                  varchar(32)  NOT NULL DEFAULT replace(gen_random_uuid()::text, '-', ''),
    tenant_id           varchar(32)  NOT NULL,
    dept_code           varchar(32)  NOT NULL,
    dept_name           varchar(128) NOT NULL,
    sub_specialty       varchar(32)[],
    common_complaints   varchar(64)[],
    parent_code         varchar(32),
    sort_no             integer      NOT NULL DEFAULT 0,
    status              char(1)      NOT NULL DEFAULT '1',
    create_by           varchar(32),
    create_time         timestamptz  NOT NULL DEFAULT now(),
    update_by           varchar(32),
    update_time         timestamptz,
    del_flag            char(1)      NOT NULL DEFAULT '0',
    remark              varchar(500),
    CONSTRAINT pk_mg_dept PRIMARY KEY (id)
);
COMMENT ON TABLE  mg_dept                     IS '科室：分诊目标与知识库归属维度';
COMMENT ON COLUMN mg_dept.id                  IS '主键';
COMMENT ON COLUMN mg_dept.tenant_id           IS '租户标识，所有复合索引首列';
COMMENT ON COLUMN mg_dept.dept_code           IS '科室编码，租户内唯一';
COMMENT ON COLUMN mg_dept.dept_name           IS '科室名称';
COMMENT ON COLUMN mg_dept.sub_specialty       IS '亚专科列表';
COMMENT ON COLUMN mg_dept.common_complaints   IS '常见主诉列表，供检索与引导使用';
COMMENT ON COLUMN mg_dept.parent_code         IS '上级科室编码，空表示一级科室';
COMMENT ON COLUMN mg_dept.sort_no             IS '排序号';
COMMENT ON COLUMN mg_dept.status              IS '状态：1 启用 / 0 停用';
COMMENT ON COLUMN mg_dept.create_by           IS '创建人标识';
COMMENT ON COLUMN mg_dept.create_time         IS '创建时间';
COMMENT ON COLUMN mg_dept.update_by           IS '最后更新人标识';
COMMENT ON COLUMN mg_dept.update_time         IS '最后更新时间，由应用层维护';
COMMENT ON COLUMN mg_dept.del_flag            IS '软删除标记：0 正常 / 1 已删除（科室停用即置 1）';
COMMENT ON COLUMN mg_dept.remark              IS '备注';

CREATE UNIQUE INDEX IF NOT EXISTS uk_mg_dept_tenant_code ON mg_dept (tenant_id, dept_code);
CREATE INDEX IF NOT EXISTS idx_mg_dept_tenant_status     ON mg_dept (tenant_id, status) WHERE del_flag = '0';
COMMENT ON INDEX uk_mg_dept_tenant_code IS '租户内科室编码唯一';
COMMENT ON INDEX idx_mg_dept_tenant_status IS '部分索引：按租户查询启用中的科室';

-- =============================================================================
-- 表：mg_sys_config  系统配置
-- 说明：承载租户级可调参数，含分诊阈值、检索模式、保留期等。
-- =============================================================================
CREATE TABLE IF NOT EXISTS mg_sys_config (
    id              varchar(32)  NOT NULL DEFAULT replace(gen_random_uuid()::text, '-', ''),
    tenant_id       varchar(32)  NOT NULL,
    config_key      varchar(128) NOT NULL,
    config_value    text,
    config_type     varchar(32)  NOT NULL DEFAULT 'string',
    is_encrypted    char(1)      NOT NULL DEFAULT '0',
    description     varchar(255),
    status          char(1)      NOT NULL DEFAULT '1',
    create_by       varchar(32),
    create_time     timestamptz  NOT NULL DEFAULT now(),
    update_by       varchar(32),
    update_time     timestamptz,
    del_flag        char(1)      NOT NULL DEFAULT '0',
    remark          varchar(500),
    CONSTRAINT pk_mg_sys_config PRIMARY KEY (id)
);
COMMENT ON TABLE  mg_sys_config                 IS '系统配置：租户级可调参数';
COMMENT ON COLUMN mg_sys_config.id              IS '主键';
COMMENT ON COLUMN mg_sys_config.tenant_id       IS '租户标识';
COMMENT ON COLUMN mg_sys_config.config_key      IS '配置键，租户内唯一';
COMMENT ON COLUMN mg_sys_config.config_value    IS '配置值';
COMMENT ON COLUMN mg_sys_config.config_type     IS '值类型：string / number / boolean / json';
COMMENT ON COLUMN mg_sys_config.is_encrypted    IS '值是否加密存储：1 是 / 0 否';
COMMENT ON COLUMN mg_sys_config.description     IS '配置项说明';
COMMENT ON COLUMN mg_sys_config.status          IS '状态：1 启用 / 0 停用';
COMMENT ON COLUMN mg_sys_config.create_by       IS '创建人标识';
COMMENT ON COLUMN mg_sys_config.create_time     IS '创建时间';
COMMENT ON COLUMN mg_sys_config.update_by       IS '最后更新人标识';
COMMENT ON COLUMN mg_sys_config.update_time     IS '最后更新时间，由应用层维护';
COMMENT ON COLUMN mg_sys_config.del_flag        IS '软删除标记：0 正常 / 1 已删除';
COMMENT ON COLUMN mg_sys_config.remark          IS '备注';

CREATE UNIQUE INDEX IF NOT EXISTS uk_mg_sys_config_tenant_key ON mg_sys_config (tenant_id, config_key);
COMMENT ON INDEX uk_mg_sys_config_tenant_key IS '租户内配置键唯一';

-- =============================================================================
-- 表：mg_user  用户（医生与管理员）
-- 说明：两类角色统一存储，以 role 区分。口令只存哈希。
-- =============================================================================
CREATE TABLE IF NOT EXISTS mg_user (
    id                varchar(32)  NOT NULL DEFAULT replace(gen_random_uuid()::text, '-', ''),
    tenant_id         varchar(32)  NOT NULL,
    account           varchar(64)  NOT NULL,
    real_name         varchar(64),
    role              varchar(32)  NOT NULL,
    title             varchar(32),
    dept_code         varchar(32),
    credential_hash   varchar(255) NOT NULL,
    fail_count        integer      NOT NULL DEFAULT 0,
    lock_until        timestamptz,
    last_login_time   timestamptz,
    status            char(1)      NOT NULL DEFAULT '1',
    create_by         varchar(32),
    create_time       timestamptz  NOT NULL DEFAULT now(),
    update_by         varchar(32),
    update_time       timestamptz,
    del_flag          char(1)      NOT NULL DEFAULT '0',
    remark            varchar(500),
    CONSTRAINT pk_mg_user PRIMARY KEY (id)
);
COMMENT ON TABLE  mg_user                   IS '用户：医生与管理员统一存储，以角色区分';
COMMENT ON COLUMN mg_user.id                IS '主键';
COMMENT ON COLUMN mg_user.tenant_id         IS '租户标识';
COMMENT ON COLUMN mg_user.account           IS '登录账号，租户内唯一';
COMMENT ON COLUMN mg_user.real_name         IS '真实姓名';
COMMENT ON COLUMN mg_user.role              IS '角色：DOCTOR 医生 / KB_ADMIN 知识库管理员 / ORG_ADMIN 机构管理员';
COMMENT ON COLUMN mg_user.title             IS '医师职称：住院医师/主治医师/副主任医师/主任医师，参与评测样本采纳判定';
COMMENT ON COLUMN mg_user.dept_code         IS '所属科室编码，仅医生有值';
COMMENT ON COLUMN mg_user.credential_hash   IS '口令哈希，不可逆存储';
COMMENT ON COLUMN mg_user.fail_count        IS '连续登录失败次数，用于账号锁定';
COMMENT ON COLUMN mg_user.lock_until        IS '锁定截止时间';
COMMENT ON COLUMN mg_user.last_login_time   IS '最后登录时间';
COMMENT ON COLUMN mg_user.status            IS '状态：1 启用 / 0 停用';
COMMENT ON COLUMN mg_user.create_by         IS '创建人标识';
COMMENT ON COLUMN mg_user.create_time       IS '创建时间';
COMMENT ON COLUMN mg_user.update_by         IS '最后更新人标识';
COMMENT ON COLUMN mg_user.update_time       IS '最后更新时间，由应用层维护';
COMMENT ON COLUMN mg_user.del_flag          IS '软删除标记：0 正常 / 1 已删除（账号停用即置 1）';
COMMENT ON COLUMN mg_user.remark            IS '备注';

CREATE UNIQUE INDEX IF NOT EXISTS uk_mg_user_tenant_account ON mg_user (tenant_id, account);
CREATE INDEX IF NOT EXISTS idx_mg_user_tenant_dept          ON mg_user (tenant_id, dept_code, status);
CREATE INDEX IF NOT EXISTS idx_mg_user_tenant_role          ON mg_user (tenant_id, role, status);
COMMENT ON INDEX uk_mg_user_tenant_account IS '租户内登录账号唯一';
COMMENT ON INDEX idx_mg_user_tenant_dept IS '按科室查询医生';
COMMENT ON INDEX idx_mg_user_tenant_role IS '按角色查询用户';

-- =============================================================================
-- 表：mg_patient  患者
-- 说明：不存姓名、身份证号、住址。只存哈希与分诊所需特征。
-- =============================================================================
CREATE TABLE IF NOT EXISTS mg_patient (
    id              varchar(32)  NOT NULL DEFAULT replace(gen_random_uuid()::text, '-', ''),
    tenant_id       varchar(32)  NOT NULL,
    patient_hash    varchar(64)  NOT NULL,
    patient_no      varchar(64),
    real_name       varchar(64),
    account         varchar(64),
    credential_hash varchar(255),
    fail_count      integer      NOT NULL DEFAULT 0,
    lock_until      timestamptz,
    last_login_time timestamptz,
    age             integer,
    gender          char(1),
    phone_masked    varchar(32),
    phone_hash      varchar(64),
    device_id       varchar(128),
    status          char(1)      NOT NULL DEFAULT '1',
    create_by       varchar(32),
    create_time     timestamptz  NOT NULL DEFAULT now(),
    update_by       varchar(32),
    update_time     timestamptz,
    del_flag        char(1)      NOT NULL DEFAULT '0',
    remark          varchar(500),
    CONSTRAINT pk_mg_patient PRIMARY KEY (id)
);
COMMENT ON TABLE  mg_patient                IS '患者：不含身份信息，仅存哈希与分诊特征';
COMMENT ON COLUMN mg_patient.id             IS '主键';
COMMENT ON COLUMN mg_patient.tenant_id      IS '租户标识';
COMMENT ON COLUMN mg_patient.patient_hash   IS '患者标识哈希，加盐后计算，同一患者在不同租户下哈希不同';
COMMENT ON COLUMN mg_patient.patient_no     IS '院内患者编号，用于脱敏展示';
COMMENT ON COLUMN mg_patient.real_name      IS '患者姓名，医生接诊时展示';
COMMENT ON COLUMN mg_patient.age            IS '年龄';
COMMENT ON COLUMN mg_patient.gender         IS '性别：1 男 / 2 女 / 0 未知';
COMMENT ON COLUMN mg_patient.phone_masked   IS '手机号脱敏形式，仅用于回显';
COMMENT ON COLUMN mg_patient.phone_hash     IS '手机号哈希，用于匹配，不存明文';
COMMENT ON COLUMN mg_patient.device_id      IS '设备标识，用于匿名会话关联与恢复';
COMMENT ON COLUMN mg_patient.status         IS '状态：1 正常 / 0 停用';
COMMENT ON COLUMN mg_patient.create_by      IS '创建人标识';
COMMENT ON COLUMN mg_patient.create_time    IS '创建时间';
COMMENT ON COLUMN mg_patient.update_by      IS '最后更新人标识';
COMMENT ON COLUMN mg_patient.update_time    IS '最后更新时间，由应用层维护';
COMMENT ON COLUMN mg_patient.del_flag       IS '软删除标记，本表不实际使用（患者数据按保留期归档）';
COMMENT ON COLUMN mg_patient.remark         IS '备注';

CREATE UNIQUE INDEX IF NOT EXISTS uk_mg_patient_tenant_hash  ON mg_patient (tenant_id, patient_hash);
CREATE UNIQUE INDEX IF NOT EXISTS uk_mg_patient_tenant_account ON mg_patient (tenant_id, account);
CREATE INDEX IF NOT EXISTS idx_mg_patient_tenant_phone       ON mg_patient (tenant_id, phone_hash);
CREATE INDEX IF NOT EXISTS idx_mg_patient_tenant_device      ON mg_patient (tenant_id, device_id);
COMMENT ON INDEX uk_mg_patient_tenant_hash IS '租户内患者标识哈希唯一';
COMMENT ON INDEX idx_mg_patient_tenant_phone IS '按手机号哈希查找患者';
COMMENT ON INDEX idx_mg_patient_tenant_device IS '按设备标识查找匿名会话患者';

-- =============================================================================
-- 表：mg_patient_consent  患者授权记录
-- 说明：患者对既往病历调阅的授权。无有效授权时禁止调阅。
-- =============================================================================
CREATE TABLE IF NOT EXISTS mg_patient_consent (
    id                varchar(32)  NOT NULL DEFAULT replace(gen_random_uuid()::text, '-', ''),
    tenant_id         varchar(32)  NOT NULL,
    patient_id        varchar(32)  NOT NULL,
    session_id        varchar(32),
    consent_scope     varchar(255) NOT NULL,
    consent_time      timestamptz  NOT NULL DEFAULT now(),
    expire_time       timestamptz,
    consent_channel   varchar(32),
    revoke_time       timestamptz,
    create_by         varchar(32),
    create_time       timestamptz  NOT NULL DEFAULT now(),
    update_by         varchar(32),
    update_time       timestamptz,
    del_flag          char(1)      NOT NULL DEFAULT '0',
    remark            varchar(500),
    CONSTRAINT pk_mg_patient_consent PRIMARY KEY (id)
);
COMMENT ON TABLE  mg_patient_consent                 IS '患者授权记录：既往病历调阅授权';
COMMENT ON COLUMN mg_patient_consent.id              IS '主键';
COMMENT ON COLUMN mg_patient_consent.tenant_id       IS '租户标识';
COMMENT ON COLUMN mg_patient_consent.patient_id      IS '患者标识，逻辑关联 mg_patient';
COMMENT ON COLUMN mg_patient_consent.session_id      IS '触发授权的会话标识，逻辑关联 mg_session';
COMMENT ON COLUMN mg_patient_consent.consent_scope   IS '授权范围说明，如“调阅近两年门诊与住院记录”';
COMMENT ON COLUMN mg_patient_consent.consent_time    IS '授权时间';
COMMENT ON COLUMN mg_patient_consent.expire_time     IS '失效时间，空表示长期有效';
COMMENT ON COLUMN mg_patient_consent.consent_channel IS '授权渠道：患者端 / 线下';
COMMENT ON COLUMN mg_patient_consent.revoke_time     IS '撤回时间，空表示未撤回';
COMMENT ON COLUMN mg_patient_consent.create_by       IS '创建人标识';
COMMENT ON COLUMN mg_patient_consent.create_time     IS '创建时间';
COMMENT ON COLUMN mg_patient_consent.update_by       IS '最后更新人标识';
COMMENT ON COLUMN mg_patient_consent.update_time     IS '最后更新时间，由应用层维护';
COMMENT ON COLUMN mg_patient_consent.del_flag        IS '软删除标记，本表不实际使用（授权记录需长期保留）';
COMMENT ON COLUMN mg_patient_consent.remark          IS '备注';

CREATE INDEX IF NOT EXISTS idx_mg_consent_tenant_patient ON mg_patient_consent (tenant_id, patient_id, consent_time DESC);
CREATE INDEX IF NOT EXISTS idx_mg_consent_tenant_session ON mg_patient_consent (tenant_id, session_id);
COMMENT ON INDEX idx_mg_consent_tenant_patient IS '查询患者最新授权记录';
COMMENT ON INDEX idx_mg_consent_tenant_session IS '按会话查询授权';

-- =============================================================================
-- 表：mg_session  预问诊会话
-- 说明：核心业务表。id 直接作为编排层会话标识，与检查点线程标识一致。
-- =============================================================================
CREATE TABLE IF NOT EXISTS mg_session (
    id                 varchar(32)  NOT NULL DEFAULT replace(gen_random_uuid()::text, '-', ''),
    tenant_id          varchar(32)  NOT NULL,
    session_no         varchar(64)  NOT NULL,
    patient_id         varchar(32)  NOT NULL,
    doctor_id          varchar(32),
    dept_code          varchar(32),
    chief_complaint    text,
    status             varchar(32)  NOT NULL DEFAULT 'IN_PROGRESS',
    risk_flag          char(1)      NOT NULL DEFAULT '0',
    inquiry_rounds     integer      NOT NULL DEFAULT 0,
    sufficiency_score  numeric(5,4),
    device_id          varchar(128),
    started_time       timestamptz  NOT NULL DEFAULT now(),
    finished_time      timestamptz,
    expire_time        timestamptz,
    create_by          varchar(32),
    create_time        timestamptz  NOT NULL DEFAULT now(),
    update_by          varchar(32),
    update_time        timestamptz,
    del_flag           char(1)      NOT NULL DEFAULT '0',
    remark             varchar(500),
    CONSTRAINT pk_mg_session PRIMARY KEY (id)
);
COMMENT ON TABLE  mg_session                   IS '预问诊会话：一次预问诊的全过程，核心业务表';
COMMENT ON COLUMN mg_session.id                IS '主键，同时作为编排层会话标识与检查点线程标识';
COMMENT ON COLUMN mg_session.tenant_id         IS '租户标识';
COMMENT ON COLUMN mg_session.session_no        IS '会话业务编号，租户内唯一';
COMMENT ON COLUMN mg_session.patient_id        IS '患者标识，逻辑关联 mg_patient';
COMMENT ON COLUMN mg_session.doctor_id         IS '接诊医生标识，逻辑关联 mg_user，未分配时为空';
COMMENT ON COLUMN mg_session.dept_code         IS '最终建议科室编码';
COMMENT ON COLUMN mg_session.chief_complaint   IS '主诉原文';
COMMENT ON COLUMN mg_session.status            IS '状态：IN_PROGRESS 进行中 / FINISHED 已出结论 / PENDING_TAKEOVER 待接管 / TAKEN_OVER 已接管 / CLOSED 已结束 / EMERGENCY 已触发急诊';
COMMENT ON COLUMN mg_session.risk_flag         IS '风险标记：1 高风险（危重症命中）/ 0 正常';
COMMENT ON COLUMN mg_session.inquiry_rounds    IS '已追问轮次，上限见系统配置';
COMMENT ON COLUMN mg_session.sufficiency_score IS '最后一次信息充分度评分';
COMMENT ON COLUMN mg_session.device_id         IS '设备标识，用于匿名会话恢复';
COMMENT ON COLUMN mg_session.started_time      IS '会话开始时间';
COMMENT ON COLUMN mg_session.finished_time     IS '会话结束时间';
COMMENT ON COLUMN mg_session.expire_time       IS '会话有效期，默认开始时间加 24 小时，用于断点恢复判断';
COMMENT ON COLUMN mg_session.create_by         IS '创建人标识';
COMMENT ON COLUMN mg_session.create_time       IS '创建时间';
COMMENT ON COLUMN mg_session.update_by         IS '最后更新人标识';
COMMENT ON COLUMN mg_session.update_time       IS '最后更新时间，由应用层维护';
COMMENT ON COLUMN mg_session.del_flag          IS '软删除标记，本表不实际使用（会话按保留期归档）';
COMMENT ON COLUMN mg_session.remark            IS '备注';

CREATE UNIQUE INDEX IF NOT EXISTS uk_mg_session_tenant_no       ON mg_session (tenant_id, session_no);
CREATE INDEX IF NOT EXISTS idx_mg_session_tenant_patient        ON mg_session (tenant_id, patient_id, started_time DESC);
CREATE INDEX IF NOT EXISTS idx_mg_session_tenant_doctor         ON mg_session (tenant_id, doctor_id, status);
CREATE INDEX IF NOT EXISTS idx_mg_session_tenant_takeover       ON mg_session (tenant_id, started_time) WHERE status = 'PENDING_TAKEOVER';
CREATE INDEX IF NOT EXISTS idx_mg_session_tenant_device         ON mg_session (tenant_id, device_id, status);
COMMENT ON INDEX uk_mg_session_tenant_no IS '租户内会话编号唯一';
COMMENT ON INDEX idx_mg_session_tenant_patient IS '查询患者历史会话';
COMMENT ON INDEX idx_mg_session_tenant_doctor IS '医生端接诊列表按状态筛选';
COMMENT ON INDEX idx_mg_session_tenant_takeover IS '部分索引：待接管队列按等待时长排序，索引体积极小';
COMMENT ON INDEX idx_mg_session_tenant_device IS '匿名会话恢复按设备查询';

-- =============================================================================
-- 表：mg_session_message  会话消息
-- 说明：全库行数最多的表。seq_no 保证顺序确定性，不依赖时间戳排序。
-- =============================================================================
CREATE TABLE IF NOT EXISTS mg_session_message (
    id           varchar(32) NOT NULL DEFAULT replace(gen_random_uuid()::text, '-', ''),
    tenant_id    varchar(32) NOT NULL,
    session_id   varchar(32) NOT NULL,
    seq_no       integer     NOT NULL,
    role         varchar(16) NOT NULL,
    content      text        NOT NULL,
    msg_type     varchar(32) NOT NULL DEFAULT 'TEXT',
    extra_json   jsonb,
    send_time    timestamptz NOT NULL DEFAULT now(),
    create_by    varchar(32),
    create_time  timestamptz NOT NULL DEFAULT now(),
    update_by    varchar(32),
    update_time  timestamptz,
    del_flag     char(1)     NOT NULL DEFAULT '0',
    remark       varchar(500),
    CONSTRAINT pk_mg_session_message PRIMARY KEY (id)
);
COMMENT ON TABLE  mg_session_message            IS '会话消息：对话逐条记录，全库行数最多的表';
COMMENT ON COLUMN mg_session_message.id         IS '主键';
COMMENT ON COLUMN mg_session_message.tenant_id  IS '租户标识';
COMMENT ON COLUMN mg_session_message.session_id IS '会话标识，逻辑关联 mg_session';
COMMENT ON COLUMN mg_session_message.seq_no     IS '会话内序号，从 1 递增，保证消息顺序确定性';
COMMENT ON COLUMN mg_session_message.role       IS '消息角色：PATIENT 患者 / AI 智能体 / DOCTOR 医生 / SYSTEM 系统';
COMMENT ON COLUMN mg_session_message.content    IS '消息内容';
COMMENT ON COLUMN mg_session_message.msg_type   IS '消息类型：TEXT 文字 / VOICE 语音 / BODY_MAP 部位点选 / RESULT 结果 / EMERGENCY 急诊告警';
COMMENT ON COLUMN mg_session_message.extra_json IS '附加信息，如部位点选的部位列表、语音转写原文';
COMMENT ON COLUMN mg_session_message.send_time  IS '发送时间';
COMMENT ON COLUMN mg_session_message.create_by  IS '创建人标识';
COMMENT ON COLUMN mg_session_message.create_time IS '创建时间';
COMMENT ON COLUMN mg_session_message.update_by  IS '最后更新人标识';
COMMENT ON COLUMN mg_session_message.update_time IS '最后更新时间，由应用层维护';
COMMENT ON COLUMN mg_session_message.del_flag   IS '软删除标记，本表不实际使用';
COMMENT ON COLUMN mg_session_message.remark     IS '备注';

CREATE UNIQUE INDEX IF NOT EXISTS uk_mg_msg_tenant_session_seq ON mg_session_message (tenant_id, session_id, seq_no);
CREATE INDEX IF NOT EXISTS idx_mg_msg_tenant_session_time      ON mg_session_message (tenant_id, session_id, send_time);
COMMENT ON INDEX uk_mg_msg_tenant_session_seq IS '会话内序号唯一，保证消息不重复与顺序确定';
COMMENT ON INDEX idx_mg_msg_tenant_session_time IS '按时间分页读取会话消息';

-- =============================================================================
-- 表：mg_triage_result  分诊结论
-- 说明：候选科室与判断依据用 JSONB 存储（快照式附属数据）。
-- =============================================================================
CREATE TABLE IF NOT EXISTS mg_triage_result (
    id                 varchar(32)  NOT NULL DEFAULT replace(gen_random_uuid()::text, '-', ''),
    tenant_id          varchar(32)  NOT NULL,
    session_id         varchar(32)  NOT NULL,
    candidates_json    jsonb        NOT NULL,
    confidence         numeric(5,4),
    route              varchar(32)  NOT NULL,
    retrieval_mode     varchar(16),
    evidence_json      jsonb,
    kb_version         varchar(64),
    doctor_confirmed   char(1)      NOT NULL DEFAULT '0',
    confirmed_time     timestamptz,
    create_by          varchar(32),
    create_time        timestamptz  NOT NULL DEFAULT now(),
    update_by          varchar(32),
    update_time        timestamptz,
    del_flag           char(1)      NOT NULL DEFAULT '0',
    remark             varchar(500),
    CONSTRAINT pk_mg_triage_result PRIMARY KEY (id)
);
COMMENT ON TABLE  mg_triage_result                  IS '分诊结论：会话产出的科室建议与路由结果';
COMMENT ON COLUMN mg_triage_result.id               IS '主键';
COMMENT ON COLUMN mg_triage_result.tenant_id        IS '租户标识';
COMMENT ON COLUMN mg_triage_result.session_id       IS '会话标识，逻辑关联 mg_session';
COMMENT ON COLUMN mg_triage_result.candidates_json  IS '候选科室列表（JSONB）：科室编码、名称、置信度、命中依据';
COMMENT ON COLUMN mg_triage_result.confidence       IS '整体置信度';
COMMENT ON COLUMN mg_triage_result.route            IS '路由去向：DIRECT 直接推荐 / MDT 多科会诊 / MANUAL 转人工 / EMERGENCY 急诊';
COMMENT ON COLUMN mg_triage_result.retrieval_mode   IS '本次采用的检索模式：DENSE 仅语义 / SPARSE 仅词元 / HYBRID 融合';
COMMENT ON COLUMN mg_triage_result.evidence_json    IS '判断依据（JSONB）：命中的症状、引用的指南条目标识';
COMMENT ON COLUMN mg_triage_result.kb_version       IS '本次决策依据的知识库版本，用于事后复盘';
COMMENT ON COLUMN mg_triage_result.doctor_confirmed IS '医生是否已确认：1 是 / 0 否';
COMMENT ON COLUMN mg_triage_result.confirmed_time   IS '医生确认时间';
COMMENT ON COLUMN mg_triage_result.create_by        IS '创建人标识';
COMMENT ON COLUMN mg_triage_result.create_time      IS '创建时间';
COMMENT ON COLUMN mg_triage_result.update_by        IS '最后更新人标识';
COMMENT ON COLUMN mg_triage_result.update_time      IS '最后更新时间，由应用层维护';
COMMENT ON COLUMN mg_triage_result.del_flag         IS '软删除标记，本表不实际使用';
COMMENT ON COLUMN mg_triage_result.remark           IS '备注';

CREATE UNIQUE INDEX IF NOT EXISTS uk_mg_triage_session             ON mg_triage_result (session_id);
CREATE INDEX IF NOT EXISTS idx_mg_triage_tenant_route              ON mg_triage_result (tenant_id, route, create_time DESC);
CREATE INDEX IF NOT EXISTS idx_mg_triage_tenant_confirm            ON mg_triage_result (tenant_id, doctor_confirmed);
CREATE INDEX IF NOT EXISTS idx_mg_triage_candidates_gin            ON mg_triage_result USING gin (candidates_json jsonb_path_ops);
COMMENT ON INDEX uk_mg_triage_session IS '一次会话仅一份分诊结论';
COMMENT ON INDEX idx_mg_triage_tenant_route IS '按路由去向统计（会诊比例、转人工比例）';
COMMENT ON INDEX idx_mg_triage_tenant_confirm IS '查询医生未确认的结论';
COMMENT ON INDEX idx_mg_triage_candidates_gin IS 'GIN 索引：按候选科室 JSONB 内部字段检索';

-- =============================================================================
-- 表：mg_triage_correction  分诊修正记录
-- 说明：评测样本的唯一来源。职称采用快照存储。
-- =============================================================================
CREATE TABLE IF NOT EXISTS mg_triage_correction (
    id               varchar(32)  NOT NULL DEFAULT replace(gen_random_uuid()::text, '-', ''),
    tenant_id        varchar(32)  NOT NULL,
    triage_id        varchar(32)  NOT NULL,
    session_id       varchar(32)  NOT NULL,
    before_dept      varchar(32)  NOT NULL,
    after_dept       varchar(32)  NOT NULL,
    reason           varchar(500) NOT NULL,
    doctor_id        varchar(32)  NOT NULL,
    doctor_title     varchar(32)  NOT NULL,
    usable_for_eval  char(1)      NOT NULL DEFAULT '0',
    create_by        varchar(32),
    create_time      timestamptz  NOT NULL DEFAULT now(),
    update_by        varchar(32),
    update_time      timestamptz,
    del_flag         char(1)      NOT NULL DEFAULT '0',
    remark           varchar(500),
    CONSTRAINT pk_mg_triage_correction PRIMARY KEY (id)
);
COMMENT ON TABLE  mg_triage_correction                  IS '分诊修正记录：医生修正留痕，评测样本来源';
COMMENT ON COLUMN mg_triage_correction.id               IS '主键';
COMMENT ON COLUMN mg_triage_correction.tenant_id        IS '租户标识';
COMMENT ON COLUMN mg_triage_correction.triage_id        IS '分诊结论标识，逻辑关联 mg_triage_result';
COMMENT ON COLUMN mg_triage_correction.session_id       IS '会话标识，冗余存储便于按会话直接查询';
COMMENT ON COLUMN mg_triage_correction.before_dept      IS '修正前科室编码';
COMMENT ON COLUMN mg_triage_correction.after_dept       IS '修正后科室编码';
COMMENT ON COLUMN mg_triage_correction.reason           IS '修正理由，不少于 10 字';
COMMENT ON COLUMN mg_triage_correction.doctor_id        IS '修正人标识，逻辑关联 mg_user';
COMMENT ON COLUMN mg_triage_correction.doctor_title     IS '修正人职称快照，用于评测样本采纳判定';
COMMENT ON COLUMN mg_triage_correction.usable_for_eval  IS '是否可用于评测：1 是（副主任医师及以上）/ 0 否';
COMMENT ON COLUMN mg_triage_correction.create_by        IS '创建人标识';
COMMENT ON COLUMN mg_triage_correction.create_time      IS '创建时间';
COMMENT ON COLUMN mg_triage_correction.update_by        IS '最后更新人标识';
COMMENT ON COLUMN mg_triage_correction.update_time      IS '最后更新时间，由应用层维护';
COMMENT ON COLUMN mg_triage_correction.del_flag         IS '软删除标记，本表不实际使用';
COMMENT ON COLUMN mg_triage_correction.remark           IS '备注';

CREATE INDEX IF NOT EXISTS idx_mg_corr_tenant_triage ON mg_triage_correction (tenant_id, triage_id);
CREATE INDEX IF NOT EXISTS idx_mg_corr_tenant_eval   ON mg_triage_correction (tenant_id, create_time DESC) WHERE usable_for_eval = '1';
COMMENT ON INDEX idx_mg_corr_tenant_triage IS '按结论查询修正历史';
COMMENT ON INDEX idx_mg_corr_tenant_eval IS '部分索引：提取可用于评测的修正样本';

-- =============================================================================
-- 表：mg_mdt_council  多学科会诊记录
-- 说明：各专科意见用 JSONB；分歧必须显式存储，不得被抹平。
-- =============================================================================
CREATE TABLE IF NOT EXISTS mg_mdt_council (
    id                    varchar(32)  NOT NULL DEFAULT replace(gen_random_uuid()::text, '-', ''),
    tenant_id             varchar(32)  NOT NULL,
    session_id            varchar(32)  NOT NULL,
    trigger_reason        varchar(255) NOT NULL,
    candidate_depts       varchar(32)[] NOT NULL,
    opinions_json         jsonb        NOT NULL,
    consensus_dept        varchar(32),
    consensus_confidence  numeric(5,4),
    divergence_flag       char(1)      NOT NULL DEFAULT '0',
    divergence_json       jsonb,
    missing_count         integer      NOT NULL DEFAULT 0,
    duration_ms           integer,
    create_by             varchar(32),
    create_time           timestamptz  NOT NULL DEFAULT now(),
    update_by             varchar(32),
    update_time           timestamptz,
    del_flag              char(1)      NOT NULL DEFAULT '0',
    remark                varchar(500),
    CONSTRAINT pk_mg_mdt_council PRIMARY KEY (id)
);
COMMENT ON TABLE  mg_mdt_council                       IS '多学科会诊记录：多个专科角色并行判断与汇总结果';
COMMENT ON COLUMN mg_mdt_council.id                    IS '主键';
COMMENT ON COLUMN mg_mdt_council.tenant_id             IS '租户标识';
COMMENT ON COLUMN mg_mdt_council.session_id            IS '会话标识，逻辑关联 mg_session';
COMMENT ON COLUMN mg_mdt_council.trigger_reason        IS '触发原因，如“候选科室置信度差值低于阈值”';
COMMENT ON COLUMN mg_mdt_council.candidate_depts       IS '参与会诊的候选科室编码列表';
COMMENT ON COLUMN mg_mdt_council.opinions_json         IS '各专科意见（JSONB）：科室角色、倾向方向、判断依据、建议科室、置信度';
COMMENT ON COLUMN mg_mdt_council.consensus_dept        IS '综合推荐科室编码';
COMMENT ON COLUMN mg_mdt_council.consensus_confidence  IS '综合置信度';
COMMENT ON COLUMN mg_mdt_council.divergence_flag       IS '是否存在分歧：1 是 / 0 否。分歧必须显式保留，不得在汇总时抹平';
COMMENT ON COLUMN mg_mdt_council.divergence_json       IS '分歧点明细（JSONB）：结论不一致的角色及其理由';
COMMENT ON COLUMN mg_mdt_council.missing_count         IS '未返回结论的专科角色数量，用于判断本次会诊结论的可靠性';
COMMENT ON COLUMN mg_mdt_council.duration_ms           IS '会诊总耗时（毫秒）';
COMMENT ON COLUMN mg_mdt_council.create_by             IS '创建人标识';
COMMENT ON COLUMN mg_mdt_council.create_time           IS '创建时间';
COMMENT ON COLUMN mg_mdt_council.update_by             IS '最后更新人标识';
COMMENT ON COLUMN mg_mdt_council.update_time           IS '最后更新时间，由应用层维护';
COMMENT ON COLUMN mg_mdt_council.del_flag              IS '软删除标记，本表不实际使用';
COMMENT ON COLUMN mg_mdt_council.remark                IS '备注';

CREATE INDEX IF NOT EXISTS idx_mg_mdt_tenant_session     ON mg_mdt_council (tenant_id, session_id, create_time);
CREATE INDEX IF NOT EXISTS idx_mg_mdt_tenant_divergence  ON mg_mdt_council (tenant_id, create_time DESC) WHERE divergence_flag = '1';
CREATE INDEX IF NOT EXISTS idx_mg_mdt_opinions_gin       ON mg_mdt_council USING gin (opinions_json jsonb_path_ops);
COMMENT ON INDEX idx_mg_mdt_tenant_session IS '按会话查询会诊记录';
COMMENT ON INDEX idx_mg_mdt_tenant_divergence IS '部分索引：统计存在分歧的会诊，用于优化专科角色';
COMMENT ON INDEX idx_mg_mdt_opinions_gin IS 'GIN 索引：按专科意见内部字段检索';

-- =============================================================================
-- 表：mg_emr_record  预问诊病历
-- 说明：SOAP 四段独立字段存储，便于按患者端/医生端分别控制返回。
-- =============================================================================
CREATE TABLE IF NOT EXISTS mg_emr_record (
    id                 varchar(32)  NOT NULL DEFAULT replace(gen_random_uuid()::text, '-', ''),
    tenant_id          varchar(32)  NOT NULL,
    session_id         varchar(32)  NOT NULL,
    patient_id         varchar(32)  NOT NULL,
    subjective         text,
    objective          text,
    assessment         text,
    plan               text,
    soap_json          jsonb,
    source_refs_json   jsonb,
    schema_version     varchar(16)  NOT NULL DEFAULT '1.0',
    completeness_rate  numeric(5,4),
    generate_status    varchar(16)  NOT NULL DEFAULT 'SUCCESS',
    create_by          varchar(32),
    create_time        timestamptz  NOT NULL DEFAULT now(),
    update_by          varchar(32),
    update_time        timestamptz,
    del_flag           char(1)      NOT NULL DEFAULT '0',
    remark             varchar(500),
    CONSTRAINT pk_mg_emr_record PRIMARY KEY (id)
);
COMMENT ON TABLE  mg_emr_record                    IS '预问诊病历：SOAP 结构化病历';
COMMENT ON COLUMN mg_emr_record.id                 IS '主键';
COMMENT ON COLUMN mg_emr_record.tenant_id          IS '租户标识';
COMMENT ON COLUMN mg_emr_record.session_id         IS '会话标识，逻辑关联 mg_session';
COMMENT ON COLUMN mg_emr_record.patient_id         IS '患者标识，逻辑关联 mg_patient';
COMMENT ON COLUMN mg_emr_record.subjective         IS 'S 段：主观资料（主诉、现病史、既往史）';
COMMENT ON COLUMN mg_emr_record.objective          IS 'O 段：客观资料（已采集的体征与检查结果）';
COMMENT ON COLUMN mg_emr_record.assessment         IS 'A 段：评估（鉴别方向），仅医生端可见，患者端须剔除疾病名称';
COMMENT ON COLUMN mg_emr_record.plan               IS 'P 段：计划（建议就诊科室、建议补充检查），不得含用药建议';
COMMENT ON COLUMN mg_emr_record.soap_json          IS 'SOAP 四段的结构化版本（JSONB），含各段来源标注';
COMMENT ON COLUMN mg_emr_record.source_refs_json   IS '各段内容的来源引用，标注来自既往病历的条目与时点';
COMMENT ON COLUMN mg_emr_record.schema_version     IS '病历结构版本';
COMMENT ON COLUMN mg_emr_record.completeness_rate  IS '字段完整率，用于非功能需求校验';
COMMENT ON COLUMN mg_emr_record.generate_status    IS '生成状态：SUCCESS 成功 / PARTIAL 部分缺失 / FAILED 失败';
COMMENT ON COLUMN mg_emr_record.create_by          IS '创建人标识';
COMMENT ON COLUMN mg_emr_record.create_time        IS '创建时间';
COMMENT ON COLUMN mg_emr_record.update_by          IS '最后更新人标识';
COMMENT ON COLUMN mg_emr_record.update_time        IS '最后更新时间，由应用层维护';
COMMENT ON COLUMN mg_emr_record.del_flag           IS '软删除标记，本表不实际使用';
COMMENT ON COLUMN mg_emr_record.remark             IS '备注';

CREATE UNIQUE INDEX IF NOT EXISTS uk_mg_emr_record_session           ON mg_emr_record (session_id);
CREATE INDEX IF NOT EXISTS idx_mg_emr_record_tenant_patient          ON mg_emr_record (tenant_id, patient_id, create_time DESC);
CREATE INDEX IF NOT EXISTS idx_mg_emr_record_tenant_status           ON mg_emr_record (tenant_id, generate_status);
COMMENT ON INDEX uk_mg_emr_record_session IS '一次会话仅一份预问诊病历';
COMMENT ON INDEX idx_mg_emr_record_tenant_patient IS '查询患者历史病历';
COMMENT ON INDEX idx_mg_emr_record_tenant_status IS '查询生成失败或部分缺失的病历';

-- =============================================================================
-- 表：mg_emr_document  既往病历文书
-- 说明：section_json 按语义小节切分，是分块检索的前提；record_time 支撑时间衰减。
-- =============================================================================
CREATE TABLE IF NOT EXISTS mg_emr_document (
    id            varchar(32)  NOT NULL DEFAULT replace(gen_random_uuid()::text, '-', ''),
    tenant_id     varchar(32)  NOT NULL,
    patient_id    varchar(32)  NOT NULL,
    doc_type      varchar(32)  NOT NULL,
    doc_title     varchar(255),
    dept_code     varchar(32),
    record_time   timestamptz  NOT NULL,
    doc_content   text         NOT NULL,
    section_json  jsonb,
    icd10_codes   varchar(16)[],
    source_system varchar(64),
    doc_no        varchar(64),
    create_by     varchar(32),
    create_time   timestamptz  NOT NULL DEFAULT now(),
    update_by     varchar(32),
    update_time   timestamptz,
    del_flag      char(1)      NOT NULL DEFAULT '0',
    remark        varchar(500),
    CONSTRAINT pk_mg_emr_document PRIMARY KEY (id)
);
COMMENT ON TABLE  mg_emr_document               IS '既往病历文书：门诊/入院/病程/出院小结等';
COMMENT ON COLUMN mg_emr_document.id            IS '主键';
COMMENT ON COLUMN mg_emr_document.tenant_id     IS '租户标识';
COMMENT ON COLUMN mg_emr_document.patient_id    IS '患者标识，逻辑关联 mg_patient';
COMMENT ON COLUMN mg_emr_document.doc_type      IS '文书类型：OUTPATIENT 门诊病历 / ADMISSION 入院记录 / PROGRESS 病程记录 / DISCHARGE 出院小结 / CONSULT 会诊记录';
COMMENT ON COLUMN mg_emr_document.doc_title     IS '文书标题';
COMMENT ON COLUMN mg_emr_document.dept_code     IS '所属科室编码';
COMMENT ON COLUMN mg_emr_document.record_time   IS '记录日期，用于时间衰减重排，近期记录优先';
COMMENT ON COLUMN mg_emr_document.doc_content   IS '文书正文';
COMMENT ON COLUMN mg_emr_document.section_json  IS '按语义小节切分的内容（JSONB）：主诉/现病史/既往史/体格检查等，供分块检索';
COMMENT ON COLUMN mg_emr_document.icd10_codes   IS '涉及疾病编码列表';
COMMENT ON COLUMN mg_emr_document.source_system IS '来源系统标识';
COMMENT ON COLUMN mg_emr_document.doc_no        IS '院内文书编号';
COMMENT ON COLUMN mg_emr_document.create_by     IS '创建人标识';
COMMENT ON COLUMN mg_emr_document.create_time   IS '创建时间';
COMMENT ON COLUMN mg_emr_document.update_by     IS '最后更新人标识';
COMMENT ON COLUMN mg_emr_document.update_time   IS '最后更新时间，由应用层维护';
COMMENT ON COLUMN mg_emr_document.del_flag      IS '软删除标记，本表不实际使用';
COMMENT ON COLUMN mg_emr_document.remark        IS '备注';

CREATE INDEX IF NOT EXISTS idx_mg_emrdoc_tenant_patient_time ON mg_emr_document (tenant_id, patient_id, record_time DESC);
CREATE INDEX IF NOT EXISTS idx_mg_emrdoc_tenant_type         ON mg_emr_document (tenant_id, patient_id, doc_type);
CREATE INDEX IF NOT EXISTS idx_mg_emrdoc_section_gin         ON mg_emr_document USING gin (section_json jsonb_path_ops);
COMMENT ON INDEX idx_mg_emrdoc_tenant_patient_time IS '查询患者病历文书，按记录时间倒序';
COMMENT ON INDEX idx_mg_emrdoc_tenant_type IS '按文书类型筛选';
COMMENT ON INDEX idx_mg_emrdoc_section_gin IS 'GIN 索引：按小节内容检索';

-- =============================================================================
-- 表：mg_appointment  挂号记录
-- 说明：appointment_no 唯一约束是幂等的实现手段。
-- =============================================================================
CREATE TABLE IF NOT EXISTS mg_appointment (
    id                 varchar(32) NOT NULL DEFAULT replace(gen_random_uuid()::text, '-', ''),
    tenant_id          varchar(32) NOT NULL,
    appointment_no     varchar(64) NOT NULL,
    session_id         varchar(32),
    patient_id         varchar(32),
    dept_code          varchar(32) NOT NULL,
    doctor_id          varchar(32),
    schedule_date      date        NOT NULL,
    time_slot          varchar(32),
    slot_id            varchar(64),
    status             varchar(16) NOT NULL DEFAULT 'BOOKED',
    cancel_time        timestamptz,
    external_order_id  varchar(64),
    create_by          varchar(32),
    create_time        timestamptz NOT NULL DEFAULT now(),
    update_by          varchar(32),
    update_time        timestamptz,
    del_flag           char(1)     NOT NULL DEFAULT '0',
    remark             varchar(500),
    CONSTRAINT pk_mg_appointment PRIMARY KEY (id)
);
COMMENT ON TABLE  mg_appointment                    IS '挂号记录：号源预约结果';
COMMENT ON COLUMN mg_appointment.id                 IS '主键';
COMMENT ON COLUMN mg_appointment.tenant_id          IS '租户标识';
COMMENT ON COLUMN mg_appointment.appointment_no     IS '预约单号，租户内唯一，同时作为幂等键';
COMMENT ON COLUMN mg_appointment.session_id         IS '来源会话标识，逻辑关联 mg_session，线下挂号时为空';
COMMENT ON COLUMN mg_appointment.patient_id         IS '患者标识，逻辑关联 mg_patient';
COMMENT ON COLUMN mg_appointment.dept_code          IS '挂号科室编码';
COMMENT ON COLUMN mg_appointment.doctor_id          IS '医生标识，逻辑关联 mg_user';
COMMENT ON COLUMN mg_appointment.schedule_date      IS '就诊日期';
COMMENT ON COLUMN mg_appointment.time_slot          IS '就诊时段';
COMMENT ON COLUMN mg_appointment.slot_id            IS '外部系统号源标识';
COMMENT ON COLUMN mg_appointment.status             IS '状态：BOOKED 已预约 / CANCELLED 已取消 / COMPLETED 已完成 / NOSHOW 爽约';
COMMENT ON COLUMN mg_appointment.cancel_time        IS '取消时间';
COMMENT ON COLUMN mg_appointment.external_order_id  IS '外部系统返回的订单标识';
COMMENT ON COLUMN mg_appointment.create_by          IS '创建人标识';
COMMENT ON COLUMN mg_appointment.create_time        IS '创建时间';
COMMENT ON COLUMN mg_appointment.update_by          IS '最后更新人标识';
COMMENT ON COLUMN mg_appointment.update_time        IS '最后更新时间，由应用层维护';
COMMENT ON COLUMN mg_appointment.del_flag           IS '软删除标记，本表不实际使用';
COMMENT ON COLUMN mg_appointment.remark             IS '备注';

CREATE UNIQUE INDEX IF NOT EXISTS uk_mg_appt_tenant_no       ON mg_appointment (tenant_id, appointment_no);
CREATE INDEX IF NOT EXISTS idx_mg_appt_tenant_session        ON mg_appointment (tenant_id, session_id);
CREATE INDEX IF NOT EXISTS idx_mg_appt_tenant_patient        ON mg_appointment (tenant_id, patient_id, schedule_date DESC);
CREATE INDEX IF NOT EXISTS idx_mg_appt_tenant_slot           ON mg_appointment (tenant_id, slot_id, status);
COMMENT ON INDEX uk_mg_appt_tenant_no IS '预约单号租户内唯一，重复提交时靠唯一约束保证幂等';
COMMENT ON INDEX idx_mg_appt_tenant_session IS '按会话查询挂号记录';
COMMENT ON INDEX idx_mg_appt_tenant_patient IS '查询患者挂号历史';
COMMENT ON INDEX idx_mg_appt_tenant_slot IS '号源占用查询';

-- =============================================================================
-- 表：mg_kb_entry  知识库条目
-- 说明：知识库的唯一真相。entry_code 是入库幂等键。
-- =============================================================================
CREATE TABLE IF NOT EXISTS mg_kb_entry (
    id             varchar(32)  NOT NULL DEFAULT replace(gen_random_uuid()::text, '-', ''),
    tenant_id      varchar(32)  NOT NULL,
    kb_type        varchar(32)  NOT NULL,
    entry_code     varchar(128) NOT NULL,
    title          varchar(255),
    content        text         NOT NULL,
    content_json   jsonb,
    dept_code      varchar(32),
    icd10_codes    varchar(16)[],
    age_group      varchar(16),
    gender         char(1),
    source         varchar(255),
    entry_version  varchar(32),
    status         char(1)      NOT NULL DEFAULT '0',
    is_active      char(1)      NOT NULL DEFAULT '0',
    create_by      varchar(32),
    create_time    timestamptz  NOT NULL DEFAULT now(),
    update_by      varchar(32),
    update_time    timestamptz,
    del_flag       char(1)      NOT NULL DEFAULT '0',
    remark         varchar(500),
    CONSTRAINT pk_mg_kb_entry PRIMARY KEY (id)
);
COMMENT ON TABLE  mg_kb_entry                IS '知识库条目：知识库的唯一真相，向量库由此派生';
COMMENT ON COLUMN mg_kb_entry.id             IS '主键';
COMMENT ON COLUMN mg_kb_entry.tenant_id      IS '租户标识';
COMMENT ON COLUMN mg_kb_entry.kb_type        IS '知识类型：DEPT_EXPERTISE 科室专长 / SYMPTOM_DISEASE 症状疾病 / GUIDELINE 诊疗指南 / ICD-10 编码对照 / DRUG_SAFETY 用药禁忌 / CASE 脱敏病例';
COMMENT ON COLUMN mg_kb_entry.entry_code     IS '条目标识，租户内唯一，入库幂等键';
COMMENT ON COLUMN mg_kb_entry.title          IS '标题';
COMMENT ON COLUMN mg_kb_entry.content        IS '正文内容，用于向量化与全文检索';
COMMENT ON COLUMN mg_kb_entry.content_json   IS '结构化附加内容（JSONB），按知识类型不同：编码、别名、禁忌人群等';
COMMENT ON COLUMN mg_kb_entry.dept_code      IS '归属科室编码';
COMMENT ON COLUMN mg_kb_entry.icd10_codes    IS '涉及疾病编码列表';
COMMENT ON COLUMN mg_kb_entry.age_group      IS '适用年龄段：child 儿童 / adult 成人 / elderly 老年 / all 通用';
COMMENT ON COLUMN mg_kb_entry.gender         IS '适用性别：1 男 / 2 女 / 0 通用';
COMMENT ON COLUMN mg_kb_entry.source         IS '来源说明，如指南名称与年份、科室简介版本';
COMMENT ON COLUMN mg_kb_entry.entry_version  IS '条目版本';
COMMENT ON COLUMN mg_kb_entry.status         IS '状态：0 草稿 / 1 已发布 / 2 已停用';
COMMENT ON COLUMN mg_kb_entry.is_active      IS '是否参与检索：1 参与 / 0 不参与。与 status 是两个不同维度';
COMMENT ON COLUMN mg_kb_entry.create_by      IS '创建人标识';
COMMENT ON COLUMN mg_kb_entry.create_time    IS '创建时间';
COMMENT ON COLUMN mg_kb_entry.update_by      IS '最后更新人标识';
COMMENT ON COLUMN mg_kb_entry.update_time    IS '最后更新时间，由应用层维护';
COMMENT ON COLUMN mg_kb_entry.del_flag       IS '软删除标记：0 正常 / 1 已删除（条目停用即置 1，不提供物理删除）';
COMMENT ON COLUMN mg_kb_entry.remark         IS '备注';

CREATE UNIQUE INDEX IF NOT EXISTS uk_mg_kb_tenant_code        ON mg_kb_entry (tenant_id, entry_code);
CREATE INDEX IF NOT EXISTS idx_mg_kb_tenant_type_status       ON mg_kb_entry (tenant_id, kb_type, status, is_active);
CREATE INDEX IF NOT EXISTS idx_mg_kb_tenant_dept              ON mg_kb_entry (tenant_id, dept_code) WHERE del_flag = '0';
CREATE INDEX IF NOT EXISTS idx_mg_kb_content_json_gin         ON mg_kb_entry USING gin (content_json jsonb_path_ops);
CREATE INDEX IF NOT EXISTS idx_mg_kb_content_gin              ON mg_kb_entry USING gin (to_tsvector('simple', coalesce(title, '') || ' ' || content));
COMMENT ON INDEX uk_mg_kb_tenant_code IS '条目标识租户内唯一，入库时按此字段 upsert 保证幂等';
COMMENT ON INDEX idx_mg_kb_tenant_type_status IS '按知识类型与发布状态筛选';
COMMENT ON INDEX idx_mg_kb_tenant_dept IS '部分索引：按科室筛选未删除条目';
COMMENT ON INDEX idx_mg_kb_content_json_gin IS 'GIN 索引：按结构化内容检索';
COMMENT ON INDEX idx_mg_kb_content_gin IS 'GIN 全文索引：知识库关键词搜索';

-- =============================================================================
-- 表：mg_kb_entry_history  知识库变更记录
-- 说明：只追加表，不含 del_flag。
-- =============================================================================
CREATE TABLE IF NOT EXISTS mg_kb_entry_history (
    id              varchar(32)  NOT NULL DEFAULT replace(gen_random_uuid()::text, '-', ''),
    tenant_id       varchar(32)  NOT NULL,
    entry_id        varchar(32)  NOT NULL,
    entry_code      varchar(128) NOT NULL,
    change_type     varchar(16)  NOT NULL,
    before_json     jsonb,
    after_json      jsonb,
    changed_fields  varchar(32)[],
    operator        varchar(32)  NOT NULL,
    operator_name   varchar(64),
    kb_version      varchar(64),
    create_by       varchar(32),
    create_time     timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT pk_mg_kb_entry_history PRIMARY KEY (id)
);
COMMENT ON TABLE  mg_kb_entry_history                IS '知识库变更记录：只追加，不设软删除标记';
COMMENT ON COLUMN mg_kb_entry_history.id             IS '主键';
COMMENT ON COLUMN mg_kb_entry_history.tenant_id      IS '租户标识';
COMMENT ON COLUMN mg_kb_entry_history.entry_id       IS '条目标识，逻辑关联 mg_kb_entry';
COMMENT ON COLUMN mg_kb_entry_history.entry_code     IS '条目标识编码，冗余存储：条目停用后仍可识别';
COMMENT ON COLUMN mg_kb_entry_history.change_type    IS '变更类型：CREATE 新增 / UPDATE 修改 / ENABLE 启用 / DISABLE 停用';
COMMENT ON COLUMN mg_kb_entry_history.before_json    IS '变更前内容（JSONB），新增时为空';
COMMENT ON COLUMN mg_kb_entry_history.after_json     IS '变更后内容（JSONB），停用时为状态快照';
COMMENT ON COLUMN mg_kb_entry_history.changed_fields IS '本次变更涉及的字段名列表';
COMMENT ON COLUMN mg_kb_entry_history.operator       IS '操作人标识';
COMMENT ON COLUMN mg_kb_entry_history.operator_name  IS '操作人姓名快照';
COMMENT ON COLUMN mg_kb_entry_history.kb_version     IS '变更后的知识库版本标识';
COMMENT ON COLUMN mg_kb_entry_history.create_by      IS '创建人标识';
COMMENT ON COLUMN mg_kb_entry_history.create_time    IS '创建时间';

CREATE INDEX IF NOT EXISTS idx_mg_kbh_tenant_entry ON mg_kb_entry_history (tenant_id, entry_id, create_time DESC);
CREATE INDEX IF NOT EXISTS idx_mg_kbh_tenant_time  ON mg_kb_entry_history (tenant_id, create_time DESC);
COMMENT ON INDEX idx_mg_kbh_tenant_entry IS '查询条目的变更历史';
COMMENT ON INDEX idx_mg_kbh_tenant_time IS '按时间查询全局变更流水';

-- =============================================================================
-- 表：mg_kb_publish  知识库发布版本
-- 说明：快照是发布留痕与迁移介质，不是数据源。一期不支持回滚。
-- =============================================================================
CREATE TABLE IF NOT EXISTS mg_kb_publish (
    id               varchar(32)  NOT NULL DEFAULT replace(gen_random_uuid()::text, '-', ''),
    tenant_id        varchar(32)  NOT NULL,
    version_tag      varchar(64)  NOT NULL,
    entry_count      integer      NOT NULL DEFAULT 0,
    snapshot_path    varchar(500),
    snapshot_hash    varchar(64),
    published_by     varchar(32)  NOT NULL,
    published_time   timestamptz  NOT NULL DEFAULT now(),
    create_by        varchar(32),
    create_time      timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT pk_mg_kb_publish PRIMARY KEY (id)
);
COMMENT ON TABLE  mg_kb_publish                IS '知识库发布版本：发布留痕与跨环境迁移介质';
COMMENT ON COLUMN mg_kb_publish.id             IS '主键';
COMMENT ON COLUMN mg_kb_publish.tenant_id      IS '租户标识';
COMMENT ON COLUMN mg_kb_publish.version_tag    IS '版本标识，租户内唯一，如 kb-v2026.10.15';
COMMENT ON COLUMN mg_kb_publish.entry_count    IS '发布的条目数';
COMMENT ON COLUMN mg_kb_publish.snapshot_path  IS '快照文件位置';
COMMENT ON COLUMN mg_kb_publish.snapshot_hash  IS '快照内容哈希，用于校验完整性';
COMMENT ON COLUMN mg_kb_publish.published_by   IS '发布人标识';
COMMENT ON COLUMN mg_kb_publish.published_time IS '发布时间';
COMMENT ON COLUMN mg_kb_publish.create_by      IS '创建人标识';
COMMENT ON COLUMN mg_kb_publish.create_time    IS '创建时间';

CREATE UNIQUE INDEX IF NOT EXISTS uk_mg_kbpub_tenant_tag ON mg_kb_publish (tenant_id, version_tag);
CREATE INDEX IF NOT EXISTS idx_mg_kbpub_tenant_time      ON mg_kb_publish (tenant_id, published_time DESC);
COMMENT ON INDEX uk_mg_kbpub_tenant_tag IS '版本标识租户内唯一';
COMMENT ON INDEX idx_mg_kbpub_tenant_time IS '按时间查询发布历史';

-- =============================================================================
-- 表：mg_kb_ingest_task  知识库入库任务
-- 说明：异步任务记录，部分索引只索引未完成任务。
-- =============================================================================
CREATE TABLE IF NOT EXISTS mg_kb_ingest_task (
    id              varchar(32) NOT NULL DEFAULT replace(gen_random_uuid()::text, '-', ''),
    tenant_id       varchar(32) NOT NULL,
    task_no         varchar(64) NOT NULL,
    status          varchar(16) NOT NULL DEFAULT 'PENDING',
    stage           varchar(32),
    progress        integer     NOT NULL DEFAULT 0,
    total_count     integer     NOT NULL DEFAULT 0,
    added_count     integer     NOT NULL DEFAULT 0,
    updated_count   integer     NOT NULL DEFAULT 0,
    disabled_count  integer     NOT NULL DEFAULT 0,
    failed_count    integer     NOT NULL DEFAULT 0,
    error_json      jsonb,
    triggered_by    varchar(32),
    started_time    timestamptz,
    finished_time   timestamptz,
    create_by       varchar(32),
    create_time     timestamptz NOT NULL DEFAULT now(),
    update_by       varchar(32),
    update_time     timestamptz,
    del_flag        char(1)     NOT NULL DEFAULT '0',
    remark          varchar(500),
    CONSTRAINT pk_mg_kb_ingest_task PRIMARY KEY (id)
);
COMMENT ON TABLE  mg_kb_ingest_task                IS '知识库入库任务：异步任务的执行记录与统计';
COMMENT ON COLUMN mg_kb_ingest_task.id             IS '主键';
COMMENT ON COLUMN mg_kb_ingest_task.tenant_id      IS '租户标识';
COMMENT ON COLUMN mg_kb_ingest_task.task_no        IS '任务编号，租户内唯一';
COMMENT ON COLUMN mg_kb_ingest_task.status         IS '状态：PENDING 待执行 / RUNNING 执行中 / SUCCESS 成功 / FAILED 失败 / ABORTED 已中止';
COMMENT ON COLUMN mg_kb_ingest_task.stage          IS '当前阶段：VALIDATE 校验 / DIFF 差异比对 / EMBED 向量化 / WRITE 写入 / VERIFY 验证';
COMMENT ON COLUMN mg_kb_ingest_task.progress       IS '进度百分比，取值 0 到 100';
COMMENT ON COLUMN mg_kb_ingest_task.total_count    IS '总条目数';
COMMENT ON COLUMN mg_kb_ingest_task.added_count    IS '新增条目数';
COMMENT ON COLUMN mg_kb_ingest_task.updated_count  IS '修改条目数';
COMMENT ON COLUMN mg_kb_ingest_task.disabled_count IS '停用条目数';
COMMENT ON COLUMN mg_kb_ingest_task.failed_count   IS '校验失败条目数';
COMMENT ON COLUMN mg_kb_ingest_task.error_json     IS '失败条目明细（JSONB）：条目编码与错误原因';
COMMENT ON COLUMN mg_kb_ingest_task.triggered_by   IS '触发人标识';
COMMENT ON COLUMN mg_kb_ingest_task.started_time   IS '开始时间';
COMMENT ON COLUMN mg_kb_ingest_task.finished_time  IS '完成时间';
COMMENT ON COLUMN mg_kb_ingest_task.create_by      IS '创建人标识';
COMMENT ON COLUMN mg_kb_ingest_task.create_time    IS '创建时间';
COMMENT ON COLUMN mg_kb_ingest_task.update_by      IS '最后更新人标识';
COMMENT ON COLUMN mg_kb_ingest_task.update_time    IS '最后更新时间，由应用层维护';
COMMENT ON COLUMN mg_kb_ingest_task.del_flag       IS '软删除标记：0 正常 / 1 已删除（任务记录可按保留期清理）';
COMMENT ON COLUMN mg_kb_ingest_task.remark         IS '备注';

CREATE UNIQUE INDEX IF NOT EXISTS uk_mg_kbing_tenant_no  ON mg_kb_ingest_task (tenant_id, task_no);
CREATE INDEX IF NOT EXISTS idx_mg_kbing_tenant_status    ON mg_kb_ingest_task (tenant_id, create_time DESC) WHERE status IN ('PENDING', 'RUNNING');
CREATE INDEX IF NOT EXISTS idx_mg_kbing_tenant_time      ON mg_kb_ingest_task (tenant_id, create_time DESC);
COMMENT ON INDEX uk_mg_kbing_tenant_no IS '任务编号租户内唯一';
COMMENT ON INDEX idx_mg_kbing_tenant_status IS '部分索引：只索引未完成任务，用于防止重复触发与统计任务积压';
COMMENT ON INDEX idx_mg_kbing_tenant_time IS '按时间查询任务历史';

-- =============================================================================
-- 表：mg_golden_query  黄金查询集
-- 说明：知识库变更的质量闸门。expect_not_depts 用于验证串扰。
-- =============================================================================
CREATE TABLE IF NOT EXISTS mg_golden_query (
    id               varchar(32)  NOT NULL DEFAULT replace(gen_random_uuid()::text, '-', ''),
    tenant_id        varchar(32)  NOT NULL,
    query_code       varchar(64)  NOT NULL,
    query_text       text         NOT NULL,
    expect_depts     varchar(32)[],
    expect_not_depts varchar(32)[],
    expect_route     varchar(32),
    category         varchar(64),
    is_active        char(1)      NOT NULL DEFAULT '1',
    description      varchar(500),
    create_by        varchar(32),
    create_time      timestamptz  NOT NULL DEFAULT now(),
    update_by        varchar(32),
    update_time      timestamptz,
    del_flag         char(1)      NOT NULL DEFAULT '0',
    remark           varchar(500),
    CONSTRAINT pk_mg_golden_query PRIMARY KEY (id)
);
COMMENT ON TABLE  mg_golden_query                IS '黄金查询集：知识库变更后的回归验证用例';
COMMENT ON COLUMN mg_golden_query.id             IS '主键';
COMMENT ON COLUMN mg_golden_query.tenant_id      IS '租户标识';
COMMENT ON COLUMN mg_golden_query.query_code     IS '用例编号，租户内唯一';
COMMENT ON COLUMN mg_golden_query.query_text     IS '查询文本，模拟患者主诉';
COMMENT ON COLUMN mg_golden_query.expect_depts   IS '期望召回的科室编码列表';
COMMENT ON COLUMN mg_golden_query.expect_not_depts IS '期望不应出现的科室编码列表，用于验证串扰';
COMMENT ON COLUMN mg_golden_query.expect_route   IS '期望的路由去向，如 EMERGENCY';
COMMENT ON COLUMN mg_golden_query.category       IS '用例分类，如跨科室歧义、危重症、口语化表述';
COMMENT ON COLUMN mg_golden_query.is_active      IS '是否启用：1 启用 / 0 停用';
COMMENT ON COLUMN mg_golden_query.description    IS '用例说明';
COMMENT ON COLUMN mg_golden_query.create_by      IS '创建人标识';
COMMENT ON COLUMN mg_golden_query.create_time    IS '创建时间';
COMMENT ON COLUMN mg_golden_query.update_by      IS '最后更新人标识';
COMMENT ON COLUMN mg_golden_query.update_time    IS '最后更新时间，由应用层维护';
COMMENT ON COLUMN mg_golden_query.del_flag       IS '软删除标记：0 正常 / 1 已删除';
COMMENT ON COLUMN mg_golden_query.remark         IS '备注';

CREATE UNIQUE INDEX IF NOT EXISTS uk_mg_gq_tenant_code  ON mg_golden_query (tenant_id, query_code);
CREATE INDEX IF NOT EXISTS idx_mg_gq_tenant_active      ON mg_golden_query (tenant_id, category) WHERE is_active = '1';
COMMENT ON INDEX uk_mg_gq_tenant_code IS '用例编号租户内唯一';
COMMENT ON INDEX idx_mg_gq_tenant_active IS '部分索引：只取启用中的用例执行回归';

-- =============================================================================
-- 表：mg_golden_query_run  回归执行记录
-- 说明：retrieval_mode 字段与索引是判断混合检索是否值得保留的数据来源。
-- =============================================================================
CREATE TABLE IF NOT EXISTS mg_golden_query_run (
    id              varchar(32)  NOT NULL DEFAULT replace(gen_random_uuid()::text, '-', ''),
    tenant_id       varchar(32)  NOT NULL,
    run_no          varchar(64)  NOT NULL,
    kb_version      varchar(64),
    retrieval_mode  varchar(16),
    total_count     integer      NOT NULL DEFAULT 0,
    passed_count    integer      NOT NULL DEFAULT 0,
    failed_count    integer      NOT NULL DEFAULT 0,
    pass_rate       numeric(5,4),
    baseline_rate   numeric(5,4),
    is_regression   char(1)      NOT NULL DEFAULT '0',
    failed_json     jsonb,
    duration_ms     integer,
    triggered_by    varchar(32),
    create_by       varchar(32),
    create_time     timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT pk_mg_golden_query_run PRIMARY KEY (id)
);
COMMENT ON TABLE  mg_golden_query_run                IS '回归执行记录：黄金查询集的执行结果';
COMMENT ON COLUMN mg_golden_query_run.id             IS '主键';
COMMENT ON COLUMN mg_golden_query_run.tenant_id      IS '租户标识';
COMMENT ON COLUMN mg_golden_query_run.run_no         IS '执行批次编号，租户内唯一';
COMMENT ON COLUMN mg_golden_query_run.kb_version     IS '本次回归对应的知识库版本';
COMMENT ON COLUMN mg_golden_query_run.retrieval_mode IS '本次采用的检索模式：DENSE 仅语义 / SPARSE 仅词元 / HYBRID 融合';
COMMENT ON COLUMN mg_golden_query_run.total_count    IS '用例总数';
COMMENT ON COLUMN mg_golden_query_run.passed_count   IS '通过数';
COMMENT ON COLUMN mg_golden_query_run.failed_count   IS '失败数';
COMMENT ON COLUMN mg_golden_query_run.pass_rate      IS '通过率';
COMMENT ON COLUMN mg_golden_query_run.baseline_rate  IS '基线通过率，用于判断是否退化';
COMMENT ON COLUMN mg_golden_query_run.is_regression  IS '是否低于基线：1 是 / 0 否';
COMMENT ON COLUMN mg_golden_query_run.failed_json    IS '失败用例明细（JSONB）：用例编号、查询、期望、实际';
COMMENT ON COLUMN mg_golden_query_run.duration_ms    IS '总耗时（毫秒）';
COMMENT ON COLUMN mg_golden_query_run.triggered_by   IS '触发人标识';
COMMENT ON COLUMN mg_golden_query_run.create_by      IS '创建人标识';
COMMENT ON COLUMN mg_golden_query_run.create_time    IS '创建时间';

CREATE UNIQUE INDEX IF NOT EXISTS uk_mg_gqr_tenant_no ON mg_golden_query_run (tenant_id, run_no);
CREATE INDEX IF NOT EXISTS idx_mg_gqr_tenant_time     ON mg_golden_query_run (tenant_id, create_time DESC);
CREATE INDEX IF NOT EXISTS idx_mg_gqr_tenant_mode     ON mg_golden_query_run (tenant_id, retrieval_mode, create_time DESC);
COMMENT ON INDEX uk_mg_gqr_tenant_no IS '批次编号租户内唯一';
COMMENT ON INDEX idx_mg_gqr_tenant_time IS '按时间查询回归历史';
COMMENT ON INDEX idx_mg_gqr_tenant_mode IS '按检索模式对比通过率，支撑混合检索增益的判断';

-- =============================================================================
-- 表：mg_model_provider  模型服务配置
-- 说明：支撑推理后端配置化切换，密钥加密存储。
-- =============================================================================
CREATE TABLE IF NOT EXISTS mg_model_provider (
    id                varchar(32)  NOT NULL DEFAULT replace(gen_random_uuid()::text, '-', ''),
    tenant_id         varchar(32)  NOT NULL,
    provider_code     varchar(64)  NOT NULL,
    provider_type     varchar(32)  NOT NULL,
    provider_name     varchar(128),
    base_url          varchar(500) NOT NULL,
    model_name        varchar(128),
    api_key_enc       varchar(500),
    is_default        char(1)      NOT NULL DEFAULT '0',
    is_on_prem        char(1)      NOT NULL DEFAULT '0',
    timeout_seconds   integer      DEFAULT 60,
    extra_json        jsonb,
    status            char(1)      NOT NULL DEFAULT '1',
    create_by         varchar(32),
    create_time       timestamptz  NOT NULL DEFAULT now(),
    update_by         varchar(32),
    update_time       timestamptz,
    del_flag          char(1)      NOT NULL DEFAULT '0',
    remark            varchar(500),
    CONSTRAINT pk_mg_model_provider PRIMARY KEY (id)
);
COMMENT ON TABLE  mg_model_provider               IS '模型服务配置：推理后端的可配置信息';
COMMENT ON COLUMN mg_model_provider.id            IS '主键';
COMMENT ON COLUMN mg_model_provider.tenant_id     IS '租户标识';
COMMENT ON COLUMN mg_model_provider.provider_code IS '配置编码，租户内唯一';
COMMENT ON COLUMN mg_model_provider.provider_type IS '类型：LLM 内容生成 / EMBEDDING 向量化 / RERANK 精排 / ASR 语音识别';
COMMENT ON COLUMN mg_model_provider.provider_name IS '配置名称，如院内推理服务';
COMMENT ON COLUMN mg_model_provider.base_url      IS '服务地址';
COMMENT ON COLUMN mg_model_provider.model_name    IS '模型名称';
COMMENT ON COLUMN mg_model_provider.api_key_enc   IS '访问密钥，加密存储；界面与日志中脱敏展示';
COMMENT ON COLUMN mg_model_provider.is_default    IS '是否同类型默认：1 是 / 0 否';
COMMENT ON COLUMN mg_model_provider.is_on_prem    IS '是否院内地址：1 是 / 0 否，供出域守卫直接依据配置判定';
COMMENT ON COLUMN mg_model_provider.timeout_seconds IS '调用超时（秒）';
COMMENT ON COLUMN mg_model_provider.extra_json    IS '扩展参数（JSONB），如温度、最大输出长度';
COMMENT ON COLUMN mg_model_provider.status        IS '状态：1 启用 / 0 停用';
COMMENT ON COLUMN mg_model_provider.create_by     IS '创建人标识';
COMMENT ON COLUMN mg_model_provider.create_time   IS '创建时间';
COMMENT ON COLUMN mg_model_provider.update_by     IS '最后更新人标识';
COMMENT ON COLUMN mg_model_provider.update_time   IS '最后更新时间，由应用层维护';
COMMENT ON COLUMN mg_model_provider.del_flag      IS '软删除标记：0 正常 / 1 已删除';
COMMENT ON COLUMN mg_model_provider.remark        IS '备注';

CREATE UNIQUE INDEX IF NOT EXISTS uk_mg_model_tenant_code ON mg_model_provider (tenant_id, provider_code);
CREATE INDEX IF NOT EXISTS idx_mg_model_tenant_type       ON mg_model_provider (tenant_id, provider_type, is_default) WHERE del_flag = '0';
COMMENT ON INDEX uk_mg_model_tenant_code IS '配置编码租户内唯一';
COMMENT ON INDEX idx_mg_model_tenant_type IS '部分索引：取某类型的默认配置';

-- =============================================================================
-- 表：mg_audit_log  审计记录
-- 说明：只追加、不可修改、不可删除。结构上不含 update_* 与 del_flag。
-- =============================================================================
CREATE TABLE IF NOT EXISTS mg_audit_log (
    id            varchar(32) NOT NULL DEFAULT replace(gen_random_uuid()::text, '-', ''),
    tenant_id     varchar(32) NOT NULL,
    actor_id      varchar(32),
    actor_role    varchar(32),
    action_type   varchar(32) NOT NULL,
    target_type   varchar(64),
    target_id     varchar(32),
    patient_hash  varchar(64),
    session_id    varchar(32),
    result        varchar(16) NOT NULL DEFAULT 'SUCCESS',
    fail_reason   varchar(255),
    detail_json   jsonb,
    client_ip     varchar(64),
    trace_id      varchar(64),
    action_time   timestamptz NOT NULL DEFAULT now(),
    create_by     varchar(32),
    create_time   timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_mg_audit_log PRIMARY KEY (id)
);
COMMENT ON TABLE  mg_audit_log               IS '审计记录：只追加、不可修改、不可删除。不与其他表建立逻辑关联';
COMMENT ON COLUMN mg_audit_log.id            IS '主键';
COMMENT ON COLUMN mg_audit_log.tenant_id     IS '租户标识';
COMMENT ON COLUMN mg_audit_log.actor_id      IS '操作人标识，系统操作填 system';
COMMENT ON COLUMN mg_audit_log.actor_role    IS '操作人角色';
COMMENT ON COLUMN mg_audit_log.action_type   IS '操作类型：EMR_READ 病历读取 / EXTERNAL_CALL 外部调用 / TRIAGE_CONFIRM 分诊确认 / TRIAGE_CORRECT 分诊修正 / PERM_CHANGE 权限变更 / KB_CHANGE 知识库变更 / EGRESS_BLOCK 出域拦截 / DATA_ARCHIVE 数据归档';
COMMENT ON COLUMN mg_audit_log.target_type   IS '操作对象类型';
COMMENT ON COLUMN mg_audit_log.target_id     IS '操作对象标识';
COMMENT ON COLUMN mg_audit_log.patient_hash  IS '涉及的患者标识哈希，不存明文';
COMMENT ON COLUMN mg_audit_log.session_id    IS '关联会话标识';
COMMENT ON COLUMN mg_audit_log.result        IS '结果：SUCCESS 成功 / FAILURE 失败';
COMMENT ON COLUMN mg_audit_log.fail_reason   IS '失败原因';
COMMENT ON COLUMN mg_audit_log.detail_json   IS '附加信息（JSONB）：调用参数摘要、变更前后值等';
COMMENT ON COLUMN mg_audit_log.client_ip     IS '客户端地址';
COMMENT ON COLUMN mg_audit_log.trace_id      IS '追踪标识，用于关联可观测链路';
COMMENT ON COLUMN mg_audit_log.action_time   IS '操作时间';
COMMENT ON COLUMN mg_audit_log.create_by     IS '创建人标识';
COMMENT ON COLUMN mg_audit_log.create_time   IS '创建时间';

CREATE INDEX IF NOT EXISTS idx_mg_audit_tenant_time    ON mg_audit_log (tenant_id, action_time DESC);
CREATE INDEX IF NOT EXISTS idx_mg_audit_tenant_patient ON mg_audit_log (tenant_id, patient_hash, action_time DESC);
CREATE INDEX IF NOT EXISTS idx_mg_audit_tenant_actor   ON mg_audit_log (tenant_id, actor_id, action_time DESC);
CREATE INDEX IF NOT EXISTS idx_mg_audit_tenant_action  ON mg_audit_log (tenant_id, action_type, action_time DESC);
CREATE INDEX IF NOT EXISTS idx_mg_audit_trace          ON mg_audit_log (tenant_id, trace_id);
COMMENT ON INDEX idx_mg_audit_tenant_time IS '按时间查询审计流水';
COMMENT ON INDEX idx_mg_audit_tenant_patient IS '查询某患者的数据被访问的历史';
COMMENT ON INDEX idx_mg_audit_tenant_actor IS '按操作人查询操作历史';
COMMENT ON INDEX idx_mg_audit_tenant_action IS '按操作类型统计，如出域拦截次数';
COMMENT ON INDEX idx_mg_audit_trace IS '按追踪标识关联可观测链路';

-- =============================================================================
-- 表：mg_file  文件与对象
-- 说明：上传文件的元信息。二进制内容存对象存储，本表只存归属关系与对象键。
--       接口 GET /api/v1/files/{file_id} 的鉴权依据来自本表。
-- =============================================================================
CREATE TABLE IF NOT EXISTS mg_file (
    id              varchar(32)  NOT NULL DEFAULT replace(gen_random_uuid()::text, '-', ''),
    tenant_id       varchar(32)  NOT NULL,
    file_name       varchar(255) NOT NULL,
    file_ext        varchar(16),
    mime_type       varchar(128),
    file_size       bigint       NOT NULL,
    file_hash       varchar(64),
    bucket_name     varchar(128) NOT NULL,
    object_key      varchar(500) NOT NULL,
    biz_type        varchar(32)  NOT NULL,
    session_id      varchar(32),
    patient_id      varchar(32),
    biz_ref_id      varchar(32),
    upload_status   varchar(16)  NOT NULL DEFAULT 'DONE',
    create_by       varchar(32),
    create_time     timestamptz  NOT NULL DEFAULT now(),
    update_by       varchar(32),
    update_time     timestamptz,
    del_flag        char(1)      NOT NULL DEFAULT '0',
    remark          varchar(500),
    CONSTRAINT pk_mg_file PRIMARY KEY (id)
);
COMMENT ON TABLE  mg_file                 IS '文件与对象：上传文件元信息，二进制内容存对象存储';
COMMENT ON COLUMN mg_file.id              IS '主键，即接口返回的 file_id';
COMMENT ON COLUMN mg_file.tenant_id       IS '租户标识，所有复合索引首列';
COMMENT ON COLUMN mg_file.file_name       IS '原始文件名（含扩展名）';
COMMENT ON COLUMN mg_file.file_ext        IS '扩展名，小写且不含点';
COMMENT ON COLUMN mg_file.mime_type       IS 'MIME 类型，下载时用于设置响应头';
COMMENT ON COLUMN mg_file.file_size       IS '文件字节数';
COMMENT ON COLUMN mg_file.file_hash       IS '内容 SHA-256，用于租户内秒传与去重';
COMMENT ON COLUMN mg_file.bucket_name     IS '对象存储桶名';
COMMENT ON COLUMN mg_file.object_key      IS '对象键：{tenant_id}/{biz_type}/{yyyyMM}/{file_id}.{ext}';
COMMENT ON COLUMN mg_file.biz_type        IS '业务类型：EMR_ATTACHMENT 病历附件 / VOICE_INPUT 语音输入 / OTHER 其他';
COMMENT ON COLUMN mg_file.session_id      IS '关联会话标识，VOICE_INPUT 时必填';
COMMENT ON COLUMN mg_file.patient_id      IS '关联患者标识，用于鉴权与批量清理';
COMMENT ON COLUMN mg_file.biz_ref_id      IS '关联业务对象标识，如 mg_emr_document.id';
COMMENT ON COLUMN mg_file.upload_status   IS '上传状态：UPLOADING 上传中 / DONE 完成 / FAILED 失败';
COMMENT ON COLUMN mg_file.create_by       IS '创建人标识';
COMMENT ON COLUMN mg_file.create_time     IS '创建时间';
COMMENT ON COLUMN mg_file.update_by       IS '最后更新人标识';
COMMENT ON COLUMN mg_file.update_time     IS '最后更新时间，由应用层维护';
COMMENT ON COLUMN mg_file.del_flag        IS '软删除标记：0 正常 / 1 已删除';
COMMENT ON COLUMN mg_file.remark          IS '备注';

CREATE UNIQUE INDEX IF NOT EXISTS uk_mg_file_tenant_object ON mg_file (tenant_id, object_key);
CREATE INDEX IF NOT EXISTS idx_mg_file_tenant_session      ON mg_file (tenant_id, session_id) WHERE del_flag = '0';
CREATE INDEX IF NOT EXISTS idx_mg_file_tenant_biz          ON mg_file (tenant_id, biz_type, biz_ref_id) WHERE del_flag = '0';
CREATE INDEX IF NOT EXISTS idx_mg_file_tenant_hash         ON mg_file (tenant_id, file_hash);
COMMENT ON INDEX uk_mg_file_tenant_object IS '同一对象不被重复登记';
COMMENT ON INDEX idx_mg_file_tenant_session IS '部分索引：按会话取附件，用于语音与点选图回放';
COMMENT ON INDEX idx_mg_file_tenant_biz IS '部分索引：按业务对象取附件';
COMMENT ON INDEX idx_mg_file_tenant_hash IS '秒传与去重查询';

-- =============================================================================
-- 种子数据
-- 说明：使用固定 32 位标识，ON CONFLICT DO NOTHING 保证可重复执行。
--       口令哈希为 bcrypt 占位符，请在生产环境替换。
-- =============================================================================

-- 默认租户
INSERT INTO mg_tenant (id, tenant_code, tenant_name, hospital_level, status, create_by, remark)
VALUES ('00000000000000000000000000000001', 'HOSP_001', '示例三甲医院', '三级甲等', '1', 'system',
        '种子数据：默认租户，请按实际情况修改')
ON CONFLICT (id) DO NOTHING;

-- 默认机构管理员（账号 admin，密码 admin123）
INSERT INTO mg_user (id, tenant_id, account, real_name, role, credential_hash, status, create_by, remark)
VALUES ('00000000000000000000000000000002', '00000000000000000000000000000001',
        'admin', '系统管理员', 'ORG_ADMIN',
        '$2b$12$REPLACE_WITH_REAL_BCRYPT_HASH_OF_admin123',
        '1', 'system', '种子数据：默认机构管理员，密码 admin123')
ON CONFLICT (id) DO NOTHING;

-- 默认知识库管理员（账号 kbadmin，密码 admin123）
INSERT INTO mg_user (id, tenant_id, account, real_name, role, credential_hash, status, create_by, remark)
VALUES ('00000000000000000000000000000003', '00000000000000000000000000000001',
        'kbadmin', '知识库管理员', 'KB_ADMIN',
        '$2b$12$REPLACE_WITH_REAL_BCRYPT_HASH_OF_admin123',
        '1', 'system', '种子数据：默认知识库管理员，密码 admin123')
ON CONFLICT (id) DO NOTHING;

-- 默认模型服务配置（内容生成）
INSERT INTO mg_model_provider (id, tenant_id, provider_code, provider_type, provider_name,
                               base_url, model_name, is_default, is_on_prem, status, create_by, remark)
VALUES ('00000000000000000000000000000004', '00000000000000000000000000000001',
        'default_llm', 'LLM', '默认内容生成服务',
        'https://api.siliconflow.cn/v1', 'Qwen/Qwen2.5-32B-Instruct',
        '1', '0', '1', 'system',
        '种子数据：开发期默认内容生成服务。生产环境须替换为院内地址并将 is_on_prem 置 1')
ON CONFLICT (id) DO NOTHING;

-- 默认向量化配置（本地模型）
INSERT INTO mg_model_provider (id, tenant_id, provider_code, provider_type, provider_name,
                               base_url, model_name, is_default, is_on_prem, status, create_by, remark)
VALUES ('00000000000000000000000000000005', '00000000000000000000000000000001',
        'default_embedding', 'EMBEDDING', '本地向量化模型',
        'local', 'BAAI/bge-m3',
        '1', '1', '1', 'system',
        '种子数据：本地 BGE-M3，一次推理同时产出稠密与稀疏向量')
ON CONFLICT (id) DO NOTHING;

-- 默认精排配置
INSERT INTO mg_model_provider (id, tenant_id, provider_code, provider_type, provider_name,
                               base_url, model_name, is_default, is_on_prem, status, create_by, remark)
VALUES ('00000000000000000000000000000006', '00000000000000000000000000000001',
        'default_rerank', 'RERANK', '默认精排服务',
        'https://api.siliconflow.cn/v1', 'BAAI/bge-reranker-v2-m3',
        '1', '0', '1', 'system',
        '种子数据：开发期默认精排服务。生产环境须替换为院内地址并将 is_on_prem 置 1')
ON CONFLICT (id) DO NOTHING;

-- 默认系统配置
INSERT INTO mg_sys_config (tenant_id, config_key, config_value, config_type, description, create_by)
VALUES
  ('00000000000000000000000000000001', 'inquiry.max_rounds',          '4',      'number',  '澄清追问轮次上限', 'system'),
  ('00000000000000000000000000000001', 'triage.sufficiency_threshold', '0.75',   'number',  '信息充分度判定阈值', 'system'),
  ('00000000000000000000000000000001', 'triage.confidence_threshold',  '0.60',   'number',  '分诊置信度阈值，低于则转人工', 'system'),
  ('00000000000000000000000000000001', 'triage.dept_gap_threshold',    '0.10',   'number',  '候选科室置信度差值阈值，低于则触发会诊', 'system'),
  ('00000000000000000000000000000001', 'retrieval.mode',               'HYBRID', 'string',  '检索模式：DENSE 仅语义 / SPARSE 仅词元 / HYBRID 融合', 'system'),
  ('00000000000000000000000000000001', 'retrieval.rerank_candidates',  '8',      'number',  '精排候选数，开发期为 CPU 环境收敛', 'system'),
  ('00000000000000000000000000000001', 'session.retention_days',       '90',     'number',  '预问诊会话数据保留天数', 'system'),
  ('00000000000000000000000000000001', 'session.resume_hours',         '24',     'number',  '会话断点恢复的有效期（小时）', 'system'),
  ('00000000000000000000000000000001', 'audit.retention_days',         '365',    'number',  '审计记录保留天数，不少于 1 年', 'system'),
  ('00000000000000000000000000000001', 'security.login_fail_limit',    '5',      'number',  '连续登录失败次数上限', 'system'),
  ('00000000000000000000000000000001', 'security.lock_minutes',        '15',     'number',  '账号锁定时长（分钟）', 'system'),
  ('00000000000000000000000000000001', 'kb.regression_baseline',       '0.90',   'number',  '黄金查询回归的基线通过率', 'system')
ON CONFLICT (tenant_id, config_key) DO NOTHING;

-- =============================================================================
-- 审计表防篡改：任何修改与删除一律拒绝
-- 说明：使用触发器而非 REVOKE 权限。原因：REVOKE 对超级用户无效，
--       而开发与部署默认可能以超级用户连接，会造成"看似已加固"的假象。
--       触发器对所有角色一致生效，不依赖连接身份配置。
--       审计数据只能通过归档（迁移旧分区）清理，不能就地删除。
-- =============================================================================
CREATE OR REPLACE FUNCTION fn_mg_audit_log_immutable()
RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'mg_audit_log is append-only: % is not permitted. Archive old partitions instead.', TG_OP
        USING ERRCODE = 'restrict_violation';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_mg_audit_log_no_update_delete ON mg_audit_log;
CREATE TRIGGER trg_mg_audit_log_no_update_delete
    BEFORE UPDATE OR DELETE ON mg_audit_log
    FOR EACH ROW
    EXECUTE FUNCTION fn_mg_audit_log_immutable();

DROP TRIGGER IF EXISTS trg_mg_audit_log_no_truncate ON mg_audit_log;
CREATE TRIGGER trg_mg_audit_log_no_truncate
    BEFORE TRUNCATE ON mg_audit_log
    FOR EACH STATEMENT
    EXECUTE FUNCTION fn_mg_audit_log_immutable();

COMMENT ON FUNCTION fn_mg_audit_log_immutable() IS '审计表防篡改：UPDATE / DELETE / TRUNCATE 一律抛异常';

DO $$
DECLARE
    v_table_count  integer;
    v_index_count  integer;
BEGIN
    SELECT count(*) INTO v_table_count
      FROM information_schema.tables
     WHERE table_schema = 'public' AND table_name LIKE 'mg\_%';

    SELECT count(*) INTO v_index_count
      FROM pg_indexes
     WHERE schemaname = 'public' AND tablename LIKE 'mg\_%';

    RAISE NOTICE '============================================================';
    RAISE NOTICE 'MedicalGuidance 数据库初始化完成';
    RAISE NOTICE '  业务表数量：%', v_table_count;
    RAISE NOTICE '  索引数量：  %', v_index_count;
    RAISE NOTICE '  向量扩展：  %', (SELECT extversion FROM pg_extension WHERE extname = 'vector');
    RAISE NOTICE '  默认租户：  HOSP_001（示例三甲医院）';
    RAISE NOTICE '  默认账号：  admin / kbadmin（密码 admin123，请立即修改）';
    RAISE NOTICE '============================================================';
END $$;

-- =============================================================================
-- 文件说明
--   本文件由《03-数据库设计说明书》第 4 章同步生成，请勿手工修改。
--   表结构变更：先更新 03 文档第 4 章，再重新同步；或改用 Alembic 迁移脚本。
--   行级安全：一期不启用。启用脚本见 deploy/postgres/migrations/001_enable_rls.sql
-- =============================================================================
