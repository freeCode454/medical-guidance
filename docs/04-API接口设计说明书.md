# 04 · API 接口设计说明书

| 项目名称 | MedicalGuidance 医疗智能导诊分诊与多学科会诊多智能体系统 |
|---|---|
| 文档编号 | MG-API-004 |
| 版本 | v1.0 |
| 编制日期 | 2026-10-15 |
| 编制方 | 个人开发者 |
| 客户 | —（个人作品集项目，无外部客户） |
| 技术栈 | FastAPI 0.115.6 + Pydantic 2.10.4 + PostgreSQL 16.6 + Redis 7.4 + Milvus 2.6.0 |

---

## 1. 引言

### 1.1 文档目的

本文档定义 MedicalGuidance 系统对外暴露的全部 HTTP 与 WebSocket 接口契约。开发人员按本文档实现后端，前端与测试人员按本文档进行联调与用例编写，三方不需要额外的口头约定。

文档覆盖三类读者场景：

| 读者 | 使用方式 |
|---|---|
| 后端开发 | 按第 12 章的接口定义实现，字段名与类型以本文档为准；响应体与错误码按第 3、4 章实现 |
| 前端开发 | 按第 5 章处理认证与 Token 刷新，第 7 章处理分页，第 11 章接入 WebSocket 流式对话 |
| 测试 | 按每个接口的「错误码」与「业务规则」编写用例；第 15.2 节提供常见错误场景清单 |

所有接口均以 `01-需求规格说明书` 的功能需求编号（`F01`~`F56`）为追溯依据，每个接口在「功能说明」中标注对应的需求编号。

### 1.2 设计依据

| 文档 | 编号 | 用途 |
|---|---|---|
| 《01-需求规格说明书》 | MG-SRS-001 | 功能需求、业务规则、验收标准的来源 |
| 《02-系统架构设计说明书》 | MG-ARCH-002 | 分层结构、中间件设计、认证与租户隔离机制 |
| 《03-数据库设计说明书》 | MG-DB-003 | 字段命名、主键格式、实体关系、枚举取值 |

### 1.3 术语表

| 术语 | 英文 | 含义 |
|---|---|---|
| 租户 | Tenant | 使用本系统的医院或院区，是数据隔离的边界 |
| 患者标识哈希 | patient_hash | 患者身份的去标识化标识 |
| 预问诊会话 | Session | 一次完整的预问诊过程，是系统的核心实体 |
| 会话标识 | session_id | 会话的唯一标识，格式为 32 位无连字符字符串 |
| 分诊结论 | Triage Result | 会话产出的建议科室与置信度 |
| 候选科室 | Candidate Department | 检索召回的候选科室及其置信度列表 |
| 路由去向 | Route | 流程的下一步：直接推荐 / 多科会诊 / 转人工 / 急诊 |
| 澄清追问 | Clarifying Inquiry | 信息不足时由系统发起的补充提问 |
| 多学科会诊 | MDT | 多个专科角色并行判断并汇总的过程 |
| 分歧点 | Divergence | 各专科角色结论不一致之处 |
| 信息充分度 | Sufficiency Score | 已采集信息是否足以支撑分诊决策的评分 |
| 信息槽位 | Slot | 分诊所需的结构化信息项 |
| 已问项 | Asked Slot | 已提问过的信息项，用于避免重复提问 |
| 危重症红线 | Critical Redline | 需立即急救的表征集合，命中即中断问诊 |
| SOAP 病历 | SOAP Record | 主观 / 客观 / 评估 / 计划四段结构的病历 |
| 区分度 | Confidence | 候选科室的置信度 |
| 知识库条目 | KB Entry | 支撑分诊的知识内容，是知识库的唯一真相 |
| 知识库入库任务 | Ingest Task | 将知识库条目向量化写入向量库的异步任务 |
| 黄金查询集 | Golden Query | 用于回归验证的固定查询与期望结果 |
| 回归通过率 | Pass Rate | 黄金查询集执行后的通过比例 |
| 人工接管 | Takeover | 医生接手被转人工的会话 |
| 患者授权 | Consent | 患者对既往病历调阅的明示授权 |
| 出域拦截 | Egress Block | 守卫拒绝访问院外地址的记录 |
| 幂等键 | Idempotency-Key | 保证写接口重复提交只生效一次的请求头 |
| 访问令牌 | access_token | 短效期认证凭证 |
| 刷新令牌 | refresh_token | 用于换取新的访问令牌的长效期凭证 |
| 降级 | Degradation | 主能力不可用时切换到简化处理路径 |
| 流式输出 | Streaming | 生成内容逐字返回 |

---

## 2. 接口规范

### 2.1 接口前缀与版本

所有接口统一以 `/api/v1` 为前缀。

```
https://<host>/api/v1/<module>/<resource>
```

**版本演进策略**

| 项 | 规则 |
|---|---|
| 当前版本 | `v1` |
| 版本位置 | **路径中**（`/api/v1/...`），不使用请求头或查询参数 |
| 兼容性变更 | 在 `v1` 内新增字段或接口，不改变版本号。**客户端必须忽略未知字段** |
| 破坏性变更 | 新增 `/api/v2`，`v1` 保留至少 6 个月后再下线 |
| 弃用通知 | 通过响应头 `Deprecation` 与 `Sunset` 提示 |
| 健康检查 | **不带版本前缀**，固定为 `/healthz`，供容器探针使用 |

**与系统架构文档的对应**：架构文档 11.6 节规定 WebSocket 鉴权走端点依赖，因此 WebSocket 路径同样带 `/api/v1` 前缀。

| 协议 | 路径 |
|---|---|
| HTTP | `/api/v1/<module>/<resource>` |
| WebSocket（对话流式） | `/api/v1/ws/sessions/{session_id}` |
| WebSocket（任务进度） | `/api/v1/ws/tasks/{task_id}` |
| 健康检查 | `/healthz`（无版本前缀） |

### 2.2 请求方法语义

| 方法 | 语义 | 幂等 | 使用场景 | 本项目示例 |
|---|---|---|---|---|
| `GET` | 查询资源，不改变服务端状态 | ✅ | 列表、详情、导出 | 查询会话列表 |
| `POST` | 创建资源或执行动作 | ❌ | 新建、触发任务、执行校验 | 创建会话、触发入库 |
| `PUT` | 全量更新资源 | ✅ | 修改知识库条目、更新配置 | 修改条目 |
| `PATCH` | 部分更新资源 | ❌ | 仅修改状态字段 | 本**不使用**，统一用 `POST` 动作接口 |
| `DELETE` | 删除资源 | ✅ | 取消挂号 | 取消预约 |

**本项目对 `PATCH` 与 `DELETE` 的特殊约定**

| 约定 | 说明 |
|---|---|
| 不使用 `PATCH` | 状态变更有业务语义（停用科室、停用条目、取消挂号），统一用 `POST .../{id}/<action>` 表达动作 |
| `DELETE` 仅用于取消预约 | 其余实体的"删除"一律是软删除，用 `POST .../{id}/disable` 表达 |
| 不存在真正的物理删除接口 | 符合需求 `R09`（知识库不提供物理删除）与 `NFR21`（审计不可删除） |

### 2.3 请求头规范

| Header | 必填 | 说明 |
|---|---|---|
| `Authorization` | 除认证接口外必填 | 格式 `Bearer <access_token>` |
| `Content-Type` | 有请求体时必填 | 固定为 `application/json`；文件上传用 `multipart/form-data` |
| `Idempotency-Key` | 写接口建议携带 | 32 位无连字符字符串，用于保证重复提交只生效一次 |
| `X-Request-ID` | 可选 | 客户端生成的请求标识，用于跨系统排查；未传时服务端自动生成 |
| `Accept-Language` | 可选 | 语言偏好，默认 `zh-CN` |
| `X-Client-Version` | 可选 | 客户端版本，用于灰度与问题定位 |

**服务端响应头**

| Header | 说明 |
|---|---|
| `X-Request-ID` | 请求标识，与请求头一致或由服务端生成 |
| `X-Trace-ID` | 链路追踪标识，用于关联完整调用链 |
| `X-RateLimit-Limit` | 当前限流阈值 |
| `X-RateLimit-Remaining` | 当前窗口剩余可用次数 |
| `X-RateLimit-Reset` | 限流窗口重置时间（Unix 时间戳，秒） |
| `Deprecation` | 接口被弃用时返回 |
| `Sunset` | 接口下线时间 |

### 2.4 响应格式规范

所有接口（含错误响应）统一返回以下结构：

```json
{
  "code": 200,
  "data": {},
  "message": "成功"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `code` | integer | 业务状态码。`200` 表示成功，其余见第 4 章 |
| `data` | object / array / null | 业务数据。无返回内容时为 `null`，**不使用空对象占位** |
| `message` | string | 面向调用方的提示文本。成功时固定为 `"成功"` |

**设计说明**

| 设计点 | 理由 |
|---|---|
| 不返回 HTTP 状态码作为唯一判断依据 | 业务错误（如"号源已被占用"）在 HTTP 层仍是 `200`，由 `code` 区分，避免客户端需要同时解析两个维度 |
| HTTP 状态码仍保持语义 | 认证失败返回 `401`、无权限返回 `403`、限流返回 `429`，便于网关与监控识别 |
| `data` 不用空对象占位 | `null` 明确表示"无数据"，`{}` 会产生歧义（是空对象还是有对象但无字段） |

### 2.5 时间与字段命名

| 项 | 规范 |
|---|---|
| 字段命名 | `snake_case`（与数据库字段一致，避免前后端映射时的转换错误） |
| 时间格式 | ISO 8601 带时区偏移，如 `2026-10-15T19:23:41+08:00` |
| 日期格式 | `YYYY-MM-DD`，如 `2026-10-15` |
| 时区 | 统一使用 `Asia/Shanghai`（UTC+8） |
| 时间戳字段 | 一律使用带时区类型，不使用 Unix 秒/毫秒整数 |
| 布尔语义字段 | 数据库用 `char(1)`，**接口层转为 boolean**，如 `is_active: true` |
| 标识字段 | 一律 32 位无连字符字符串，如 `a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6` |
| 枚举字段 | 大写蛇形字符串，如 `PENDING_TAKEOVER` |
| 金额字段 | **本项目不涉及** |

### 2.6 空值处理

| 场景 | 规范 |
|---|---|
| 字段无值 | 返回 `null`，**不返回空字符串**、`0` 或 `"null"` |
| 数组无元素 | 返回 `[]`，不返回 `null`（空数组与"无此字段"语义不同） |
| 请求体中省略字段 | 视为"不修改该字段"（用于 `PUT` 接口） |
| 请求体中显式传 `null` | 视为"将该字段置空"（用于可空字段的清空操作） |
| 字符串字段 | 不做 trim 之外的自动处理；前后空格由服务端统一去除 |

---

## 3. 统一响应格式

### 3.1 成功响应

**单个对象**

```json
{
  "code": 200,
  "data": {
    "id": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
    "session_no": "S20261015000001",
    "status": "IN_PROGRESS",
    "chief_complaint": "肚子疼三天了",
    "inquiry_rounds": 2,
    "started_time": "2026-10-15T19:23:41+08:00"
  },
  "message": "成功"
}
```

**列表（非分页）**

```json
{
  "code": 200,
  "data": [
    {
      "dept_code": "DIG",
      "dept_name": "消化内科"
    },
    {
      "dept_code": "GEN_SURG",
      "dept_name": "普通外科"
    }
  ],
  "message": "成功"
}
```

**无返回数据（如删除成功）**

```json
{
  "code": 200,
  "data": null,
  "message": "成功"
}
```

### 3.2 分页响应

所有列表接口统一使用以下分页结构：

```json
{
  "code": 200,
  "data": {
    "total": 128,
    "page": 1,
    "size": 20,
    "items": [
      {
        "id": "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7",
        "session_no": "S20261015000002",
        "patient_hash": "9f8e7d6c5b4a39281706f5e4d3c2b1a0",
        "status": "PENDING_TAKEOVER",
        "risk_flag": true,
        "started_time": "2026-10-15T18:05:12+08:00"
      }
    ]
  },
  "message": "成功"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `total` | integer | 满足条件的总记录数（不受分页限制） |
| `page` | integer | 当前页码，从 1 开始 |
| `size` | integer | 每页条数 |
| `items` | array | 当前页数据列表；无数据时为 `[]` |

### 3.3 错误响应

```json
{
  "code": 40101,
  "data": null,
  "message": "口令错误，还可尝试 4 次"
}
```

**带字段级错误的响应**（参数校验失败时）

```json
{
  "code": 400,
  "data": {
    "errors": [
      {
        "field": "chief_complaint",
        "message": "主诉字数不能超过 500 字"
      },
      {
        "field": "gender",
        "message": "取值必须是 1、2 或 0"
      }
    ]
  },
  "message": "参数校验失败"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `errors` | array | 字段级错误列表 |
| `errors[].field` | string | 出错的字段名（`snake_case`） |
| `errors[].message` | string | 该字段的具体错误原因 |

---

## 4. 错误码规范

**编码规则**

| 区间 | 含义 |
|---|---|
| `200` | 成功 |
| `400` ~ `599` | 通用错误，取值与 HTTP 状态码一致 |
| `10xxx` | 认证与账号 |
| `20xxx` | 会话与分诊 |
| `30xxx` | 挂号与号源 |
| `40xxx` | 知识库与检索 |
| `50xxx` | 机构与配置 |
| `60xxx` | 外部依赖与系统 |

**通用错误码**

| code | message | 说明 | 触发场景 |
|---|---|---|---|
| `200` | 成功 | 请求成功 | — |
| `400` | 参数校验失败 | 入参不满足校验规则 | 字段缺失、格式错误、超出范围；`data.errors` 给出字段级原因 |
| `401` | 未认证 | 缺少或无法解析 `Authorization` 头 | 未携带 Token |
| `403` | 无权限 | 已认证但角色或数据范围不允许 | 医生访问他人接诊患者；知识库管理员调用机构配置接口 |
| `404` | 资源不存在 | 目标资源不存在或不属于当前租户 | 访问其他租户的资源时同样返回此码，**不暴露"资源存在但无权访问"** |
| `409` | 资源冲突 | 唯一性约束冲突或状态不允许该操作 | 号源已被占用；同一会话重复创建分诊结论 |
| `410` | 资源已失效 | 资源存在但已过期 | 会话超过 24 小时有效期，不可恢复 |
| `422` | 业务规则校验失败 | 满足参数格式但违反业务规则 | 修正理由少于 10 字；停用被引用的科室 |
| `429` | 请求过于频繁 | 触发限流 | 超过接口限流阈值；响应头带 `X-RateLimit-*` |
| `500` | 服务器内部错误 | 未预期异常 | 服务端 bug；`message` 不含堆栈，凭 `X-Trace-ID` 排查 |
| `502` | 外部依赖调用失败 | 调用 HIS / EMR / 推理服务失败且无降级路径 | 挂号接口超时 |
| `503` | 服务暂不可用 | 系统处于降级状态或依赖不可用 | 内容生成能力不可用但未降级 |
| `504` | 外部依赖超时 | 外部依赖调用超时 | 号源查询超过 3 秒 |

**认证与账号（10xxx）**

| code | message | 说明 | 触发场景 |
|---|---|---|---|
| `10001` | 账号或口令错误 | 凭据校验失败 | 登录时账号不存在或口令错误 |
| `10002` | 账号已锁定 | 连续失败超限，账号被临时锁定 | 连续 5 次口令错误后 15 分钟内再次登录；`message` 含剩余分钟数 |
| `10003` | 账号已停用 | 账号状态为停用 | 被机构管理员停用的账号登录 |
| `10004` | 访问令牌已过期 | `access_token` 超过有效期 | 使用过期 Token 调用接口；客户端应走刷新流程 |
| `10005` | 令牌无效 | Token 签名校验失败或格式错误 | 篡改 Token、伪造身份字段 |
| `10006` | 刷新令牌已过期 | `refresh_token` 超过有效期 | 需重新登录 |
| `10007` | 验证码错误或已过期 | 患者手机号验证码校验失败 | 验证码错误、超过 5 分钟有效期 |
| `10008` | 手机号格式不正确 | 入参手机号不合法 | 挂号前实名校验 |
| `10009` | 角色不允许访问该端 | 角色与接口所属端不匹配 | 医生账号登录管理后台 |
| `10010` | 原口令不正确 | 修改口令时原口令校验失败 | 修改口令接口 |

**会话与分诊（20xxx）**

| code | message | 说明 | 触发场景 |
|---|---|---|---|
| `20001` | 会话不存在 | 会话标识无效或不属于当前身份 | 访问他人会话 |
| `20002` | 会话已结束 | 会话处于终态，不可继续对话 | 向已关闭会话发送消息 |
| `20003` | 会话已过期 | 超过恢复有效期，需新建会话 | 超过 24 小时尝试恢复 |
| `20004` | 会话已完成预问诊 | 已产出分诊结论，不可再追加问诊 | 重复发起问诊 |
| `20005` | 该会话已存在分诊结论 | 唯一性冲突 | 重复触发分诊 |
| `20006` | 分诊结论尚未生成 | 结论仍在校验或生成中 | 过早查询结果 |
| `20007` | 追问轮次已达上限 | 超过系统配置的追问轮次上限 | 继续追问 |
| `20008` | 该会话已被其他医生接管 | 接管并发冲突 | 两名医生同时接管 |
| `20009` | 会话不在待接管状态 | 状态不允许该操作 | 对接管中的会话再次接管 |
| `20010` | 修正理由不满足要求 | 理由少于 10 字或与修正无关 | 提交修正接口 |
| `20011` | 修正前后科室相同 | 未发生实际修正 | 提交修正接口 |
| `20012` | 患者未授权调阅既往病历 | 缺少有效授权记录 | 未授权时调用病历查阅 |
| `20013` | 危重症已触发急诊通道 | 会话已进入急诊流程，不可继续问诊 | 危重症命中后继续发消息 |
| `20014` | 消息内容为空或超长 | 消息长度为 0 或超过 500 字 | 发送消息接口 |
| `20015` | 不支持的消息类型 | `msg_type` 取值不在允许范围 | 发送消息接口 |

**挂号与号源（30xxx）**

| code | message | 说明 | 触发场景 |
|---|---|---|---|
| `30001` | 号源不存在或已过期 | 号源标识无效或已过期 | 挂号接口 |
| `30002` | 号源已被占用 | 并发占用冲突 | 提交挂号时该号源已被他人预约 |
| `30003` | 该科室近期无号源 | 查询范围内无可用号源 | 号源查询接口 |
| `30004` | 已存在相同预约 | 幂等命中，返回原预约记录 | 重复提交同一幂等键 |
| `30005` | 预约不存在 | 预约标识无效 | 取消预约接口 |
| `30006` | 该预约不可取消 | 状态或时限不允许取消 | 取消已完成的预约 |
| `30007` | 号源查询服务超时 | 外部系统超时 | 号源查询接口，可重试 |

**知识库与检索（40xxx）**

| code | message | 说明 | 触发场景 |
|---|---|---|---|
| `40001` | 知识库条目不存在 | 条目标识无效或已停用 | 条目详情、修改接口 |
| `40002` | 条目标识已存在 | `entry_code` 唯一性冲突 | 新增条目 |
| `40003` | 条目标识不存在 | 引用的编码或科室不存在 | 新增/修改条目时的引用完整性校验 |
| `40004` | 该条目已被引用，不可停用 | 被其他知识引用 | 停用被引用的知识 |
| `40005` | 条目校验失败 | 必填项缺失或格式不符 | 新增/修改条目 |
| `40006` | 存在未完成的入库任务 | 并发冲突，不可重复触发 | 触发入库接口 |
| `40007` | 入库任务不存在 | 任务编号无效 | 任务详情接口 |
| `40008` | 入库任务不可中止 | 任务已处于终态 | 中止任务接口 |
| `40009` | 检索查询为空 | 查询文本为空 | 检索验证接口 |
| `40010` | 黄金查询用例不存在 | 用例标识无效 | 回归执行接口 |
| `40011` | 无启用中的黄金查询用例 | 无法执行回归 | 回归执行接口 |
| `40012` | 知识库检索超时 | 检索耗时超过阈值 | 检索接口 |
| `40013` | 发布快照生成失败 | 快照写入异常 | 发布接口 |
| `40014` | 版本标识已存在 | `version_tag` 唯一性冲突 | 发布接口 |

**机构与配置（50xxx）**

| 代码 | message | 说明 | 触发场景 |
|---|---|---|---|
| `50001` | 科室不存在 | 科室编码无效 | 科室相关接口 |
| `50002` | 科室编码已存在 | 唯一性冲突 | 新增科室 |
| `50003` | 该科室已被引用，不可停用 | 存在引用该科室的知识条目 | 停用科室 |
| `50004` | 用户不存在 | 用户标识无效 | 用户相关接口 |
| `50005` | 登录账号已存在 | 唯一性冲突 | 创建用户 |
| `50006` | 该医生存在未完成接诊 | 存在进行中的会话 | 停用医生账号 |
| `50007` | 配置项不存在 | 配置键无效 | 修改配置 |
| `50008` | 配置项取值非法 | 超出允许范围 | 修改配置 |
| `50009` | 模型配置不存在 | 配置标识无效 | 模型配置接口 |
| `50010` | 该类型已有默认配置 | 默认配置唯一性冲突 | 设置默认模型配置 |
| `50011` | 机构信息不存在 | 租户无有效机构信息 | 机构信息接口 |

**外部依赖与系统（60xxx）**

| code | message | 说明 | 触发场景 |
|---|---|---|---|
| `60001` | 病历系统不可用 | EMR 调用失败 | 既往病历查阅 |
| `60002` | 病历调阅失败 | EMR 返回异常 | 既往病历查阅 |
| `60003` | 语音识别服务不可用 | ASR 能力不可用 | 语音输入接口 |
| `60004` | 内容生成服务不可用 | 推理服务不可用且未降级 | 问诊接口 |
| `60005` | 向量化服务不可用 | 向量化后端不可用 | 检索接口、入库任务 |
| `60006` | 精排服务不可用 | 精排后端不可用（**触发降级，不阻断流程**） | 检索接口 |
| `60007` | 数据出域被拦截 | 守卫拒绝院外地址 | 涉及患者数据的能力调用 |
| `60008` | 审计写入失败 | 审计无法写入，业务被拒绝 | 任意写操作 |
| `60009` | 文件格式不支持 | 上传文件类型不在白名单 | 文件上传 |
| `60010` | 文件大小超限 | 上传文件超过限制 | 文件上传 |
| `60011` | 系统处于降级状态 | 主链路降级 | 依赖降级的接口 |

**错误码的三条设计约定**

| 约定 | 说明 |
|---|---|
| `404` 不区分"不存在"与"无权访问" | 避免通过错误码探测其他租户的资源是否存在 |
| 业务错误 HTTP 状态码为 `200` | 业务规则失败不是协议层错误，客户端只需判断 `code` 字段 |
| 错误 `message` 不含内部信息 | 不返回堆栈、SQL、内网地址；排查依赖 `X-Trace-ID` |

---

## 5. 认证与授权

### 5.1 JWT 结构

**访问令牌载荷示例**

```json
{
  "sub": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
  "tenant_id": "00000000000000000000000000000001",
  "org_id": "00000000000000000000000000000001",
  "role": "DOCTOR",
  "dept_code": "DIG",
  "title": "副主任医师",
  "identity_type": "STAFF",
  "token_type": "access",
  "jti": "c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8",
  "iat": 1760552621,
  "exp": 1760554421,
  "iss": "medical-guidance",
  "aud": "medical-guidance-api"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `sub` | string | 主体标识。医生与管理员为 `mg_user.id`；患者为 `mg_patient.id` |
| `tenant_id` | string | **租户标识。所有接口的租户过滤来源，客户端不可传** |
| `org_id` | string | 机构标识，当前与 `tenant_id` 相同（一机构一租户） |
| `role` | string | 角色：`PATIENT` / `DOCTOR` / `KB_ADMIN` / `ORG_ADMIN` |
| `dept_code` | string | 医生所属科室，非医生角色为 `null` |
| `title` | string | 医师职称，用于评测样本采纳判定；非医生角色为 `null` |
| `identity_type` | string | 身份类型：`STAFF` 院内用户 / `PATIENT` 患者 / `ANONYMOUS` 匿名会话 |
| `token_type` | string | 令牌类型：`access` / `refresh`。**刷新接口会校验此字段** |
| `jti` | string | 令牌唯一标识，用于登出时的黑名单校验 |
| `iat` / `exp` | integer | 签发时间与过期时间（Unix 时间戳，秒） |
| `iss` | string | 签发者，固定 `medical-guidance` |
| `aud` | string | 受众，固定 `medical-guidance-api` |

**患者匿名会话令牌载荷示例**

```json
{
  "sub": "d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9",
  "tenant_id": "00000000000000000000000000000001",
  "role": "PATIENT",
  "identity_type": "ANONYMOUS",
  "device_id": "dev_7f3a9b2c1d4e",
  "scope": ["session:create", "session:read", "session:write"],
  "token_type": "access",
  "jti": "e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0",
  "iat": 1760552621,
  "exp": 1760554421,
  "iss": "medical-guidance",
  "aud": "medical-guidance-api"
}
```

| 附加字段 | 说明 |
|---|---|
| `device_id` | 设备标识，用于匿名会话的归属校验与恢复 |
| `scope` | 匿名会话允许的操作范围。**挂号等需实名的操作不在此范围内** |

**令牌安全约定**

| 约定 | 说明 |
|---|---|
| 签名算法 | `HS256`。密钥来自环境变量，长度不少于 32 字节，不进版本控制 |
| 不存放敏感数据 | 载荷只放标识与角色，**不放姓名、手机号、患者标识哈希** |
| 身份不接受客户端指定 | `tenant_id` / `role` / `sub` 只来自令牌载荷，**请求参数中的同名字段一律忽略** |
| 篡改检测 | 载荷被修改后签名校验失败，返回 `10005` |
| 登出失效 | 登出时将 `jti` 写入缓存黑名单，有效期为令牌剩余有效期 |

### 5.2 Token 有效期与刷新

| 令牌 | 有效期 | 存储位置（客户端） | 说明 |
|---|---|---|---|
| `access_token` | **2 小时** | 内存或会话存储 | 短期凭证，过期后走刷新流程 |
| `refresh_token` | 院内用户 **8 小时** / 患者 **7 天** | 安全存储 | 院内用户与工作时段对齐；患者端考虑使用连续性 |
| 患者匿名令牌 | **30 分钟**，可静默续期 | 内存 | 符合需求 `F01`；续期失败时保留本地对话记录 |

**刷新流程**

```
客户端                        服务端
  │                             │
  │ ① 调用受保护接口            │
  ├────────────────────────────→│
  │←─ code=10004 令牌已过期 ─────┤
  │                             │
  │ ② POST /api/v1/auth/refresh │
  │    Body: refresh_token      │
  ├────────────────────────────→│
  │                             │ 校验 refresh_token：
  │                             │  · 签名有效
  │                             │  · token_type = 'refresh'
  │                             │  · 未过期、未在黑名单
  │                             │
  │←─ 新的 access_token ─────────┤
  │   （refresh_token 不变）      │
  │                             │
  │ ③ 用新令牌重放原请求          │
  ├────────────────────────────→│
```

| 规则 | 说明 |
|---|---|
| `refresh_token` 不轮换 | 刷新时不签发新的 `refresh_token`（有效期不变），避免并发刷新导致失效 |
| 刷新失败需重新登录 | 返回 `10006`，客户端清除本地凭证并跳转登录 |
| 并发刷新处理 | 多个请求同时触发刷新时，服务端对同一 `refresh_token` 返回相同的新令牌（幂等） |
| 患者匿名续期 | 由服务端在会话有效期内自动延长，客户端无需显式调用刷新接口 |

### 5.3 角色权限矩阵

**图例**：`C` 创建 / `R` 读 / `U` 修改 / `D` 停用或删除 / `—` 无权限

| 资源 | 患者 PATIENT | 医生 DOCTOR | 知识库管理员 KB_ADMIN | 机构管理员 ORG_ADMIN |
|---|:--:|:--:|:--:|:--:|
| 预问诊会话（本人） | C R U | — | — | — |
| 预问诊会话（接诊患者） | — | R U | — | R |
| 会话消息 | C R | C R | — | R |
| 分诊结论 | R | R U | — | R |
| 鉴别诊断候选与依据 | — | R | — | R |
| SOAP 预问诊病历 | R（**患者视图，无评估段**） | R | — | R |
| 既往病历文书 | — | R | — | R |
| 患者授权记录 | C R | R | — | R |
| 号源查询 | R | R | — | R |
| 挂号记录 | C R D | R | — | R |
| 待接管队列 | — | R U | — | R |
| 分诊修正记录 | — | C R | — | R |
| 知识库条目 | — | — | C R U D | R |
| 知识库变更记录 | — | — | R | R |
| 知识库发布 | — | — | C R | R |
| 知识库入库任务 | — | — | C R U | R |
| 黄金查询集 | — | — | C R U D | R |
| 检索验证台 | — | — | R | R |
| 回归执行记录 | — | — | C R | R |
| 科室配置 | — | R | R | C R U D |
| 用户账号 | — | — | — | C R U D |
| 系统配置 | — | — | R | R U |
| 模型服务配置 | — | — | — | C R U D |
| 机构信息 | — | — | — | R U |
| 审计记录 | — | — | — | R |
| 文件上传 | C（仅图片） | C | C | C |

**权限判定的三层叠加**（与架构文档 §8.1 一致）

```
① 角色权限  →  接口层依赖注入，判断"该角色能否访问该接口"
② 租户隔离  →  数据访问层强制注入 tenant_id，客户端不可传
③ 行级权限  →  服务层校验业务关系：
                · 医生仅可访问自己接诊的患者（R07）
                · 患者仅可访问本人的会话
```

**三个容易混淆的权限边界**

| 边界 | 规则 |
|---|---|
| 医生能否看他人接诊的患者 | **不能**。返回 `403`，并写审计日志 |
| 知识库管理员能否查看病历 | **不能**。知识库管理员只操作知识，不接触患者数据 |
| 机构管理员能否修改知识库 | **不能**。机构管理员管人与配置，知识库内容归知识库管理员 |

---

## 6. 多租户隔离

| 项 | 规范 |
|---|---|
| 租户标识来源 | **仅来自 JWT 载荷中的 `tenant_id`**。请求体、查询参数、请求头中的同名字段一律忽略 |
| 过滤位置 | 数据访问层统一注入，业务代码不手写租户条件 |
| 缓存键 | 以 `tenant_id` 为前缀，避免跨租户命中 |
| 向量检索 | 强制附加租户过滤，不提供"不过滤"的调用方式 |
| 跨租户访问 | 返回 `404 资源不存在`，**不返回 `403`**——避免通过错误码探测其他租户的资源是否存在 |
| 审计 | 所有敏感操作记录 `tenant_id` |

**客户端不需要传租户标识**

```json
// 正确：租户来自 JWT
GET /api/v1/doctor/encounters
Authorization: Bearer <access_token>

// 错误：服务端会忽略请求体中的 tenant_id，并以 JWT 中的为准
POST /api/v1/patient/sessions
{
  "tenant_id": "00000000000000000000000000000002",
  "chief_complaint": "肚子疼"
}
```

**例外说明**

| 例外 | 说明 |
|---|---|
| 版本列表中的全局共享数据 | 知识库类型为编码对照的条目为全局共享，检索时按"当前租户 + 全局"合并返回，接口层表现为普通列表 |
| 机构信息接口 | 只返回当前租户自身的机构信息，不接受查询其他租户 |

---

## 7. 分页规范

**请求参数**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `page` | integer | 否 | `1` | 页码，从 1 开始。小于 1 时按 1 处理 |
| `size` | integer | 否 | `20` | 每页条数。取值范围 1~100，超过 100 时按 100 处理 |

**响应字段**：见 3.2 节的统一分页结构。

**排序约定**

| 约定 | 说明 |
|---|---|
| 默认排序 | 按创建时间倒序（`create_time DESC`） |
| 显式排序 | 通过 `sort_by` 与 `sort_order` 参数指定（仅部分接口支持，见各接口定义） |
| `sort_by` 白名单 | 每个接口在定义中给出允许排序的字段，**不接受任意字段**（防止对未索引字段排序导致全表扫描） |
| `sort_order` | `asc` / `desc`，默认 `desc` |
| 稳定排序 | 分页时会附加主键作为最终排序键，避免翻页时出现重复或遗漏 |

**分页实现约定**

| 约定 | 说明 |
|---|---|
| 深分页 | `page * size` 超过 10000 时，服务端返回 `400`，提示改用时间范围筛选 |
| `total` 的准确性 | 使用精确计数。若后续数据量增大影响性能，可改为估算并在文档中标注 |
| 越界页 | 请求页码超过总页数时返回空 `items` 与正确的 `total`，**不返回错误** |

---

## 8. 幂等规范

**适用接口**

| 接口类型 | 是否需要幂等键 | 说明 |
|---|---|---|
| 创建会话 | 建议 | 防止用户重复点击创建多个会话 |
| 发送消息 | **不建议** | 消息有顺序语义，重复发送应被视为两次发言 |
| 挂号 | **强烈建议** | 直接涉及号源占用 |
| 确认 / 修正分诊 | 建议 | 防止重复写入修正记录 |
| 触发知识库入库 | **强烈建议** | 重复触发会产生并发任务冲突 |
| 知识库发布 | 建议 | 防止产生重复版本 |
| 停用 / 启用类接口 | 建议 | 本身已是幂等操作，键用于防止重复的审计记录 |
| 查询类接口 | 不需要 | `GET` 天然幂等 |

**使用方式**

```http
POST /api/v1/patient/appointments HTTP/1.1
Host: medical-guidance.example.com
Authorization: Bearer <access_token>
Content-Type: application/json
Idempotency-Key: f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6
```

**行为约定**

| 项 | 规则 |
|---|---|
| 键格式 | 32 位无连字符字符串。格式不符时返回 `400` |
| 缓存时长 | **24 小时**。超时后同一键会被视为新请求 |
| 缓存范围 | 按 `tenant_id + 接口路径 + 幂等键` 三元组缓存，避免不同接口的键冲突 |
| 重复请求 | **返回首次请求的完整响应**（含 `code`、`data`、`message`），HTTP 状态码为 `200` |
| 首次请求处理中 | 返回 `409`，`message` 为"请求正在处理中，请勿重复提交" |
| 首次请求失败 | 失败结果**同样被缓存**。客户端需用新的幂等键重试（这避免"失败被无限重试"） |
| 未携带该请求头 | 不做幂等保证，按普通请求处理 |

**幂等键的生成建议**

| 场景 | 建议 |
|---|---|
| 表单提交 | 进入表单页时生成一次，整个填写过程复用同一键 |
| 重试 | **复用原键**（这才是幂等的意义）；若前次失败且已缓存失败结果，则改用新键 |
| 不要用随机数 | 每次请求生成新随机数等于没有幂等 |

---

## 9. 限流规范

**限流维度**

```
客户端标识（未认证：IP + User-Agent 指纹）
        │
      或  ──→  限流计数器（缓存）
        │
账号标识（已认证：用户标识）
```

**默认阈值**

| 接口类别 | 阈值 | 维度 | 说明 |
|---|---|---|---|
| 通用接口（默认） | **600 次 / 分钟** | 客户端标识 | 覆盖绝大多数查询类接口 |
| 任务创建类 | **6 次 / 分钟** | 账号标识 | 触发知识库入库、执行回归验证 |
| 登录接口 | **10 次 / 分钟** | 客户端标识 | 防止暴力尝试 |
| 验证码发送 | **5 次 / 分钟，单日 20 次** | 手机号 | 防止短信轰炸 |
| 消息发送 | **60 次 / 分钟** | 会话 | 防止单会话刷消息拖垮推理服务 |
| 检索验证台 | **30 次 / 分钟** | 账号标识 | 单次检索开销较大 |
| 文件上传 | **20 次 / 分钟** | 账号标识 | — |
| 健康检查 | **不限流** | — | 探针必须可访问，否则会误判服务不可用 |

**超限响应**

```json
{
  "code": 429,
  "data": {
    "limit": 600,
    "remaining": 0,
    "reset_at": 1760552680,
    "retry_after": 37
  },
  "message": "请求过于频繁，请在 37 秒后重试"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `limit` | integer | 当前接口的限流阈值 |
| `remaining` | integer | 当前窗口剩余可用次数 |
| `reset_at` | integer | 窗口重置时间（Unix 时间戳，秒） |
| `retry_after` | integer | 建议重试等待秒数 |

**响应头**（所有响应都带，不限于超限时）

| Header | 说明 |
|---|---|
| `X-RateLimit-Limit` | 限流阈值 |
| `X-RateLimit-Remaining` | 剩余可用次数 |
| `X-RateLimit-Reset` | 窗口重置时间（Unix 时间戳，秒） |

**限流与业务优先级的处理**

| 场景 | 规则 |
|---|---|
| 危重症相关请求 | **不受限流限制**。安全相关请求优先级最高 |
| 急诊引导推送 | 不受限流限制 |
| 降级状态下的请求 | 保持限流，避免降级期间过载 |

---

## 10. 文件上传规范

**支持的文件类型**

| 类别 | 允许的扩展名 | 单文件上限 | 说明 |
|---|---|---|---|
| 图片 | `.jpg` `.jpeg` `.png` `.webp` | **5 MB** | 患者上传的检查报告照片、医生端的示意图 |
| 文档 | **本项目不支持** | — | 病历文书由病历系统同步，不走上传通道 |
| 音频 | `.wav` `.mp3` `.m4a` | **10 MB** | 语音输入；超过 60 秒会被截断（需求 `F03`） |

**请求格式**

```http
POST /api/v1/files/upload HTTP/1.1
Host: medical-guidance.example.com
Authorization: Bearer <access_token>
Content-Type: multipart/form-data; boundary=----Boundary7MA4YWxkTrZu0gW
```

```
------Boundary7MA4YWxkTrZu0gW
Content-Disposition: form-data; name="file"; filename="report.jpg"
Content-Type: image/jpeg

<二进制内容>
------Boundary7MA4YWxkTrZu0gW
Content-Disposition: form-data; name="biz_type"

EMR_ATTACHMENT
------Boundary7MA4YWxkTrZu0gW
```

**表单字段**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `file` | file | 是 | 文件内容 |
| `biz_type` | string | 是 | 业务类型：`EMR_ATTACHMENT` 病历附件 / `VOICE_INPUT` 语音输入 / `OTHER` 其他 |
| `session_id` | string | 否 | 关联会话标识，语音输入时需要 |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "file_id": "a9b8c7d6e5f4a3b2c1d0e9f8a7b6c5d4",
    "file_name": "report.jpg",
    "file_size": 1048576,
    "content_type": "image/jpeg",
    "biz_type": "EMR_ATTACHMENT",
    "url": "/api/v1/files/a9b8c7d6e5f4a3b2c1d0e9f8a7b6c5d4",
    "uploaded_time": "2026-10-15T19:23:41+08:00"
  },
  "message": "成功"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `file_id` | string | 文件标识，后续接口通过它引用文件 |
| `file_name` | string | 原始文件名 |
| `file_size` | integer | 文件大小（字节） |
| `content_type` | string | MIME 类型，**由服务端探测，不信任客户端声明** |
| `biz_type` | string | 业务类型 |
| `url` | string | 文件访问地址 |
| `uploaded_time` | string | 上传时间 |

**服务端处理规则**

| 规则 | 说明 |
|---|---|
| 类型校验 | **以文件魔数（magic number）为准**，不信任 `Content-Type` 与扩展名 |
| 文件名处理 | 服务端重命名为 `file_id` + 原扩展名，**不使用客户端提供的文件名做存储路径**（防路径穿越） |
| 图片二次处理 | 去除 EXIF 信息（含 GPS 定位等个人标识） |
| 存储位置 | 对象存储，按 `tenant_id` 分目录前缀 |
| 访问控制 | 访问文件时校验归属租户与会话权限 |
| 病毒扫描 | 本项目不涉及（院内网环境，无外部文件来源） |

---

## 11. WebSocket 协议

系统提供**两条** WebSocket 通道，用途不同。

| 通道 | 路径 | 用途 | 消息方向 | 需求 |
|---|---|---|---|---|
| 对话流式 | `/api/v1/ws/sessions/{session_id}` | 预问诊对话的流式输出与追问推送 | 双向 | `F05`、`F34`、`F40`、`F50` |
| 任务进度 | `/api/v1/ws/tasks/{task_id}` | 知识库入库任务的进度推送 | 单向（服务端推） | `F29` |

### 11.1 连接与鉴权

**连接地址**

```
# 对话流式
wss://<host>/api/v1/ws/sessions/{session_id}?token=<ws_ticket>

# 任务进度
wss://<host>/api/v1/ws/tasks/{task_id}?token=<ws_ticket>
```

**鉴权方式：一次性票据（ws_ticket）**

浏览器的 WebSocket API **无法设置自定义请求头**，因此不能直接使用 `Authorization` 头。若把 `access_token` 直接放在 URL 中，会被网关、代理、浏览器历史的日志记录，带来泄露风险。

因此采用两段式：**先用 REST 接口换取一次性短效票据，再用票据建立连接**。

```
客户端                          服务端
  │                               │
  │ ① POST /api/v1/ws/ticket      │
  │    Authorization: Bearer ...  │
  ├──────────────────────────────→│
  │                               │ 生成一次性票据：
  │                               │  · 有效期 60 秒
  │                               │  · 绑定 tenant_id / sub / 目标资源
  │                               │  · 使用一次后立即失效
  │←─ ws_ticket ───────────────────┤
  │                               │
  │ ② wss://...?token=<ws_ticket> │
  ├──────────────────────────────→│
  │                               │ 校验票据并建立连接
  │←─ {"type":"connected"} ────────┤
```

**票据特性**

| 特性 | 说明 |
|---|---|
| 有效期 | **60 秒**，超时未使用即失效 |
| 使用次数 | **一次性**。连接建立后立即作废 |
| 绑定关系 | 绑定 `tenant_id`、主体标识与目标资源（`session_id` 或 `task_id`）。**用于其他资源即拒绝** |
| 失效响应 | 票据无效或过期时，连接被拒绝，关闭码 `4001` |

**连接握手响应**

| 关闭码 | 含义 |
|---|---|
| `1000` | 正常关闭 |
| `4001` | 票据无效或已过期 |
| `4003` | 无权限访问该资源（会话不属于当前身份，或医生未接诊该患者） |
| `4004` | 资源不存在 |
| `4008` | 连接数超过上限 |
| `4029` | 连接频率超限 |

**心跳**

| 项 | 规则 |
|---|---|
| 客户端心跳 | 每 **30 秒** 发送一次文本 `"ping"` |
| 服务端响应 | 立即返回 `{"type": "pong", "ts": 1760552621}` |
| 超时判定 | 服务端 **90 秒** 未收到任何消息则主动关闭（关闭码 `1000`） |

### 11.2 订阅通道

**对话流式通道**

连接建立后**自动订阅**该 `session_id` 的全部事件，无需显式订阅。一个连接对应一个会话。

**任务进度通道**

连接建立后**自动订阅**该 `task_id` 的进度事件。任务完成后服务端推送 `task_complete` 并关闭连接（关闭码 `1000`）。

**客户端可发送的消息（仅对话通道）**

| 消息类型 | 格式 | 说明 |
|---|---|---|
| 心跳 | 文本 `ping` | 保活 |
| 用户消息 | 见下方 JSON | 等价于 REST 的发送消息接口，用于减少一次请求往返 |

```json
{
  "type": "user_message",
  "seq": 5,
  "data": {
    "content": "肚子疼三天了，还有点拉肚子",
    "msg_type": "TEXT"
  }
}
```

**使用建议**：文本消息优先走 WebSocket（省一次往返，且流式响应直接在当前连接返回）；需要幂等保证或携带附件时走 REST 接口。

### 11.3 事件格式

**统一事件结构**

| 字段 | 类型 | 说明 |
|---|---|---|
| `type` | string | 事件类型 |
| `seq` | integer | 事件序号，连接内从 1 递增。**用于断线重连补发** |
| `ts` | integer | 事件时间（Unix 时间戳，秒） |
| `data` | object | 事件数据，结构随 `type` 不同 |

---

#### `connected` 连接建立

```json
{
  "type": "connected",
  "seq": 1,
  "ts": 1760552621,
  "data": {
    "session_id": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
    "session_status": "IN_PROGRESS",
    "server_time": "2026-10-15T19:23:41+08:00",
    "heartbeat_interval": 30
  }
}
```

#### `node_start` 节点开始

```json
{
  "type": "node_start",
  "seq": 2,
  "ts": 1760552622,
  "data": {
    "node": "SAFETY_CHECK",
    "node_label": "危重症识别",
    "message": "正在评估症状紧急程度"
  }
}
```

| `data` 字段 | 类型 | 说明 |
|---|---|---|
| `node` | string | 节点标识：`SAFETY_CHECK` / `HISTORY_INJECT` / `ENTITY_EXTRACT` / `SUFFICIENCY_CHECK` / `INQUIRY` / `RETRIEVAL` / `MDT_COUNCIL` / `TRIAGE_DECIDE` / `EMR_GENERATE` |
| `node_label` | string | 节点中文名，可直接展示给用户 |
| `message` | string | 面向患者的提示文案 |

#### `node_delta` 流式内容增量

```json
{
  "type": "node_delta",
  "seq": 3,
  "ts": 1760552623,
  "data": {
    "node": "INQUIRY",
    "delta": "请问",
    "accumulated": "请问"
  }
}
```

| `data` 字段 | 类型 | 说明 |
|---|---|---|
| `node` | string | 产生该增量的节点 |
| `delta` | string | 本次新增的文本片段 |
| `accumulated` | string | 该消息截至目前的完整文本。**客户端可直接用它替换渲染，不必自行拼接** |

#### `node_complete` 节点完成

```json
{
  "type": "node_complete",
  "seq": 24,
  "ts": 1760552624,
  "data": {
    "node": "INQUIRY",
    "duration_ms": 1820,
    "output": {
      "message_id": "f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2",
      "content": "请问疼痛是持续性的还是阵发性的？",
      "msg_type": "TEXT",
      "inquiry_rounds": 2
    }
  }
}
```

| `data` 字段 | 类型 | 说明 |
|---|---|---|
| `node` | string | 完成节点标识 |
| `duration_ms` | integer | 该节点耗时（毫秒） |
| `output` | object | 节点产出，结构随节点不同 |

**`RETRIEVAL` 节点的 `output` 示例**

```json
{
  "node": "RETRIEVAL",
  "duration_ms": 286,
  "output": {
    "retrieval_mode": "HYBRID",
    "candidate_count": 3,
    "top_depts": [
      {"dept_code": "DIG", "dept_name": "消化内科", "score": 0.8731},
      {"dept_code": "GEN_SURG", "dept_name": "普通外科", "score": 0.6204}
    ]
  }
}
```

**`MDT_COUNCIL` 节点的 `output` 示例**

```json
{
  "node": "MDT_COUNCIL",
  "duration_ms": 8420,
  "output": {
    "candidate_depts": ["DIG", "GEN_SURG", "GYN"],
    "opinion_count": 3,
    "missing_count": 0,
    "divergence": true,
    "consensus_dept": "DIG",
    "consensus_confidence": 0.7102
  }
}
```

#### `node_error` 节点错误

```json
{
  "type": "node_error",
  "seq": 25,
  "ts": 1760552625,
  "data": {
    "node": "RETRIEVAL",
    "code": 60006,
    "message": "精排服务不可用，已降级为融合结果",
    "degraded": true,
    "recoverable": true
  }
}
```

| `data` 字段 | 类型 | 说明 |
|---|---|---|
| `node` | string | 出错节点 |
| `code` | integer | 错误码，取值见第 4 章 |
| `message` | string | 面向用户的错误说明 |
| `degraded` | boolean | **是否已自动降级**。为 `true` 时流程继续，客户端应提示"结果可能略有差异" |
| `recoverable` | boolean | 是否可通过重试恢复 |

**关键区分**：`degraded=true` 的 `node_error` **不是流程终止**，而是降级通知；只有 `degraded=false` 才会导致流程中断。

#### `emergency` 危重症告警

```json
{
  "type": "emergency",
  "seq": 8,
  "ts": 1760552626,
  "data": {
    "triggered": true,
    "matched_rule": "胸痛伴出汗及后背放射痛",
    "matched_layer": 1,
    "action": "GUIDE_TO_EMERGENCY",
    "message": "您的症状需要立即就医，请立即前往就近医院急诊科",
    "emergency_phone": "120"
  }
}
```

| `data` 字段 | 类型 | 说明 |
|---|---|---|
| `triggered` | boolean | 恒为 `true` |
| `matched_rule` | string | 命中的红线规则描述 |
| `matched_layer` | integer | 命中的层级（1 规则 / 2 小模型 / 3 大模型） |
| `action` | string | 固定 `GUIDE_TO_EMERGENCY` |
| `message` | string | 展示给患者的文案 |
| `emergency_phone` | string | 急救电话 |

**收到该事件后**：客户端应全屏展示急诊引导，阻断继续对话，且**不再发送用户消息**。

#### `task_complete` 任务完成

**对话通道的任务完成事件**

```json
{
  "type": "task_complete",
  "seq": 31,
  "ts": 1760552628,
  "data": {
    "session_id": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
    "session_status": "FINISHED",
    "result": {
      "route": "DIRECT",
      "dept_code": "DIG",
      "dept_name": "消化内科",
      "confidence": 0.8731,
      "inquiry_rounds": 3,
      "triage_result_id": "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7",
      "emr_record_id": "c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8"
    },
    "suggest_next": ["FETCH_TRIAGE_RESULT", "FETCH_EMR", "QUERY_SLOTS"]
  }
}
```

| `data` 字段 | 类型 | 说明 |
|---|---|---|
| `session_status` | string | 会话终态 |
| `result.route` | string | 路由去向 |
| `result.triage_result_id` | string | 分诊结论标识，可用它调用结果接口 |
| `result.emr_record_id` | string | 病历标识 |
| `suggest_next` | array | 建议客户端接下来调用的动作 |

**任务通道的完成事件**

```json
{
  "type": "task_complete",
  "seq": 42,
  "ts": 1760552630,
  "data": {
    "task_id": "d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9",
    "task_no": "ING20261015001",
    "status": "SUCCESS",
    "progress": 100,
    "statistics": {
      "total_count": 512,
      "added_count": 38,
      "updated_count": 12,
      "disabled_count": 3,
      "failed_count": 0
    },
    "duration_ms": 184320
  }
}
```

**任务通道的其他事件**

```json
{
  "type": "task_progress",
  "seq": 15,
  "ts": 1760552625,
  "data": {
    "task_id": "d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9",
    "status": "RUNNING",
    "stage": "EMBED",
    "stage_label": "向量化",
    "progress": 45,
    "message": "正在向量化第 231 / 512 条"
  }
}
```

```json
{
  "type": "task_error",
  "seq": 22,
  "ts": 1760552626,
  "data": {
    "task_id": "d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9",
    "status": "FAILED",
    "code": 40005,
    "message": "存在 2 条数据校验失败，已中止整批入库",
    "failed_entries": [
      {"entry_code": "DEPT-DIG-018", "reason": "dept_code 不存在：DIGEST"},
      {"entry_code": "DRUG-0007", "reason": "缺少必填项 contraindication_type"}
    ]
  }
}
```

### 11.4 断线重连与事件补发

**重连流程**

```
客户端                                服务端
  │                                     │
  │ ① 检测到连接断开                     │
  │    记录最后收到的 seq = 24           │
  │                                     │
  │ ② 等待退避后重连                     │
  │    （1s → 2s → 4s → 8s，上限 30s）    │
  │                                     │
  │ ③ POST /api/v1/ws/ticket            │
  ├────────────────────────────────────→│
  │←─ 新票据 ────────────────────────────┤
  │                                     │
  │ ④ wss://...?token=<ticket>          │
  │    &last_seq=24                     │
  ├────────────────────────────────────→│
  │                                     │ 从会话事件缓冲中
  │                                     │ 取 seq > 24 的事件
  │←─ 补发的事件（seq 25, 26, 27…）───────┤
  │←─ {"type":"connected"} ──────────────┤
  │                                     │
  │ ⑤ 继续正常接收                       │
```

**补发规则**

| 项 | 规则 |
|---|---|
| 事件缓冲 | 服务端为每个通道保留最近 **100 条**事件，保留期 **5 分钟** |
| 补发范围 | `seq > last_seq` 且仍在缓冲期内的事件 |
| 补发顺序 | 严格按 `seq` 升序 |
| 超出缓冲 | 断开超过 5 分钟或缺失超过 100 条时，服务端推送 `resync_required` 事件，客户端需重新拉取全量状态 |

```json
{
  "type": "resync_required",
  "seq": 0,
  "ts": 1760552700,
  "data": {
    "reason": "EVENT_BUFFER_EXPIRED",
    "message": "断开时间过长，请重新拉取会话状态",
    "suggest_next": ["FETCH_SESSION", "FETCH_MESSAGES"]
  }
}
```

**客户端处理约定**

| 场景 | 处理 |
|---|---|
| 收到重复 `seq` | 丢弃（幂等处理） |
| `seq` 出现跳跃 | 用 `last_seq` 参数重连补发 |
| 收到 `resync_required` | 通过 REST 拉取会话与消息全量，重建 UI |
| 收到 `session_status` 为终态 | 主动关闭连接，不再重连 |
| 危重症告警后断开 | 重连时仍会收到 `emergency` 事件（它在缓冲期内，且必须送达） |

**为什么需要序号补发**：移动端网络不稳定、患者切后台会导致连接中断。若不做补发，患者回来后可能缺失追问内容，表现为"AI 的问题我没看到，但它在等我的回答"——这是会直接导致问诊中断的体验问题。

---

## 12. 接口详细设计

本章按模块列出全部接口。共 **12 个模块、65 个接口**。每个接口标注对应的功能需求编号。

### 12.1 认证与用户

#### 12.1.1 患者匿名会话创建

**接口路径**：`POST /api/v1/auth/patient/session`
**功能说明**：为未登录患者创建匿名会话并签发令牌，不采集姓名、身份证等身份信息（对应 `F01`、`R10`）
**权限要求**：**无需认证**（公开接口）

**请求头**

| Header | 必填 | 说明 |
|---|---|---|
| `Content-Type` | 是 | `application/json` |
| `X-Request-ID` | 否 | 客户端请求标识 |

**路径参数**：无

**查询参数**：无

**请求体**

```json
{
  "device_id": "dev_7f3a9b2c1d4e",
  "client_type": "H5",
  "channel": "WECHAT_MP"
}
```

**请求体字段说明**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `device_id` | string | 否 | 客户端生成的设备标识。未传时服务端生成并返回 |
| `client_type` | string | 否 | 客户端类型：`H5` / `MINIPROGRAM` / `APP`，默认 `H5` |
| `channel` | string | 否 | 进入渠道：`WECHAT_MP` / `GUIDE_MACHINE` / `SMS_LINK` / `DIRECT` |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkNGU1ZjZhN2I4YzlkMGUxZjJhM2I0YzVkNiIsInRlbmFudF9pZCI6IjAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAxIiwicm9sZSI6IlBBVElFTlQiLCJpZGVudGl0eV90eXBlIjoiQU5PTllNT1VTIn0.7xQ8mZ3nKp2vYwL9cT4bR6sD1fH5jN0gA3eU8iO2pXk",
    "token_type": "Bearer",
    "expires_in": 1800,
    "patient_id": "d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9",
    "device_id": "dev_7f3a9b2c1d4e",
    "scope": ["session:create", "session:read", "session:write"],
    "need_verify_before": ["APPOINTMENT", "EMR_ACCESS"]
  },
  "message": "成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `access_token` | string | 访问令牌，有效期 30 分钟 |
| `token_type` | string | 固定 `Bearer` |
| `expires_in` | integer | 有效期（秒） |
| `patient_id` | string | 患者标识（32 位无连字符），后续接口用于关联 |
| `device_id` | string | 设备标识（服务端生成或回显入参） |
| `scope` | array | 匿名身份允许的操作范围 |
| `need_verify_before` | array | 需要实名验证才能执行的操作，供客户端提前引导 |

**错误码**

| code | message | 说明 |
|---|---|---|
| `400` | 参数校验失败 | `device_id` 格式不合法（超过 128 字符） |
| `429` | 请求过于频繁 | 同一客户端 1 分钟内超过 20 次 |
| `500` | 服务器内部错误 | 会话创建失败 |

**业务规则**

- 不采集姓名、身份证号、手机号（`NFR18`）
- `device_id` 由服务端生成时，与客户端指纹共同参与患者标识计算
- 同一设备的多次匿名创建，**复用同一 `patient_id`**（保证会话可恢复）
- 匿名令牌**不可用于**挂号与病历调阅，这两项须先完成手机号验证

**幂等性**：不支持 `Idempotency-Key`。重复调用返回同一 `patient_id` 与新令牌。
**限流**：20 次 / 分钟（按客户端标识）

**示例请求**

```bash
curl -X POST "https://medical-guidance.example.com/api/v1/auth/patient/session" \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: 7f3a9b2c1d4e5f6a7b8c9d0e1f2a3b4c" \
  -d '{
    "device_id": "dev_7f3a9b2c1d4e",
    "client_type": "H5",
    "channel": "WECHAT_MP"
  }'
```

#### 12.1.2 发送手机验证码

**接口路径**：`POST /api/v1/auth/sms-code`
**功能说明**：向指定手机号发送 6 位数字验证码，用于患者实名校验（`F10`、`F44` 的前置步骤）
**权限要求**：无需认证

**请求头**

| Header | 必填 | 说明 |
|---|---|---|
| `Content-Type` | 是 | `application/json` |

**路径参数**：无 ｜ **查询参数**：无

**请求体**

```json
{
  "phone": "13800138000",
  "scene": "APPOINTMENT"
}
```

**请求体字段说明**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `phone` | string | 是 | 手机号，11 位数字，以 1 开头 |
| `scene` | string | 是 | 使用场景：`APPOINTMENT` 挂号 / `EMR_ACCESS` 病历调阅 / `LOGIN` 患者登录 |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "send_id": "e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0",
    "expires_in": 300,
    "retry_after": 60
  },
  "message": "验证码已发送"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `send_id` | string | 本次发送记录标识，校验时需回传 |
| `expires_in` | integer | 验证码有效期（秒），固定 300 |
| `retry_after` | integer | 可再次发送的等待秒数 |

**错误码**

| code | message | 说明 |
|---|---|---|
| `400` | 参数校验失败 | 手机号格式不正确 |
| `10008` | 手机号格式不正确 | 手机号不合法 |
| `429` | 请求过于频繁 | 超过 5 次 / 分钟 或 20 次 / 日 |
| `60001` | 病历系统不可用 | 短信通道不可用 |

**业务规则**

- 同一手机号 **60 秒内不可重复发送**
- 同一手机号 **单日最多 20 次**
- 验证码有效期 **5 分钟**
- 同一手机号 **连续 5 次校验失败后锁定 15 分钟**
- 响应中**不返回**验证码本身（即使在开发环境）

**幂等性**：不支持（发送动作本身受频率限制约束）
**限流**：5 次 / 分钟（按手机号），单日 20 次

**示例请求**

```bash
curl -X POST "https://medical-guidance.example.com/api/v1/auth/sms-code" \
  -H "Content-Type: application/json" \
  -d '{"phone": "13800138000", "scene": "APPOINTMENT"}'
```

#### 12.1.3 患者手机号验证

**接口路径**：`POST /api/v1/auth/patient/verify`
**功能说明**：校验验证码并将匿名身份升级为实名身份（对应 `F10` 授权前、`F44` 挂号前）
**权限要求**：需匿名患者令牌

**请求头**

| Header | 必填 | 说明 |
|---|---|---|
| `Authorization` | 是 | `Bearer <access_token>` |
| `Content-Type` | 是 | `application/json` |

**路径参数**：无 ｜ **查询参数**：无

**请求体**

```json
{
  "send_id": "e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0",
  "phone": "13800138000",
  "code": "728341",
  "scene": "APPOINTMENT"
}
```

**请求体字段说明**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `send_id` | string | 是 | 验证码发送记录标识 |
| `phone` | string | 是 | 手机号，须与发送时一致 |
| `code` | string | 是 | 6 位数字验证码 |
| `scene` | string | 是 | 场景，须与发送时一致 |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "verified": true,
    "patient_id": "d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9",
    "identity_type": "PATIENT",
    "phone_masked": "138****8000",
    "scope": ["session:create", "session:read", "session:write", "appointment:create", "emr:read"]
  },
  "message": "验证成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `verified` | boolean | 校验结果，恒为 `true`（失败走错误码） |
| `identity_type` | string | 升级后的身份类型 |
| `phone_masked` | string | 脱敏手机号，用于回显 |
| `scope` | array | **扩容后的操作范围**，新增挂号与病历调阅权限 |

**错误码**

| code | message | 说明 |
|---|---|---|
| `400` | 参数校验失败 | `code` 非 6 位数字 |
| `10007` | 验证码错误或已过期 | 验证码不符或超过 5 分钟 |
| `10008` | 手机号格式不正确 | 手机号不合法 |
| `429` | 请求过于频繁 | 校验尝试过于频繁 |
| `400` | 参数校验失败 | `phone` 与发送时不符 |

**业务规则**

- 校验成功后**原匿名令牌失效**，客户端需使用新的 `scope`
- 同一手机号在**同一租户内复用同一 `patient_id`**（避免同一患者产生多条记录）
- 手机号**不存明文**，仅存哈希与脱敏形式（`NFR18`）
- 验证码校验成功后立即作废，不可重复使用

**幂等性**：不支持
**限流**：10 次 / 分钟（按手机号）

**示例请求**

```bash
curl -X POST "https://medical-guidance.example.com/api/v1/auth/patient/verify" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{
    "send_id": "e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0",
    "phone": "13800138000",
    "code": "728341",
    "scene": "APPOINTMENT"
  }'
```

#### 12.1.4 院内用户登录

**接口路径**：`POST /api/v1/auth/staff/login`
**功能说明**：医生与管理员使用账号口令登录，返回访问令牌（对应 `F13`、`F23`）
**权限要求**：无需认证

**请求头**

| Header | 必填 | 说明 |
|---|---|---|
| `Content-Type` | 是 | `application/json` |

**路径参数**：无 ｜ **查询参数**：无

**请求体**

```json
{
  "account": "doctor001",
  "password": "Med@2026#Dig",
  "client_type": "WEB"
}
```

**请求体字段说明**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `account` | string | 是 | 登录账号，4~64 位 |
| `password` | string | 是 | 口令，8~64 位 |
| `client_type` | string | 否 | `WEB` / `ADMIN_WEB`，默认 `WEB` |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhMWIyYzNkNGU1ZjZhN2I4YzlkMGUxZjJhM2I0YzVkNiIsInJvbGUiOiJET0NUT1IifQ.k3L9mN2pQ7vXwR4tY6bD8sF1hJ5gA0cE3zU9iO2pXkQ",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhMWIyYzNkNGU1ZjZhN2I4YzlkMGUxZjJhM2I0YzVkNiIsInRva2VuX3R5cGUiOiJyZWZyZXNoIn0.mN2pQ7vXwR4tY6bD8sF1hJ5gA0cE3zU9iO2pXkQk3L9",
    "token_type": "Bearer",
    "expires_in": 7200,
    "refresh_expires_in": 28800,
    "user": {
      "user_id": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
      "account": "doctor001",
      "real_name": "张明",
      "role": "DOCTOR",
      "title": "副主任医师",
      "dept_code": "DIG",
      "dept_name": "消化内科",
      "tenant_id": "00000000000000000000000000000001",
      "tenant_name": "示例三甲医院"
    }
  },
  "message": "登录成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `access_token` | string | 访问令牌，有效期 2 小时 |
| `refresh_token` | string | 刷新令牌，有效期 8 小时 |
| `expires_in` | integer | 访问令牌有效期（秒），固定 7200 |
| `refresh_expires_in` | integer | 刷新令牌有效期（秒），固定 28800 |
| `user.user_id` | string | 用户标识（32 位无连字符） |
| `user.role` | string | 角色：`DOCTOR` / `KB_ADMIN` / `ORG_ADMIN` |
| `user.title` | string | 医师职称，非医生角色为 `null` |
| `user.dept_code` | string | 所属科室，非医生角色为 `null` |

**错误码**

| code | message | 说明 |
|---|---|---|
| `400` | 参数校验失败 | 账号或口令长度不符 |
| `10001` | 账号或口令错误 | 凭据校验失败；`message` 含剩余尝试次数 |
| `10002` | 账号已锁定 | 连续失败超限；`message` 含剩余锁定分钟数 |
| `10003` | 账号已停用 | 账号状态为停用 |
| `10009` | 角色不允许访问该端 | 医生账号使用 `ADMIN_WEB` 登录但无管理权限 |
| `429` | 请求过于频繁 | 超过 10 次 / 分钟 |

**业务规则**

- 连续 **5 次**口令错误后锁定账号 **15 分钟**（`AC-F13-3`）
- 术语说明：本文档中的"账号"即数据库中的 `mg_user`，其 `account` 字段为登录标识
- 登录成功后重置 `fail_count`，记录 `last_login_time`
- **口令只存哈希**，不可逆；登录失败时**不区分**"账号不存在"与"口令错误"（均返回 `10001`），防止账号枚举
- 角色为 `DOCTOR` 的账号使用 `client_type=ADMIN_WEB` 登录时返回 `10009`（`AC-F23-1`）

**幂等性**：不支持（每次登录签发新令牌）
**限流**：10 次 / 分钟（按客户端标识）

**示例请求**

```bash
curl -X POST "https://medical-guidance.example.com/api/v1/auth/staff/login" \
  -H "Content-Type: application/json" \
  -d '{
    "account": "doctor001",
    "password": "Med@2026#Dig",
    "client_type": "WEB"
  }'
```

#### 12.1.5 刷新访问令牌

**接口路径**：`POST /api/v1/auth/refresh`
**功能说明**：使用刷新令牌换取新的访问令牌
**权限要求**：无需 `Authorization` 头，但请求体必须携带有效 `refresh_token`

**请求头**

| Header | 必填 | 说明 |
|---|---|---|
| `Content-Type` | 是 | `application/json` |

**路径参数**：无 ｜ **查询参数**：无

**请求体**

```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhMWIyYzNkNGU1ZjZhN2I4YzlkMGUxZjJhM2I0YzVkNiIsInRva2VuX3R5cGUiOiJyZWZyZXNoIn0.mN2pQ7vXwR4tY6bD8sF1hJ5gA0cE3zU9iO2pXkQk3L9"
}
```

**请求体字段说明**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `refresh_token` | string | 是 | 登录时返回的刷新令牌 |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhMWIyYzNkNGU1ZjZhN2I4YzlkMGUxZjJhM2I0YzVkNiJ9.newAccessTokenSignatureHere",
    "token_type": "Bearer",
    "expires_in": 7200
  },
  "message": "成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `access_token` | string | 新的访问令牌 |
| `expires_in` | integer | 有效期（秒），固定 7200 |

**错误码**

| code | message | 说明 |
|---|---|---|
| `400` | 参数校验失败 | 缺少 `refresh_token` |
| `10005` | 令牌无效 | 签名校验失败，或 `token_type` 不是 `refresh` |
| `10006` | 刷新令牌已过期 | 超过 8 小时（院内）/ 7 天（患者） |
| `10003` | 账号已停用 | 账号在令牌有效期内被停用 |

**业务规则**

- **`refresh_token` 不轮换**：刷新时返回新的 `access_token`，`refresh_token` 保持不变
- 对同一 `refresh_token` 的并发刷新请求**返回相同的新令牌**（幂等）
- 刷新时重新校验账号状态，已停用的账号拒绝刷新
- 登出后写入黑名单的 `jti` 不可用于刷新

**幂等性**：天然幂等（同一 `refresh_token` 在有效期内返回相同结果）
**限流**：30 次 / 分钟（按客户端标识）

**示例请求**

```bash
curl -X POST "https://medical-guidance.example.com/api/v1/auth/refresh" \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}'
```

#### 12.1.6 登出

**接口路径**：`POST /api/v1/auth/logout`
**功能说明**：将当前令牌加入黑名单，使其在有效期内失效
**权限要求**：任意已认证角色

**请求头**

| Header | 必填 | 说明 |
|---|---|---|
| `Authorization` | 是 | `Bearer <access_token>` |

**路径参数**：无 ｜ **查询参数**：无 ｜ **请求体**：无

**响应示例**

```json
{
  "code": 200,
  "data": null,
  "message": "已退出登录"
}
```

**错误码**

| code | message | 说明 |
|---|---|---|
| `401` | 未认证 | 缺少或无法解析令牌 |
| `10005` | 令牌无效 | 令牌已被加入黑名单 |

**业务规则**

- 将当前 `jti` 写入缓存黑名单，有效期等于令牌剩余有效期
- **不影响其他设备的登录状态**（多端登录互不干扰）
- 调用后原 `access_token` 与由其派生的 `refresh_token` 均失效

**幂等性**：天然幂等（重复登出返回相同结果）
**限流**：默认 600 次 / 分钟

**示例请求**

```bash
curl -X POST "https://medical-guidance.example.com/api/v1/auth/logout" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### 12.1.7 获取当前身份信息

**接口路径**：`GET /api/v1/auth/me`
**功能说明**：返回当前令牌对应的身份信息与权限范围，供前端初始化界面
**权限要求**：任意已认证角色

**请求头**

| Header | 必填 | 说明 |
|---|---|---|
| `Authorization` | 是 | `Bearer <access_token>` |

**路径参数**：无 ｜ **查询参数**：无 ｜ **请求体**：无

**响应示例**（医生）

```json
{
  "code": 200,
  "data": {
    "subject_id": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
    "identity_type": "STAFF",
    "role": "DOCTOR",
    "real_name": "张明",
    "title": "副主任医师",
    "dept_code": "DIG",
    "dept_name": "消化内科",
    "tenant_id": "00000000000000000000000000000001",
    "tenant_name": "示例三甲医院",
    "permissions": [
      "encounter:read",
      "session:read",
      "triage:confirm",
      "triage:correct",
      "takeover:manage",
      "emr:read"
    ]
  },
  "message": "成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `subject_id` | string | 主体标识（医生/管理员为用户标识，患者为患者标识） |
| `identity_type` | string | `STAFF` / `PATIENT` / `ANONYMOUS` |
| `permissions` | array | 权限点列表，前端据此控制按钮可见性。**服务端仍会独立校验，前端隐藏不等于权限受控** |

**错误码**

| code | message | 说明 |
|---|---|---|
| `401` | 未认证 | 缺少或无法解析令牌 |
| `10004` | 访问令牌已过期 | 需走刷新流程 |

**业务规则**

- 权限点由角色映射得出，不接受客户端指定
- 患者身份调用时 `permissions` 为匿名或实名范围的子集
- 本接口**不做数据查询**，只返回令牌载荷与角色映射结果，因此响应足够快

**幂等性**：天然幂等
**限流**：默认 600 次 / 分钟

**示例请求**

```bash
curl -X GET "https://medical-guidance.example.com/api/v1/auth/me" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### 12.1.8 修改口令

**接口路径**：`PUT /api/v1/auth/password`
**功能说明**：当前用户修改自己的登录口令，修改后强制重新登录
**权限要求**：`DOCTOR` / `KB_ADMIN` / `ORG_ADMIN`

**请求头**

| Header | 必填 | 说明 |
|---|---|---|
| `Authorization` | 是 | `Bearer <access_token>` |
| `Content-Type` | 是 | `application/json` |

**路径参数**：无 ｜ **查询参数**：无

**请求体**

```json
{
  "old_password": "Med@2026#Dig",
  "new_password": "Med@2026#Gas",
  "confirm_password": "Med@2026#Gas"
}
```

**请求体字段说明**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `old_password` | string | 是 | 原口令 |
| `new_password` | string | 是 | 新口令，8~64 位，须包含大写字母、小写字母、数字、特殊字符中的至少三类 |
| `confirm_password` | string | 是 | 确认新口令，须与 `new_password` 一致 |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "need_relogin": true
  },
  "message": "口令修改成功，请重新登录"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `need_relogin` | boolean | 恒为 `true`。修改口令后所有令牌失效 |

**错误码**

| code | message | 说明 |
|---|---|---|
| `400` | 参数校验失败 | 两次新口令不一致，或新口令不满足复杂度 |
| `10010` | 原口令不正确 | 原口令校验失败 |
| `422` | 业务规则校验失败 | 新口令与原口令相同 |
| `401` | 未认证 | 缺少或无法解析令牌 |

**业务规则**

- 新口令**不得与原口令相同**
- 口令复杂度要求：长度 8~64，且包含大写字母、小写字母、数字、特殊字符中的**至少三类**
- 修改成功后**注销该用户的所有会话**，所有令牌立即失效，需重新登录
- 修改动作写入审计日志（`action_type = 'PERM_CHANGE'`）

**幂等性**：不支持（口令修改不可重复执行，第二次会因原口令不匹配失败）
**限流**：5 次 / 分钟（按账号标识）

**示例请求**

```bash
curl -X PUT "https://medical-guidance.example.com/api/v1/auth/password" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{
    "old_password": "Med@2026#Dig",
    "new_password": "Med@2026#Gas",
    "confirm_password": "Med@2026#Gas"
  }'
```

### 12.2 患者端 · 预问诊会话

#### 12.2.1 创建预问诊会话

**接口路径**：`POST /api/v1/patient/sessions`
**功能说明**：创建一次预问诊会话，返回会话标识（对应 `F01`、`F02`）
**权限要求**：`PATIENT`（可匿名）

**请求头**：`Authorization` 是 ｜ `Content-Type` 是 ｜ `Idempotency-Key` 建议

**路径参数**：无 ｜ **查询参数**：无

**请求体**

```json
{
  "chief_complaint": "肚子疼三天了，还有点拉肚子",
  "input_type": "TEXT",
  "device_id": "dev_7f3a9b2c1d4e"
}
```

**请求体字段说明**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `chief_complaint` | string | 否 | 主诉原文，不超过 500 字。为空时先创建空会话，后续通过发送消息补充 |
| `input_type` | string | 否 | 输入方式：`TEXT` / `VOICE` / `BODY_MAP`，默认 `TEXT` |
| `device_id` | string | 否 | 设备标识，用于会话恢复 |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "session_id": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
    "session_no": "S20261015000001",
    "status": "IN_PROGRESS",
    "started_time": "2026-10-15T19:23:41+08:00",
    "expire_time": "2026-10-16T19:23:41+08:00",
    "ws_url": "wss://medical-guidance.example.com/api/v1/ws/sessions/a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
  },
  "message": "成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `session_id` | string | 会话标识（32 位无连字符） |
| `session_no` | string | 会话业务编号，格式 `S` + 日期 + 序号 |
| `expire_time` | string | 会话有效期，默认开始时间 + 24 小时 |
| `ws_url` | string | WebSocket 连接地址（不含鉴权票据） |

**错误码**

| code | message | 说明 |
|---|---|---|
| `400` | 参数校验失败 | 主诉超过 500 字 |
| `401` | 未认证 | 缺少令牌 |
| `20013` | 危重症已触发急诊通道 | 主诉直接命中危重症红线，会话置为 `EMERGENCY` |
| `429` | 请求过于频繁 | 超过 30 次 / 分钟 |
| `500` | 服务器内部错误 | 会话创建失败 |

**业务规则**

- 会话有效期 **24 小时**（可由租户配置 `session.resume_hours` 调整）
- 若 `chief_complaint` 直接命中危重症红线，会话创建成功但状态为 `EMERGENCY`，**不进入后续问诊流程**（`R03`）
- 同一设备的**未完成会话只允许一个**，重复创建时返回既有会话（配合 `Idempotency-Key` 更可靠）

**幂等性**：支持
**限流**：30 次 / 分钟（按患者）

**示例请求**

```bash
curl -X POST "https://medical-guidance.example.com/api/v1/patient/sessions" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6" \
  -d '{
    "chief_complaint": "肚子疼三天了，还有点拉肚子",
    "input_type": "TEXT",
    "device_id": "dev_7f3a9b2c1d4e"
  }'
```

#### 12.2.2 查询会话列表

**接口路径**：`GET /api/v1/patient/sessions`
**功能说明**：分页查询当前患者的预问诊会话列表
**权限要求**：`PATIENT`

**请求头**：`Authorization` 是

**路径参数**：无

**查询参数**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `page` | integer | 否 | `1` | 页码 |
| `size` | integer | 否 | `20` | 每页条数，1~100 |
| `status` | string | 否 | — | 状态筛选，多值用逗号分隔 |
| `start_date` | string | 否 | — | 开始日期 `YYYY-MM-DD` |
| `end_date` | string | 否 | — | 结束日期 `YYYY-MM-DD` |

**请求体**：无

**响应示例**

```json
{
  "code": 200,
  "data": {
    "total": 3,
    "page": 1,
    "size": 20,
    "items": [
      {
        "session_id": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
        "session_no": "S20261015000001",
        "chief_complaint": "肚子疼三天了",
        "status": "FINISHED",
        "dept_code": "DIG",
        "dept_name": "消化内科",
        "inquiry_rounds": 3,
        "started_time": "2026-10-15T19:23:41+08:00"
      }
    ]
  },
  "message": "成功"
}
```

**响应字段说明**：分页字段见 3.2 节；`items[]` 字段说明如下

| 字段 | 类型 | 说明 |
|---|---|---|
| `session_id` | string | 会话标识 |
| `session_no` | string | 会话编号 |
| `chief_complaint` | string | 主诉原文 |
| `status` | string | 会话状态 |
| `dept_code` / `dept_name` | string | 最终建议科室，未产出结论时为 `null` |
| `inquiry_rounds` | integer | 已追问轮次 |
| `started_time` | string | 开始时间 |

**错误码**

| code | message | 说明 |
|---|---|---|
| `400` | 参数校验失败 | 日期格式错误 |
| `401` | 未认证 | 缺少令牌 |
| `400` | 参数校验失败 | `page * size` 超过 10000 |

**业务规则**

- 只返回**当前患者本人**的会话（`NFR16` 行级隔离）
- 按开始时间倒序
- 超出保留期（默认 90 天）的会话不返回
- 病例数据的归档由定时任务执行，接口层不感知

**幂等性**：不支持（`GET` 天然幂等）
**限流**：默认 600 次 / 分钟

**示例请求**

```bash
curl -X GET "https://medical-guidance.example.com/api/v1/patient/sessions?page=1&size=20&status=FINISHED" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### 12.2.3 查询会话详情

**接口路径**：`GET /api/v1/patient/sessions/{session_id}`
**功能说明**：查询会话的完整状态，用于页面刷新后重建界面
**权限要求**：`PATIENT`（仅本人会话）

**请求头**：`Authorization` 是

**路径参数**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `session_id` | string | 是 | 会话标识，32 位无连字符 |

**查询参数**：无 ｜ **请求体**：无

**响应示例**

```json
{
  "code": 200,
  "data": {
    "session_id": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
    "session_no": "S20261015000001",
    "status": "IN_PROGRESS",
    "chief_complaint": "肚子疼三天了，还有点拉肚子",
    "risk_flag": false,
    "inquiry_rounds": 2,
    "max_inquiry_rounds": 8,
    "sufficiency_score": 0.62,
    "askable_slots": ["duration", "location", "accompanying_symptoms"],
    "consent_granted": false,
    "started_time": "2026-10-15T19:23:41+08:00",
    "expire_time": "2026-10-16T19:23:41+08:00",
    "message_count": 6
  },
  "message": "成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `risk_flag` | boolean | 是否命中危重症红线 |
| `max_inquiry_rounds` | integer | 追问轮次上限（来自系统配置） |
| `sufficiency_score` | number | 信息充分度评分，0~1 |
| `askable_slots` | array | 仍未采集的信息项，客户端可用于引导 |
| `consent_granted` | boolean | 是否已授权调阅既往病历 |
| `message_count` | integer | 消息总数 |

**错误码**

| code | message | 说明 |
|---|---|---|
| `404` | 资源不存在 | 会话不存在或不属于当前患者 |
| `401` | 未认证 | 缺少令牌 |

**业务规则**

- 访问他人会话返回 `404`（**不返回 `403`**，避免探测）
- `askable_slots` 排除"已问项"与"既往史已获得"的项（`AC-F34-3`）

**幂等性**：天然幂等
**限流**：默认 600 次 / 分钟

**示例请求**

```bash
curl -X GET "https://medical-guidance.example.com/api/v1/patient/sessions/a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### 12.2.4 发送消息

**接口路径**：`POST /api/v1/patient/sessions/{session_id}/messages`
**功能说明**：向会话发送一条患者消息，触发智能体流程（对应 `F02`、`F03`、`F05`）
**权限要求**：`PATIENT`（仅本人会话）

**请求头**：`Authorization` 是 ｜ `Content-Type` 是 ｜ `Idempotency-Key` 不建议（消息有顺序语义）

**路径参数**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `session_id` | string | 是 | 会话标识 |

**查询参数**：无

**请求体**

```json
{
  "content": "持续性的疼，晚上更明显",
  "msg_type": "TEXT",
  "extra": {}
}
```

**请求体字段说明**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `content` | string | 是 | 消息内容，1~500 字 |
| `msg_type` | string | 否 | `TEXT` / `VOICE` / `BODY_MAP`，默认 `TEXT` |
| `extra` | object | 否 | 附加信息：`BODY_MAP` 时传 `{"body_parts": ["右上腹"]}`；`VOICE` 时传 `{"file_id": "..."}` |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "message_id": "f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2",
    "seq_no": 4,
    "session_status": "IN_PROGRESS",
    "async": true,
    "ws_hint": "后续内容通过 WebSocket 推送"
  },
  "message": "成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `message_id` | string | 患者消息标识 |
| `seq_no` | integer | 消息在会话内的序号 |
| `async` | boolean | 恒为 `true`。**AI 回复通过 WebSocket 推送，不在此响应中返回** |
| `ws_hint` | string | 提示信息 |

**错误码**

| code | message | 说明 |
|---|---|---|
| `400` | 参数校验失败 | 内容为空或超过 500 字 |
| `404` | 资源不存在 | 会话不存在或不属于当前患者 |
| `20002` | 会话已结束 | 会话处于终态 |
| `20013` | 危重症已触发急诊通道 | 不可继续发消息 |
| `20015` | 不支持的消息类型 | `msg_type` 取值非法 |
| `429` | 请求过于频繁 | 超过 60 次 / 分钟 |
| `60004` | 内容生成服务不可用 | 推理服务不可用且未降级 |

**业务规则**

- 消息**不做幂等保证**：连续两次相同内容视为两次发言（消息有顺序语义）
- 响应**立即返回**，AI 回复经 WebSocket 异步推送（架构文档 §6.1）
- 会话状态为 `EMERGENCY` 时拒绝发送，返回 `20013`
- 内容过长时**不截断**，直接返回 `400`

**幂等性**：不支持
**限流**：60 次 / 分钟（按会话）

**示例请求**

```bash
curl -X POST "https://medical-guidance.example.com/api/v1/patient/sessions/a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6/messages" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{
    "content": "持续性的疼，晚上更明显",
    "msg_type": "TEXT",
    "extra": {}
  }'
```

#### 12.2.5 查询消息列表

**接口路径**：`GET /api/v1/patient/sessions/{session_id}/messages`
**功能说明**：分页查询会话的对话记录，用于页面刷新或断线后重建
**权限要求**：`PATIENT`（仅本人会话）

**请求头**：`Authorization` 是

**路径参数**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `session_id` | string | 是 | 会话标识 |

**查询参数**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `page` | integer | 否 | `1` | 页码 |
| `size` | integer | 否 | `50` | 每页条数，1~100 |
| `after_seq` | integer | 否 | — | 只返回序号大于该值的消息，用于增量同步 |

**请求体**：无

**响应示例**

```json
{
  "code": 200,
  "data": {
    "total": 6,
    "page": 1,
    "size": 50,
    "items": [
      {
        "message_id": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
        "seq_no": 1,
        "role": "PATIENT",
        "content": "肚子疼三天了，还有点拉肚子",
        "msg_type": "TEXT",
        "extra": {},
        "send_time": "2026-10-15T19:23:41+08:00"
      },
      {
        "message_id": "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7",
        "seq_no": 2,
        "role": "AI",
        "content": "请问疼痛是持续性的还是阵发性的？",
        "msg_type": "TEXT",
        "extra": {"node": "INQUIRY"},
        "send_time": "2026-10-15T19:23:44+08:00"
      }
    ]
  },
  "message": "成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `message_id` | string | 消息标识 |
| `seq_no` | integer | 会话内序号，从 1 递增 |
| `role` | string | `PATIENT` / `AI` / `DOCTOR` / `SYSTEM` |
| `content` | string | 消息内容 |
| `msg_type` | string | `TEXT` / `VOICE` / `BODY_MAP` / `RESULT` / `EMERGENCY` |
| `extra` | object | 附加信息，`BODY_MAP` 类型含部位列表 |

**错误码**

| code | message | 说明 |
|---|---|---|
| `404` | 资源不存在 | 会话不存在或不属于当前患者 |
| `401` | 未认证 | 缺少令牌 |

**业务规则**

- 按 `seq_no` 升序返回（**不依赖时间戳排序**，避免同毫秒内顺序不确定）
- `after_seq` 用于增量同步：客户端已知前 N 条时只拉取新增部分
- 患者端**过滤 `SYSTEM` 角色的内部消息**

**幂等性**：天然幂等
**限流**：默认 600 次 / 分钟

**示例请求**

```bash
curl -X GET "https://medical-guidance.example.com/api/v1/patient/sessions/a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6/messages?page=1&size=50" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### 12.2.6 恢复会话

**接口路径**：`POST /api/v1/patient/sessions/{session_id}/resume`
**功能说明**：患者离开后重新进入时恢复会话，从中断处继续（对应 `F06`）
**权限要求**：`PATIENT`（仅本人会话）

**请求头**：`Authorization` 是 ｜ `Content-Type` 是

**路径参数**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `session_id` | string | 是 | 会话标识 |

**查询参数**：无

**请求体**

```json
{
  "device_id": "dev_7f3a9b2c1d4e",
  "last_seq": 4
}
```

**请求体字段说明**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `device_id` | string | 是 | 设备标识，须与创建会话时一致 |
| `last_seq` | integer | 否 | 客户端最后收到的消息序号，用于增量补发 |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "session_id": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
    "session_status": "IN_PROGRESS",
    "inquiry_rounds": 2,
    "asked_slots": ["duration", "location"],
    "resumed": true,
    "replayed": [
      {
        "message_id": "f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2",
        "seq_no": 5,
        "role": "AI",
        "content": "请问有没有发热或呕吐？",
        "msg_type": "TEXT",
        "send_time": "2026-10-15T19:25:10+08:00"
      }
    ],
    "replayed_count": 1
  },
  "message": "会话已恢复"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `resumed` | boolean | 恒为 `true`（失败走错误码） |
| `asked_slots` | array | 已问项列表。**恢复后不再重复提问这些项**（`AC-F06-2`） |
| `replayed` | array | 断线期间缺失的消息 |
| `replayed_count` | integer | 补发消息数 |

**错误码**

| code | message | 说明 |
|---|---|---|
| `404` | 资源不存在 | 会话不存在或不属于当前患者 |
| `20003` | 会话已过期 | 超过 24 小时有效期 |
| `20002` | 会话已结束 | 会话处于终态，无需恢复 |
| `400` | 参数校验失败 | `device_id` 与会话不匹配 |
| `401` | 未认证 | 缺少令牌 |

**业务规则**

- 恢复有效期默认 **24 小时**（`session.resume_hours` 可配置）
- **已问项不再重复提问**（`AC-F06-2`）
- 设备不匹配时拒绝恢复，避免会话被他人接管
- 会话状态从检查点载入，**支持应用重启后恢复**（`NFR26`）
- 超过有效期时返回 `20003`，客户端应引导新建会话

**幂等性**：天然幂等
**限流**：30 次 / 分钟（按患者）

**示例请求**

```bash
curl -X POST "https://medical-guidance.example.com/api/v1/patient/sessions/a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6/resume" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{"device_id": "dev_7f3a9b2c1d4e", "last_seq": 4}'
```

#### 12.2.7 提交既往病历调阅授权

**接口路径**：`POST /api/v1/patient/sessions/{session_id}/consent`
**功能说明**：患者明示授权系统调阅其既往病历（对应 `F10`、`R12`）
**权限要求**：`PATIENT`（须已实名）

**请求头**：`Authorization` 是 ｜ `Content-Type` 是

**路径参数**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `session_id` | string | 是 | 会话标识 |

**查询参数**：无

**请求体**

```json
{
  "granted": true,
  "consent_scope": "NEAR_2Y",
  "consent_channel": "PATIENT_H5"
}
```

**请求体字段说明**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `granted` | boolean | 是 | 是否授权。`false` 表示明确拒绝 |
| `consent_scope` | string | 否 | 授权范围：`NEAR_1Y` / `NEAR_2Y` / `ALL`，默认 `NEAR_2Y` |
| `consent_channel` | string | 否 | 授权渠道：`PATIENT_H5` / `OFFLINE`，默认 `PATIENT_H5` |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "consent_id": "c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8",
    "granted": true,
    "consent_scope_label": "近两年门诊与住院记录",
    "consent_time": "2026-10-15T19:26:03+08:00",
    "expire_time": null
  },
  "message": "授权成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `consent_id` | string | 授权记录标识 |
| `consent_scope_label` | string | 授权范围的中文描述，**须具体说明范围，不使用"相关数据"等模糊表述**（`AC-F10-2`） |
| `expire_time` | string | 失效时间，`null` 表示长期有效 |

**错误码**

| code | message | 说明 |
|---|---|---|
| `404` | 资源不存在 | 会话不存在或不属于当前患者 |
| `403` | 无权限 | **匿名身份未完成实名验证**，不可授权病历调阅 |
| `400` | 参数校验失败 | `consent_scope` 取值非法 |
| `401` | 未认证 | 缺少令牌 |

**业务规则**

- **授权是调阅的前提**：未授权时病历相关能力一律拒绝（`20012`、`AC-F10-1`）
- 授权记录**独立留痕**，可撤回（撤回通过传 `granted=false` 实现）
- 授权动作写审计日志
- **未授权时流程继续**，既往史相关槽位改由提问补全，并提示患者"部分问题需向您确认"

**幂等性**：天然幂等（重复提交更新同一条授权记录）
**限流**：10 次 / 分钟（按患者）

**示例请求**

```bash
curl -X POST "https://medical-guidance.example.com/api/v1/patient/sessions/a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6/consent" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{
    "granted": true,
    "consent_scope": "NEAR_2Y",
    "consent_channel": "PATIENT_H5"
  }'
```

#### 12.2.8 获取人体部位图

**接口路径**：`GET /api/v1/patient/body-map`
**功能说明**：返回人体部位分区图的数据，供患者点选主诉部位（对应 `F04`）
**权限要求**：`PATIENT`（可匿名）

**请求头**：`Authorization` 是

**路径参数**：无

**查询参数**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `view` | string | 否 | `FRONT` | 视图：`FRONT` 正面 / `BACK` 背面 |

**请求体**：无

**响应示例**

```json
{
  "code": 200,
  "data": {
    "view": "FRONT",
    "svg_url": "/api/v1/files/8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d",
    "regions": [
      {"code": "HEAD", "name": "头部", "path_id": "region-head"},
      {"code": "ABD_RUQ", "name": "右上腹", "path_id": "region-abd-ruq", "dept_hint": ["DIG", "GEN_SURG"]},
      {"code": "ABD_RLQ", "name": "右下腹", "path_id": "region-abd-rlq", "dept_hint": ["GEN_SURG", "URO"]}
    ],
    "max_select": 5
  },
  "message": "成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `svg_url` | string | 分区图资源地址 |
| `regions[].code` | string | 部位编码，提交消息时使用 |
| `regions[].name` | string | 部位中文名，**使用标准解剖术语**（`AC-F04-2`） |
| `regions[].path_id` | string | SVG 中的元素标识，供前端绑定点击事件 |
| `regions[].dept_hint` | array | 该部位常见对应科室，用于前端提示 |
| `max_select` | integer | 最多可选部位数，固定 5（`AC-F04-1`） |

**错误码**

| code | message | 说明 |
|---|---|---|
| `400` | 参数校验失败 | `view` 取值非法 |
| `401` | 未认证 | 缺少令牌 |

**业务规则**

- 部位名称使用**标准解剖术语**，不出现口语化表述
- 该数据为静态配置，服务端可长时间缓存
- 部位点选结果通过 12.2.4 接口以 `msg_type=BODY_MAP` 提交

**幂等性**：天然幂等
**限流**：默认 600 次 / 分钟

**示例请求**

```bash
curl -X GET "https://medical-guidance.example.com/api/v1/patient/body-map?view=FRONT" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### 12.3 患者端 · 分诊与挂号

#### 12.3.1 查询分诊结果

**接口路径**：`GET /api/v1/patient/sessions/{session_id}/triage`
**功能说明**：查询分诊结论，返回建议科室与已收集的症状摘要。危重症会话额外返回急诊引导信息（对应 `F07`、`F11`、`F12`）
**权限要求**：`PATIENT`（仅本人会话）

**请求头**：`Authorization` 是

**路径参数**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `session_id` | string | 是 | 会话标识 |

**查询参数**：无 ｜ **请求体**：无

**响应示例**

```json
{
  "code": 200,
  "data": {
    "triage_result_id": "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7",
    "route": "DIRECT",
    "confidence": 0.8731,
    "recommended_depts": [
      {
        "dept_code": "DIG",
        "dept_name": "消化内科",
        "confidence": 0.8731,
        "is_primary": true
      }
    ],
    "symptom_summary": {
      "chief_complaint": "肚子疼三天了，还有点拉肚子",
      "duration": "3 天",
      "location": "中上腹",
      "nature": "持续性",
      "accompanying": ["腹泻", "恶心"],
      "past_history": ["高血压"],
      "allergy": ["青霉素"]
    },
    "inquiry_rounds": 3,
    "emergency_guidance": null,
    "disclaimer": "本系统仅提供分诊建议，不构成医学诊断。请以医生面诊为准。",
    "generated_time": "2026-10-15T19:28:12+08:00"
  },
  "message": "成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `route` | string | 路由去向：`DIRECT` / `MDT` / `MANUAL` / `EMERGENCY` |
| `confidence` | number | 整体置信度，0~1 |
| `recommended_depts` | array | 建议科室列表。**只含科室，不含任何疾病名称**（`R01`） |
| `recommended_depts[].is_primary` | boolean | 是否为首要推荐科室 |
| `symptom_summary` | object | 已收集的症状摘要，字段随采集情况可能为 `null` |
| `emergency_guidance` | object \| null | **危重症引导信息（`F11`）**。仅当 `route='EMERGENCY'` 时非空，其余情况为 `null` |
| `emergency_guidance.triggered` | boolean | 是否已触发急诊通道 |
| `emergency_guidance.reason` | string | 触发原因描述。**同样不得出现疾病名称**（`R01`），如「胸痛伴呼吸困难」 |
| `emergency_guidance.advice` | string | 就医引导文案，如「请立即前往急诊科，或拨打急救电话」 |
| `emergency_guidance.emergency_phone` | string | 急救电话，默认 `120` |
| `emergency_guidance.recommended_dept` | string | 建议直接前往的科室，如「急诊内科」 |
| `disclaimer` | string | **免责声明文本（`F12`）**，客户端须完整展示，**不得折叠、截断或延迟显示** |

**错误码**

| code | message | 说明 |
|---|---|---|
| `404` | 资源不存在 | 会话不存在或不属于当前患者 |
| `20006` | 分诊结论尚未生成 | 结论仍在生成中，建议稍后重试 |
| `20005` | 该会话已存在分诊结论 | 不会出现；若并发查询中命中，返回既有结论 |
| `401` | 未认证 | 缺少令牌 |

**业务规则**

- **响应中不得出现任何疾病名称**（`R01`、`AC-F07-1`）——服务端在返回前经输出内容约束处理（`F54`）
- 无候选科室时 `recommended_depts` 为 `[]`，`route` 为 `MANUAL`，客户端应展示转人工提示（`AC-F07-3`）
- 置信度低于阈值时附加提示文案
- **鉴别诊断候选、判断依据不在本接口返回**——这两项仅医生端可见（`R02`）
- `route='EMERGENCY'` 时 `emergency_guidance` 必须非空；其中的 `reason` 与 `advice` 同样受输出内容约束（`F54`），不得出现疾病名称（`R01`、`NFR65`）
- `disclaimer` 由服务端下发而非前端硬编码，便于按机构调整文案（`F12`）

**幂等性**：天然幂等
**限流**：默认 600 次 / 分钟

**示例请求**

```bash
curl -X GET "https://medical-guidance.example.com/api/v1/patient/sessions/a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6/triage" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### 12.3.2 查询预问诊病历（患者视图）

**接口路径**：`GET /api/v1/patient/sessions/{session_id}/emr`
**功能说明**：查询 SOAP 预问诊病历的患者视图（对应 `F07`、`F36`）
**权限要求**：`PATIENT`（仅本人会话）

**请求头**：`Authorization` 是

**路径参数**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `session_id` | string | 是 | 会话标识 |

**查询参数**：无 ｜ **请求体**：无

**响应示例**

```json
{
  "code": 200,
  "data": {
    "emr_record_id": "c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8",
    "schema_version": "1.0",
    "generate_status": "SUCCESS",
    "subjective": {
      "chief_complaint": "肚子疼三天了，还有点拉肚子",
      "present_illness": "3 天前无明显诱因出现中上腹持续性疼痛，伴腹泻、恶心，无发热。",
      "past_history": ["高血压 5 年，规律服药"],
      "allergy": ["青霉素过敏"]
    },
    "objective": {
      "collected_vitals": [],
      "note": "本次为线上预问诊，未采集体格检查数据"
    },
    "assessment": null,
    "plan": {
      "recommended_depts": ["消化内科"],
      "suggested_workup": ["如症状持续，建议到院后完善血常规与腹部超声"],
      "note": "以上为就诊建议，不构成诊断"
    },
    "disclaimer": "本系统仅提供分诊建议，不构成医学诊断。请以医生面诊为准。",
    "generated_time": "2026-10-15T19:28:15+08:00"
  },
  "message": "成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `subjective` | object | S 段：主观资料（主诉、现病史、既往史、过敏史） |
| `objective` | object | O 段：客观资料。线上预问诊通常无体格检查数据 |
| `assessment` | object | A 段：评估。**患者视图恒为 `null`**（`R01`） |
| `plan.suggested_workup` | array | 建议的补充检查。**不含用药建议**（`R11`） |
| `generate_status` | string | `SUCCESS` / `PARTIAL` / `FAILED` |

**错误码**

| code | message | 说明 |
|---|---|---|
| `404` | 资源不存在 | 会话或病历不存在 |
| `20006` | 分诊结论尚未生成 | 病历尚未生成 |
| `401` | 未认证 | 缺少令牌 |

**业务规则**

- **A 段（评估）对患者恒为 `null`**：该段含鉴别诊断方向，仅医生端可见（`R01`、`R02`）
- **不返回任何疾病名称与用药建议**（`R01`、`R11`、`AC-F54-2`）
- `generate_status = PARTIAL` 时表示部分字段缺失，**不伪造内容**（`AC-F36-1`）
- 患者可看到 S / O / P 三段，用于了解"医生接诊时会看到什么"

**幂等性**：天然幂等
**限流**：默认 600 次 / 分钟

**示例请求**

```bash
curl -X GET "https://medical-guidance.example.com/api/v1/patient/sessions/a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6/emr" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### 12.3.3 查询号源

**接口路径**：`GET /api/v1/patient/slots`
**功能说明**：查询指定科室的可用号源与医生排班（对应 `F43`、`F08`）
**权限要求**：`PATIENT`

**请求头**：`Authorization` 是

**路径参数**：无

**查询参数**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `dept_code` | string | 是 | — | 科室编码 |
| `start_date` | string | 否 | 今天 | 开始日期 `YYYY-MM-DD` |
| `end_date` | string | 否 | 开始日期 + 7 天 | 结束日期，跨度不超过 14 天 |
| `doctor_id` | string | 否 | — | 指定医生 |
| `page` | integer | 否 | `1` | 页码 |
| `size` | integer | 否 | `20` | 每页条数，1~100 |

**请求体**：无

**响应示例**

```json
{
  "code": 200,
  "data": {
    "total": 12,
    "page": 1,
    "size": 20,
    "items": [
      {
        "slot_id": "HIS_SLOT_20261016_DIG_001",
        "dept_code": "DIG",
        "dept_name": "消化内科",
        "doctor_id": "d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9",
        "doctor_name": "张明",
        "doctor_title": "副主任医师",
        "schedule_date": "2026-10-16",
        "time_slot": "09:00-09:30",
        "remaining": 3,
        "fee": null,
        "source": "MOCK_HIS"
      }
    ]
  },
  "message": "成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `slot_id` | string | 号源标识，挂号时回传 |
| `doctor_title` | string | 医师职称 |
| `time_slot` | string | 就诊时段 |
| `remaining` | integer | 剩余号源数 |
| `fee` | number | 挂号费。**本期不涉及资金流，固定为 `null`** |
| `source` | string | 号源来源，`MOCK_HIS` 表示来自模拟系统（本期） |

**错误码**

| code | message | 说明 |
|---|---|---|
| `400` | 参数校验失败 | 日期跨度超过 14 天，或日期格式错误 |
| `30003` | 该科室近期无号源 | 查询范围内无可用号源（`items` 为空时返回此码） |
| `30007` | 号源查询服务超时 | 外部系统超过 3 秒未响应 |
| `60001` | 病历系统不可用 | 号源服务不可用 |
| `401` | 未认证 | 缺少令牌 |

**业务规则**

- 本接口**超时可降级**：返回 `30007` 后客户端可重试或仅展示科室信息（`AC-F08-3`）
- 无号源时返回 `30003`，客户端应展示"关注放号"入口（`AC-F08-2`）
- **不涉及资金流**：挂号费字段恒为 `null`，支付走院内既有渠道
- 结果按"最近可约 + 医师职称"排序

**幂等性**：天然幂等
**限流**：默认 600 次 / 分钟

**示例请求**

```bash
curl -X GET "https://medical-guidance.example.com/api/v1/patient/slots?dept_code=DIG&start_date=2026-10-16&end_date=2026-10-20" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### 12.3.4 提交挂号

**接口路径**：`POST /api/v1/patient/appointments`
**功能说明**：为指定号源创建预约（对应 `F44`、`F08`）
**权限要求**：`PATIENT`（**须已完成手机号验证**）

**请求头**：`Authorization` 是 ｜ `Content-Type` 是 ｜ `Idempotency-Key` **强烈建议**

**路径参数**：无 ｜ **查询参数**：无

**请求体**

```json
{
  "slot_id": "HIS_SLOT_20261016_DIG_001",
  "session_id": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
  "dept_code": "DIG",
  "doctor_id": "d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9"
}
```

**请求体字段说明**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `slot_id` | string | 是 | 号源标识，来自 12.3.3 的返回 |
| `session_id` | string | 否 | 来源会话标识，线下挂号时为空 |
| `dept_code` | string | 是 | 挂号科室编码 |
| `doctor_id` | string | 否 | 医生标识，不指定时由系统分配 |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "appointment_id": "e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0",
    "appointment_no": "AP20261016000123",
    "dept_code": "DIG",
    "dept_name": "消化内科",
    "doctor_name": "张明",
    "doctor_title": "副主任医师",
    "schedule_date": "2026-10-16",
    "time_slot": "09:00-09:30",
    "status": "BOOKED",
    "created_time": "2026-10-15T19:30:22+08:00",
    "notice": "请于就诊时段前 15 分钟到达科室分诊台报到"
  },
  "message": "预约成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `appointment_id` | string | 预约标识 |
| `appointment_no` | string | 预约单号，格式 `AP` + 日期 + 序号 |
| `status` | string | 状态：`BOOKED` / `CANCELLED` / `COMPLETED` / `NOSHOW` |
| `notice` | string | 就诊提示文案 |

**错误码**

| code | message | 说明 |
|---|---|---|
| `403` | 无权限 | 匿名身份未完成手机号验证（`R10`） |
| `30001` | 号源不存在或已过期 | `slot_id` 无效 |
| `30002` | 号源已被占用 | 并发冲突，客户端应刷新号源列表（`AC-F44-2`） |
| `30004` | 已存在相同预约 | 幂等命中，返回原预约记录 |
| `409` | 资源冲突 | 同一幂等键的请求正在处理中 |
| `400` | 参数校验失败 | 必填字段缺失 |
| `60001` | 病历系统不可用 | HIS 预约接口不可用 |

**业务规则**

- **幂等由唯一约束保证**：`appointment_no` 在租户内唯一（`AC-F44-1`）。重复提交命中唯一约束时返回原记录，`code` 为 `30004`
- **实名前置**：匿名身份调用返回 `403`，客户端应引导完成手机号验证（`R10`）
- 号源并发占用时返回 `30002`，**不做排队重试**——由客户端刷新后重新选择
- 挂号动作写审计日志（`action_type = 'EXTERNAL_CALL'`）
- **不涉及支付**：本期无支付环节，创建即占用号源

**幂等性**：支持（**强烈建议携带 `Idempotency-Key`**）
**限流**：10 次 / 分钟（按患者）

**示例请求**

```bash
curl -X POST "https://medical-guidance.example.com/api/v1/patient/appointments" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: 3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f" \
  -d '{
    "slot_id": "HIS_SLOT_20261016_DIG_001",
    "session_id": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
    "dept_code": "DIG",
    "doctor_id": "d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9"
  }'
```

#### 12.3.5 查询挂号列表

**接口路径**：`GET /api/v1/patient/appointments`
**功能说明**：分页查询当前患者的预约记录
**权限要求**：`PATIENT`

**请求头**：`Authorization` 是

**路径参数**：无

**查询参数**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `page` | integer | 否 | `1` | 页码 |
| `size` | integer | 否 | `20` | 每页条数，1~100 |
| `status` | string | 否 | — | 状态筛选：`BOOKED` / `CANCELLED` / `COMPLETED` / `NOSHOW` |
| `start_date` | string | 否 | — | 就诊日期起 |
| `end_date` | string | 否 | — | 就诊日期止 |

**请求体**：无

**响应示例**

```json
{
  "code": 200,
  "data": {
    "total": 2,
    "page": 1,
    "size": 20,
    "items": [
      {
        "appointment_id": "e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0",
        "appointment_no": "AP20261016000123",
        "dept_code": "DIG",
        "dept_name": "消化内科",
        "doctor_name": "张明",
        "schedule_date": "2026-10-16",
        "time_slot": "09:00-09:30",
        "status": "BOOKED",
        "cancellable": true,
        "created_time": "2026-10-15T19:30:22+08:00"
      }
    ]
  },
  "message": "成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `cancellable` | boolean | **当前是否可取消**。由服务端根据状态与时限计算，客户端据此控制按钮 |

**错误码**

| code | message | 说明 |
|---|---|---|
| `401` | 未认证 | 缺少令牌 |
| `400` | 参数校验失败 | 日期格式错误 |

**业务规则**

- 只返回**当前患者本人**的预约记录（行级隔离）
- 可取消判定：状态为 `BOOKED` 且未超过就诊时间
- 按就诊日期倒序排列

**幂等性**：天然幂等
**限流**：默认 600 次 / 分钟

**示例请求**

```bash
curl -X GET "https://medical-guidance.example.com/api/v1/patient/appointments?page=1&size=20&status=BOOKED" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### 12.3.6 取消挂号

**接口路径**：`DELETE /api/v1/patient/appointments/{appointment_id}`
**功能说明**：取消已预约的号源
**权限要求**：`PATIENT`（仅本人预约）

**请求头**：`Authorization` 是 ｜ `Content-Type` 是

**路径参数**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `appointment_id` | string | 是 | 预约标识 |

**查询参数**：无

**请求体**

```json
{
  "reason": "时间冲突，改期就诊"
}
```

**请求体字段说明**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `reason` | string | 否 | 取消原因，不超过 200 字 |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "appointment_id": "e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0",
    "status": "CANCELLED",
    "cancel_time": "2026-10-15T19:32:10+08:00"
  },
  "message": "已取消预约"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `status` | string | 取消后状态，固定 `CANCELLED` |
| `cancel_time` | string | 取消时间 |

**错误码**

| code | message | 说明 |
|---|---|---|
| `404` | 资源不存在 | 预约不存在或不属于当前患者 |
| `30006` | 该预约不可取消 | 状态已为 `CANCELLED` / `COMPLETED`，或已超过就诊时间 |
| `60001` | 病历系统不可用 | HIS 取消失败 |
| `401` | 未认证 | 缺少令牌 |

**业务规则**

- 只有状态为 `BOOKED` 且未超过就诊时间的预约可取消
- 取消是**软操作**：记录 `status = 'CANCELLED'` 与 `cancel_time`，**不删除记录**（预约是业务凭证）
- 取消动作写审计日志
- 因已涉及外部系统，取消失败时返回 `60001`，客户端应提示稍后重试

**幂等性**：天然幂等（重复取消返回相同结果）
**限流**：20 次 / 分钟（按患者）

**示例请求**

```bash
curl -X DELETE "https://medical-guidance.example.com/api/v1/patient/appointments/e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{"reason": "时间冲突，改期就诊"}'
```

### 12.4 患者端 · 语音与摘要

#### 12.4.1 语音转写

**接口路径**：`POST /api/v1/patient/asr/transcribe`
**功能说明**：将患者语音转写为文字，供其确认后作为主诉提交（对应 `F03`）
**权限要求**：`PATIENT`（可匿名）

**请求头**：`Authorization` 是 ｜ `Content-Type` 是 `multipart/form-data`

**路径参数**：无 ｜ **查询参数**：无

**请求体**（`multipart/form-data`）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `file` | file | 是 | 音频文件，`.wav` / `.mp3` / `.m4a`，不超过 10 MB |
| `session_id` | string | 是 | 关联会话标识 |
| `duration_ms` | integer | 否 | 音频时长（毫秒），用于校验是否超过 60 秒 |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "text": "肚子疼三天了，还有点拉肚子",
    "duration_ms": 4200,
    "confidence": 0.94,
    "hotwords_hit": ["拉肚子"],
    "truncated": false
  },
  "message": "成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `text` | string | 转写文本。**不自动提交**，须由患者确认（`AC-F03-1`） |
| `duration_ms` | integer | 音频时长 |
| `confidence` | number | 转写置信度，0~1 |
| `hotwords_hit` | array | 命中的医疗热词，用于验证热词表生效 |
| `truncated` | boolean | 音频是否被截断（超过 60 秒时 `true`） |

**错误码**

| code | message | 说明 |
|---|---|---|
| `400` | 参数校验失败 | 文件为空，或 `session_id` 缺失 |
| `60009` | 文件格式不支持 | 音频格式不在白名单 |
| `60010` | 文件大小超限 | 超过 10 MB |
| `60003` | 语音识别服务不可用 | ASR 服务不可用，客户端应降级为文字输入（`AC-F03-4`） |
| `429` | 请求过于频繁 | 超过 20 次 / 分钟 |

**业务规则**

- 转写结果**不自动提交**，必须由患者确认或修改后通过 12.2.4 提交
- 音频超过 60 秒时自动截断并置 `truncated=true`，提示患者分次录入
- 语音识别服务为**本地能力**，不调用院外服务（`NFR57`）
- 配置医疗热词表后，「消化内科」「胰腺炎」等词汇应正确识别（`AC-F03-3`）
- 转写为空时返回成功但 `text` 为 `""`，客户端提示重试且不计入输入历史

**幂等性**：不支持
**限流**：20 次 / 分钟（按患者）

**示例请求**

```bash
curl -X POST "https://medical-guidance.example.com/api/v1/patient/asr/transcribe" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -F "file=@/path/to/voice.m4a" \
  -F "session_id=a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6" \
  -F "duration_ms=4200"
```

#### 12.4.2 查询症状摘要

**接口路径**：`GET /api/v1/patient/sessions/{session_id}/summary`
**功能说明**：查询已采集的症状结构化摘要，供患者核对（对应 `F07`）
**权限要求**：`PATIENT`（仅本人会话）

**请求头**：`Authorization` 是

**路径参数**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `session_id` | string | 是 | 会话标识 |

**查询参数**：无 ｜ **请求体**：无

**响应示例**

```json
{
  "code": 200,
  "data": {
    "chief_complaint": "肚子疼三天了，还有点拉肚子",
    "entities": {
      "symptoms": [{"code": "ABDOMINAL_PAIN", "name": "腹痛", "negated": false}],
      "locations": [{"code": "ABD_EPIGASTRIC", "name": "中上腹"}],
      "durations": [{"value": 3, "unit": "DAY", "text": "3 天"}],
      "past_history": [{"name": "高血压"}],
      "medications": [{"name": "氨氯地平"}],
      "allergies": [{"name": "青霉素"}]
    },
    "missing_slots": ["accompanying_symptoms", "aggravating_factors"],
    "updated_time": "2026-10-15T19:28:10+08:00"
  },
  "message": "成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `entities.symptoms[].negated` | boolean | **是否为否定表述**。`true` 表示"没有发烧"这类阴性记录（`AC-F37-2`） |
| `entities.durations` | array | 结构化时长，`value` 与 `unit` 供程序消费，`text` 供展示 |
| `missing_slots` | array | 仍未采集的信息项 |

**错误码**

| code | message | 说明 |
|---|---|---|
| `404` | 资源不存在 | 会话不存在或不属于当前患者 |
| `401` | 未认证 | 缺少令牌 |

**业务规则**

- 术语已规范化：口语表述转为标准医学表述（如"拉肚子"→"腹泻"，`AC-F37-3`）
- **否定表述必须正确标注**（`AC-F37-2`）
- 同一实体多重表述时去重，保留置信度最高者

**幂等性**：天然幂等
**限流**：默认 600 次 / 分钟

**示例请求**

```bash
curl -X GET "https://medical-guidance.example.com/api/v1/patient/sessions/a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6/summary" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### 12.4.3 查询历史会话【二期工程】

**接口路径**：`GET /api/v1/patient/history`
**功能说明**：查询患者的历史预问诊记录（对应 `F09`）
**权限要求**：`PATIENT`（须已实名）

> **本接口属二期工程，一期不实现。** 一期的患者仅能在会话有效期内查看当前会话。

**路径参数**：无

**查询参数**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `page` | integer | 否 | `1` | 页码 |
| `size` | integer | 否 | `20` | 每页条数，1~100 |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "total": 5,
    "page": 1,
    "size": 20,
    "items": [
      {
        "session_id": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
        "session_no": "S20261015000001",
        "chief_complaint": "肚子疼三天了",
        "dept_code": "DIG",
        "dept_name": "消化内科",
        "started_time": "2026-10-15T19:23:41+08:00"
      }
    ]
  },
  "message": "成功"
}
```

**错误码**

| code | message | 说明 |
|---|---|---|
| `401` | 未认证 | 缺少令牌 |
| `403` | 无权限 | 匿名身份不可查询历史记录 |

**业务规则**

- **归属隔离**：只返回当前患者本人的记录（`AC-F09-1`）
- **保留期外不返回**：超出 `session.retention_days`（默认 90 天）的记录不可见（`AC-F09-2`）
- 二期实现，一期部署时该路径返回 `404`

**幂等性**：天然幂等 ｜ **限流**：默认 600 次 / 分钟

**示例请求**

```bash
curl -X GET "https://medical-guidance.example.com/api/v1/patient/history?page=1&size=20" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### 12.5 医生端 · 接诊与分诊

#### 12.5.1 查询今日接诊列表

**接口路径**：`GET /api/v1/doctor/encounters`
**功能说明**：查询当前医生今日接诊的患者列表（对应 `F14`）
**权限要求**：`DOCTOR`

**请求头**：`Authorization` 是

**路径参数**：无

**查询参数**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `page` | integer | 否 | `1` | 页码 |
| `size` | integer | 否 | `20` | 每页条数，1~100 |
| `status` | string | 否 | — | 状态筛选：`IN_PROGRESS` / `FINISHED` / `PENDING_TAKEOVER` / `TAKEN_OVER` / `CLOSED` / `EMERGENCY` |
| `encounter_date` | string | 否 | 今天 | 就诊日期 `YYYY-MM-DD` |
| `sort_by` | string | 否 | `started_time` | 排序字段白名单：`started_time` / `inquiry_rounds` |
| `sort_order` | string | 否 | `desc` | `asc` / `desc` |

**请求体**：无

**响应示例**

```json
{
  "code": 200,
  "data": {
    "total": 18,
    "page": 1,
    "size": 20,
    "items": [
      {
        "session_id": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
        "session_no": "S20261015000001",
        "patient_display": "患者 8000",
        "patient_hash": "9f8e7d6c5b4a39281706f5e4d3c2b1a0",
        "chief_complaint": "肚子疼三天了，还有点拉肚子",
        "status": "IN_PROGRESS",
        "risk_flag": false,
        "inquiry_rounds": 3,
        "started_time": "2026-10-15T19:23:41+08:00"
      }
    ]
  },
  "message": "成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `patient_display` | string | 患者脱敏展示名，**不使用姓名原文** |
| `status` | string | 会话状态，见 6.3 节枚举字典 |
| `risk_flag` | boolean | 高风险标记，`true` 时前端须显著提示（`F22`、`AC-F14-3`） |

**错误码**

| code | message | 说明 |
|---|---|---|
| `401` | 未认证 | 缺少令牌 |
| `403` | 无权限 | 非医生角色调用 |
| `400` | 参数校验失败 | `sort_by` 不在白名单，或日期格式错误 |

**业务规则**

- **只返回当前医生接诊的患者**（`R07`、`AC-F14-1`）——过滤下推到 SQL，不在应用层筛选（`AC-F14-2`）
- 分页每页不超过 100 条（`AC-F14-2`）
- `sort_by` 只接受白名单字段，防止对未索引字段排序

**幂等性**：天然幂等 ｜ **限流**：默认 600 次 / 分钟

**示例请求**

```bash
curl -X GET "https://medical-guidance.example.com/api/v1/doctor/encounters?page=1&size=20&status=PENDING_TAKEOVER" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### 12.5.2 查询会话详情（医生视图）

**接口路径**：`GET /api/v1/doctor/sessions/{session_id}`
**功能说明**：查询会话的完整状态与预问诊摘要（对应 `F15`）
**权限要求**：`DOCTOR`（仅自己接诊的患者）

**请求头**：`Authorization` 是

**路径参数**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `session_id` | string | 是 | 会话标识 |

**查询参数**：无 ｜ **请求体**：无

**响应示例**

```json
{
  "code": 200,
  "data": {
    "session_id": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
    "session_no": "S20261015000001",
    "status": "FINISHED",
    "risk_flag": false,
    "chief_complaint": "肚子疼三天了，还有点拉肚子",
    "inquiry_rounds": 3,
    "patient": {
      "patient_id": "d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9",
      "patient_hash": "9f8e7d6c5b4a39281706f5e4d3c2b1a0",
      "patient_display": "患者 8000",
      "age": 45,
      "gender": "男"
    },
    "triage_status": {
      "has_result": true,
      "route": "DIRECT",
      "doctor_confirmed": false
    },
    "symptom_timeline": [
      {"time_label": "3 天前", "event": "出现中上腹持续性疼痛"},
      {"time_label": "2 天前", "event": "出现腹泻，每日 3~4 次"},
      {"time_label": "今日", "event": "症状未缓解，伴恶心"}
    ],
    "consent_granted": true,
    "consent_scope_label": "近两年门诊与住院记录",
    "started_time": "2026-10-15T19:23:41+08:00",
    "finished_time": "2026-10-15T19:28:12+08:00"
  },
  "message": "成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `patient` | object | 患者信息（脱敏形式） |
| `triage_status.has_result` | boolean | 是否已产出分诊结论 |
| `symptom_timeline` | array | 症状时间线，**按时间升序**（`AC-F15-2`） |
| `consent_granted` | boolean | 患者是否已授权调阅既往病历 |

**错误码**

| code | message | 说明 |
|---|---|---|
| `404` | 资源不存在 | 会话不存在或非本人接诊 |
| `403` | 无权限 | 非医生角色 |
| `401` | 未认证 | 缺少令牌 |

**业务规则**

- **越权访问返回 `403` 并写审计日志**（`AC-F15-1`）——与患者端的 `404` 策略不同，因为医生是院内用户，明确区分"无权限"更能帮助定位问题
- 症状时间线基于对话内容与实体抽取结果生成，**不只是一段无结构文本**
- 未完成预问诊的会话也可查询，`triage_status.has_result` 为 `false`

**幂等性**：天然幂等 ｜ **限流**：默认 600 次 / 分钟

**示例请求**

```bash
curl -X GET "https://medical-guidance.example.com/api/v1/doctor/sessions/a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### 12.5.3 查询完整对话记录

**接口路径**：`GET /api/v1/doctor/sessions/{session_id}/messages`
**功能说明**：分页查询会话的完整对话记录，含系统内部消息（对应 `F20`）
**权限要求**：`DOCTOR`（仅自己接诊的患者）

**请求头**：`Authorization` 是

**路径参数**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `session_id` | string | 是 | 会话标识 |

**查询参数**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `page` | integer | 否 | `1` | 页码 |
| `size` | integer | 否 | `100` | 每页条数，1~100 |
| `include_system` | boolean | 否 | `true` | 是否包含 `SYSTEM` 角色的内部消息 |

**请求体**：无

**响应示例**

```json
{
  "code": 200,
  "data": {
    "total": 8,
    "page": 1,
    "size": 100,
    "items": [
      {
        "message_id": "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7",
        "seq_no": 2,
        "role": "AI",
        "content": "请问疼痛是持续性的还是阵发性的？",
        "msg_type": "TEXT",
        "extra": {"node": "INQUIRY", "askable_slots": ["duration", "location"]},
        "send_time": "2026-10-15T19:23:44+08:00"
      },
      {
        "message_id": "c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8",
        "seq_no": 3,
        "role": "SYSTEM",
        "content": "危重症三层识别：未命中",
        "msg_type": "TEXT",
        "extra": {"node": "SAFETY_CHECK", "duration_ms": 42, "matched_layer": null},
        "send_time": "2026-10-15T19:23:44+08:00"
      }
    ]
  },
  "message": "成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `extra.node` | string | 产生该消息的编排节点标识 |
| `extra.duration_ms` | integer | 节点耗时（`SYSTEM` 消息带此字段） |

**错误码**

| code | message | 说明 |
|---|---|---|
| `404` | 资源不存在 | 会话不存在或非本人接诊 |
| `401` | 未认证 | 缺少令牌 |

**业务规则**

- 医生可见 `include_system=true` 时的**内部消息**（如危重症识别过程），便于判断分诊依据
- 按 `seq_no` 升序；`seq_no` 是顺序的唯一依据
- 接管队列中的会话**也可查询完整记录**（`AC-F20-3` 要求"非摘要"）

**幂等性**：天然幂等 ｜ **限流**：默认 600 次 / 分钟

**示例请求**

```bash
curl -X GET "https://medical-guidance.example.com/api/v1/doctor/sessions/a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6/messages?page=1&size=100&include_system=true" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### 12.5.4 查询 SOAP 病历（医生视图）

**接口路径**：`GET /api/v1/doctor/sessions/{session_id}/emr`
**功能说明**：查询完整 SOAP 预问诊病历，含评估段与来源标注（对应 `F16`）
**权限要求**：`DOCTOR`（仅自己接诊的患者）

**请求头**：`Authorization` 是

**路径参数**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `session_id` | string | 是 | 会话标识 |

**查询参数**：无 ｜ **请求体**：无

**响应示例**

```json
{
  "code": 200,
  "data": {
    "emr_record_id": "c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8",
    "schema_version": "1.0",
    "generate_status": "SUCCESS",
    "completeness_rate": 0.96,
    "subjective": {
      "chief_complaint": "肚子疼三天了，还有点拉肚子",
      "present_illness": "3 天前无明显诱因出现中上腹持续性疼痛，伴腹泻、恶心，无发热。",
      "past_history": [
        {"content": "高血压 5 年，规律服药", "source": "EMR", "source_time": "2026-08-12"}
      ],
      "allergy": [
        {"content": "青霉素过敏", "source": "EMR", "source_time": "2025-11-03"}
      ]
    },
    "objective": {
      "collected_vitals": [],
      "note": "本次为线上预问诊，未采集体格检查数据"
    },
    "assessment": {
      "differential_directions": [
        {"dept_code": "DIG", "confidence": 0.8731, "basis": ["中上腹持续性疼痛", "伴腹泻与恶心"]},
        {"dept_code": "GEN_SURG", "confidence": 0.6204, "basis": ["腹痛持续 3 天未缓解"]}
      ],
      "note": "以上为鉴别方向参考，不构成诊断"
    },
    "plan": {
      "recommended_depts": ["消化内科"],
      "suggested_workup": ["如症状持续，建议到院后完善血常规与腹部超声"],
      "note": "以上为就诊建议，不构成诊断"
    },
    "disclaimer": "本系统仅提供分诊建议，不构成医学诊断。请以医生面诊为准。",
    "generated_time": "2026-10-15T19:28:15+08:00"
  },
  "message": "成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `completeness_rate` | number | 字段完整率，0~1。目标不低于 0.95 |
| `subjective.past_history[].source` | string | 数据来源：`EMR` 既往病历 / `ASK` 对话采集 |
| `subjective.past_history[].source_time` | string | 来源记录时点。**来源为 EMR 时必须标注**（`AC-F16-2`） |
| `assessment` | object | A 段：**仅医生视图可见**，含鉴别方向与依据（`R02`） |

**错误码**

| code | message | 说明 |
|---|---|---|
| `404` | 资源不存在 | 会话或病历不存在，或非本人接诊 |
| `20006` | 分诊结论尚未生成 | 病历尚未生成 |
| `401` | 未认证 | 缺少令牌 |

**业务规则**

- 医生视图**保留疾病名称与鉴别方向**（`R02`、`AC-F54-3`），与患者视图的关键差异
- **仍不返回用药建议与处方内容**（`R11`、`AC-F36-4`）
- 既往史来源为 EMR 时**必须标注来源与时点**（`AC-F36-3`）
- `generate_status = PARTIAL` 时表示部分字段缺失，`message` 中说明缺失项，**不伪造内容**

**幂等性**：天然幂等 ｜ **限流**：默认 600 次 / 分钟

**示例请求**

```bash
curl -X GET "https://medical-guidance.example.com/api/v1/doctor/sessions/a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6/emr" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### 12.5.5 查询鉴别诊断候选与依据

**接口路径**：`GET /api/v1/doctor/sessions/{session_id}/diagnosis`
**功能说明**：查询鉴别诊断候选列表（按置信度降序）及每个候选的判断依据，并附带用药禁忌校验结果（对应 `F17`、`F47`）
**权限要求**：`DOCTOR`（仅自己接诊的患者）

**请求头**：`Authorization` 是

**路径参数**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `session_id` | string | 是 | 会话标识 |

**查询参数**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `include_mdt` | boolean | 否 | `true` | 是否包含多学科会诊信息 |

**请求体**：无

**响应示例**

```json
{
  "code": 200,
  "data": {
    "triage_result_id": "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7",
    "retrieval_mode": "HYBRID",
    "kb_version": "kb-v2026.10.15",
    "candidates": [
      {
        "rank": 1,
        "dept_code": "DIG",
        "dept_name": "消化内科",
        "confidence": 0.8731,
        "hit_symptoms": ["中上腹持续性疼痛", "腹泻", "恶心"],
        "guideline_refs": [
          {"guideline_id": "GL-DIG-0021", "title": "急性胃肠炎诊疗要点", "publish_year": 2023, "evidence_level": "B"}
        ]
      },
      {
        "rank": 2,
        "dept_code": "GEN_SURG",
        "dept_name": "普通外科",
        "confidence": 0.6204,
        "hit_symptoms": ["腹痛持续 3 天未缓解"],
        "guideline_refs": []
      }
    ],
    "mdt": {
      "triggered": true,
      "candidate_depts": ["DIG", "GEN_SURG", "GYN"],
      "opinion_count": 3,
      "missing_count": 0,
      "duration_ms": 8420,
      "divergence": {
        "exists": true,
        "items": [
          {
            "dept_code": "GYN",
            "dept_name": "妇科",
            "opinion": "建议排除妇科急腹症",
            "reason": "育龄女性腹痛需考虑妇科来源",
            "confidence": 0.4412
          }
        ]
      },
      "consensus_dept": "DIG",
      "consensus_confidence": 0.7102
    },
    "drug_safety": {
      "checked": true,
      "allergy_hits": [
        {"drug_name": "阿莫西林", "allergy_item": "青霉素", "severity": "HIGH", "suggestion": "禁用"}
      ],
      "contraindication_hits": [],
      "note": "校验结果仅供参考，最终用药决策由医生负责"
    }
  },
  "message": "成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `retrieval_mode` | string | 本次采用的检索模式：`DENSE` / `SPARSE` / `HYBRID` |
| `kb_version` | string | 决策依据的知识库版本，用于事后复盘 |
| `candidates[].confidence` | number | 置信度，列表**按此降序**（`AC-F17-2`） |
| `candidates[].hit_symptoms` | array | 命中的症状依据 |
| `candidates[].guideline_refs` | array | 引用的指南条目；**为空表示依据不足，须标注而非隐藏** |
| `mdt.divergence.exists` | boolean | **是否存在分歧**。`true` 时前端须展示分歧区块（`AC-F17-3`） |
| `drug_safety` | object | **用药禁忌校验结果（`F47`）**。由患者过敏史与知识库中的用药禁忌条目比对得到 |
| `drug_safety.checked` | boolean | 是否成功执行了校验。**为 `false` 时前端必须显式提示"未完成禁忌校验"**，不得静默略过 |
| `drug_safety.allergy_hits` | array | 过敏冲突项。`severity` 取值 `HIGH` / `MEDIUM` / `LOW` |
| `drug_safety.contraindication_hits` | array | 禁忌症冲突项 |
| `drug_safety.note` | string | 固定说明文案，声明校验结果不构成用药建议 |

**错误码**

| code | message | 说明 |
|---|---|---|
| `404` | 资源不存在 | 会话不存在或非本人接诊 |
| `20006` | 分诊结论尚未生成 | 结论尚未产出 |
| `403` | 无权限 | 非医生角色（**患者角色调用必定被拒**，`AC-F17-4`、`R01`） |
| `401` | 未认证 | 缺少令牌 |

**业务规则**

- **本接口仅医生可访问**：患者角色调用返回 `403`（`R01`、`AC-F17-4`）
- 候选按置信度**降序**返回（`AC-F17-2`）
- 每个候选附**至少 1 条命中的症状依据**（`AC-F17-1`）
- **MDT 存在分歧时必须显式返回 `divergence` 区块**，不得在汇总时抹平（`AC-F35-2`）
- 依据不足的候选**标注"依据不足"**（`guideline_refs` 为空），不隐藏该候选
- `drug_safety` **不得返回任何用药建议或处方内容**（`R11`、`NFR65`）——只呈现冲突事实与禁用/慎用结论，不给替代药品建议
- `checked=false`（知识库不可用或患者过敏史缺失）时**必须显式告知医生校验未完成**，不得返回空数组让调用方误判为"无冲突"

**幂等性**：天然幂等 ｜ **限流**：默认 600 次 / 分钟

**示例请求**

```bash
curl -X GET "https://medical-guidance.example.com/api/v1/doctor/sessions/a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6/diagnosis?include_mdt=true" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### 12.5.6 确认分诊建议

**接口路径**：`POST /api/v1/doctor/sessions/{session_id}/confirm`
**功能说明**：医生确认系统给出的分诊建议（对应 `F18`）
**权限要求**：`DOCTOR`（仅自己接诊的患者）

**请求头**：`Authorization` 是 ｜ `Content-Type` 是 ｜ `Idempotency-Key` 建议

**路径参数**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `session_id` | string | 是 | 会话标识 |

**查询参数**：无

**请求体**

```json
{
  "note": "结合症状描述，同意分诊至消化内科"
}
```

**请求体字段说明**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `note` | string | 否 | 确认备注，不超过 200 字 |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "session_id": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
    "triage_result_id": "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7",
    "doctor_confirmed": true,
    "confirmed_time": "2026-10-15T19:35:02+08:00",
    "dept_code": "DIG",
    "dept_name": "消化内科",
    "snapshot_saved": true
  },
  "message": "已确认分诊建议"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `doctor_confirmed` | boolean | 恒为 `true` |
| `snapshot_saved` | boolean | 是否已保存结论快照。**必须为 `true`**（`AC-F18-2`） |

**错误码**

| code | message | 说明 |
|---|---|---|
| `404` | 资源不存在 | 会话不存在或非本人接诊 |
| `20006` | 分诊结论尚未生成 | 无结论可确认 |
| `20008` | 该会话已被其他医生接管 | 会话归属已变更 |
| `409` | 资源冲突 | 幂等键处理中 |
| `401` | 未认证 | 缺少令牌 |

**业务规则**

- **保存结论快照**：确认记录含当时的结论完整副本（`AC-F18-2`），结论后续若被规则调整不影响历史
- **幂等**：重复确认只产生 1 条记录（`AC-F18-1`）
- 会话状态已变更（被他人接管）时返回 `20008`，客户端应刷新列表
- 确认动作写审计日志（`action_type = 'TRIAGE_CONFIRM'`）

**幂等性**：支持
**限流**：60 次 / 分钟

**示例请求**

```bash
curl -X POST "https://medical-guidance.example.com/api/v1/doctor/sessions/a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6/confirm" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: 7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d" \
  -d '{"note": "结合症状描述，同意分诊至消化内科"}'
```

#### 12.5.7 修正分诊建议

**接口路径**：`POST /api/v1/doctor/sessions/{session_id}/correct`
**功能说明**：医生修正分诊建议的科室并填写理由，修正记录留存为评测样本（对应 `F19`）
**权限要求**：`DOCTOR`（仅自己接诊的患者）

**请求头**：`Authorization` 是 ｜ `Content-Type` 是 ｜ `Idempotency-Key` 建议

**路径参数**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `session_id` | string | 是 | 会话标识 |

**查询参数**：无

**请求体**

```json
{
  "after_dept": "GEN_SURG",
  "reason": "患者疼痛位置偏右下腹，且伴反跳痛描述，需优先排除外科急腹症"
}
```

**请求体字段说明**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `after_dept` | string | 是 | 修正后的科室编码，须存在于当前租户的科室表 |
| `reason` | string | 是 | 修正理由，**不少于 10 字**（`AC-F19-3`） |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "correction_id": "f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2",
    "before_dept": "DIG",
    "before_dept_name": "消化内科",
    "after_dept": "GEN_SURG",
    "after_dept_name": "普通外科",
    "doctor_title": "副主任医师",
    "usable_for_eval": true,
    "created_time": "2026-10-15T19:37:20+08:00"
  },
  "message": "修正已记录"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `doctor_title` | string | 修正人职称（**快照存储**），用于采纳判定 |
| `usable_for_eval` | boolean | 是否可用于评测。**副主任医师及以上为 `true`**（`AC-F19-2`） |

**错误码**

| code | message | 说明 |
|---|---|---|
| `404` | 资源不存在 | 会话不存在或非本人接诊 |
| `20010` | 修正理由不满足要求 | 理由少于 10 字 |
| `20011` | 修正前后科室相同 | 未发生实际修正（`AC-F19-3` 关联规则） |
| `400` | 参数校验失败 | `after_dept` 不存在于当前租户科室表 |
| `401` | 未认证 | 缺少令牌 |

**业务规则**

- 修正记录是**评测样本的唯一来源**（`F19`）
- `doctor_title` **快照存储**：即使该医生后续职称变更，历史修正的采纳判定仍按当时职称计算
- `usable_for_eval` 在写入时计算，**住院医师的修正记录被标记为 `false`**（`AC-F19-2`）
- 修正理由少于 10 字无法提交（`AC-F19-3`）
- 修正动作写审计日志（`action_type = 'TRIAGE_CORRECT'`）

**幂等性**：支持
**限流**：60 次 / 分钟

**示例请求**

```bash
curl -X POST "https://medical-guidance.example.com/api/v1/doctor/sessions/a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6/correct" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: 9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f" \
  -d '{
    "after_dept": "GEN_SURG",
    "reason": "患者疼痛位置偏右下腹，且伴反跳痛描述，需优先排除外科急腹症"
  }'
```

#### 12.5.8 查询待接管队列

**接口路径**：`GET /api/v1/doctor/takeover-queue`
**功能说明**：查询被系统转人工的会话队列，按等待时长升序（对应 `F20`）
**权限要求**：`DOCTOR`

**请求头**：`Authorization` 是

**路径参数**：无

**查询参数**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `page` | integer | 否 | `1` | 页码 |
| `size` | integer | 否 | `20` | 每页条数，1~100 |
| `only_mine` | boolean | 否 | `false` | 是否只看本科室的会话 |
| `min_wait_seconds` | integer | 否 | — | 最短等待秒数，用于筛选积压较久的会话 |

**请求体**：无

**响应示例**

```json
{
  "code": 200,
  "data": {
    "total": 6,
    "page": 1,
    "size": 20,
    "items": [
      {
        "session_id": "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7",
        "session_no": "S20261015000002",
        "patient_display": "患者 3921",
        "chief_complaint": "头晕乏力一周",
        "route": "MANUAL",
        "confidence": 0.4128,
        "inquiry_rounds": 5,
        "wait_seconds": 428,
        "wait_label": "7 分 8 秒",
        "started_time": "2026-10-15T18:05:12+08:00"
      }
    ],
    "backlog_warning": true,
    "backlog_threshold": 5
  },
  "message": "成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `route` | string | 转入队列的原因：`MANUAL` 低置信度 / `EMERGENCY` 危重症 |
| `confidence` | number | 触发转人工时的置信度 |
| `wait_seconds` | integer | 已等待秒数 |
| `backlog_warning` | boolean | **是否积压超阈值**。`true` 时前端须顶部告警（`AC-F20-2` 关联规则） |

**错误码**

| code | message | 说明 |
|---|---|---|
| `401` | 未认证 | 缺少令牌 |
| `403` | 无权限 | 非医生角色 |

**业务规则**

- **队列按等待时长升序**（等待最久优先），由部分索引直接支持（`AC-F20-1`）
- 队列积压超过阈值时 `backlog_warning=true`，前端展示告警
- 已被接管的会话**不在队列中**（`AC-F20-2`）
- 患者已自行结束的会话标记为 `CLOSED` 并从队列移除

**幂等性**：天然幂等 ｜ **限流**：默认 600 次 / 分钟

**示例请求**

```bash
curl -X GET "https://medical-guidance.example.com/api/v1/doctor/takeover-queue?page=1&size=20&only_mine=false" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### 12.5.9 接管会话

**接口路径**：`POST /api/v1/doctor/takeover-queue/{session_id}/take`
**功能说明**：医生从待接管队列中接管一个会话（对应 `F20`）
**权限要求**：`DOCTOR`

**请求头**：`Authorization` 是 ｜ `Content-Type` 是

**路径参数**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `session_id` | string | 是 | 会话标识 |

**查询参数**：无

**请求体**

```json
{
  "note": "开始接管处理"
}
```

**请求体字段说明**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `note` | string | 否 | 接管备注，不超过 200 字 |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "session_id": "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7",
    "status": "TAKEN_OVER",
    "doctor_id": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
    "doctor_name": "张明",
    "taken_over_time": "2026-10-15T19:40:11+08:00"
  },
  "message": "已接管"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `status` | string | 接管后状态，固定 `TAKEN_OVER` |
| `doctor_id` | string | 接管医生的用户标识 |

**错误码**

| code | message | 说明 |
|---|---|---|
| `404` | 资源不存在 | 会话不存在或不在队列中 |
| `20008` | 该会话已被其他医生接管 | **并发冲突**：两人同时点击只有一人成功（`AC-F20-2`） |
| `20009` | 会话不在待接管状态 | 状态已变更 |
| `401` | 未认证 | 缺少令牌 |

**业务规则**

- **并发接管只有一人成功**（`AC-F20-2`）：通过状态与接管人字段的条件更新实现，失败方返回 `20008`
- 接管后会话从队列移除，并归属该医生
- 接管动作写审计日志

**幂等性**：天然幂等（同一医生重复接管返回相同结果）
**限流**：60 次 / 分钟

**示例请求**

```bash
curl -X POST "https://medical-guidance.example.com/api/v1/doctor/takeover-queue/b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7/take" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{"note": "开始接管处理"}'
```

### 12.6 医生端 · 病历与患者

#### 12.6.1 查阅患者既往病历

**接口路径**：`GET /api/v1/doctor/patients/{patient_id}/records`
**功能说明**：双路查阅患者既往病历——结构化字段精确查询 + 病历文书语义检索（对应 `F21`、`F45`、`F46`）
**权限要求**：`DOCTOR`（仅自己接诊的患者）

**请求头**：`Authorization` 是

**路径参数**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `patient_id` | string | 是 | 患者标识 |

**查询参数**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `category` | string | 是 | — | 查询类别：`DIAGNOSIS` 诊断 / `LAB` 检验 / `MEDICATION` 用药 / `ALLERGY` 过敏史 / `DOCUMENT` 病历文书 |
| `keywords` | string | 否 | — | 语义检索关键词（`category=DOCUMENT` 时使用） |
| `dept_codes` | string | 否 | — | 科室编码，多值逗号分隔 |
| `test_codes` | string | 否 | — | 检验项目码（`category=LAB` 时使用） |
| `doc_types` | string | 否 | — | 文书类型（`category=DOCUMENT` 时使用） |
| `start_date` | string | 否 | — | 记录日期起 |
| `end_date` | string | 否 | — | 记录日期止 |
| `page` | integer | 否 | `1` | 页码 |
| `size` | integer | 否 | `20` | 每页条数，1~100 |

**请求体**：无

**响应示例**（`category=DOCUMENT`）

```json
{
  "code": 200,
  "data": {
    "total": 8,
    "page": 1,
    "size": 20,
    "retrieval_mode": "HYBRID",
    "items": [
      {
        "document_id": "a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2",
        "doc_type": "OUTPATIENT",
        "doc_title": "消化内科门诊病历",
        "dept_code": "DIG",
        "record_time": "2026-08-12T10:15:00+08:00",
        "sections": [
          {"section": "PRESENT_ILLNESS", "content": "患者因上腹隐痛 2 周就诊…", "score": 0.8123}
        ],
        "icd10_codes": ["K29.7"]
      }
    ]
  },
  "message": "成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `retrieval_mode` | string | 检索模式。`category=DOCUMENT` 时为语义检索模式；其余类别为 `null` |
| `items[].sections` | array | 命中的文书小节及相似度。**按记录时间倒序，近期记录优先**（`AC-F21-3`） |
| `items[].icd10_codes` | array | 涉及疾病编码 |

**错误码**

| code | message | 说明 |
|---|---|---|
| `404` | 资源不存在 | 患者不存在或非本人接诊 |
| `20012` | 患者未授权调阅既往病历 | **缺少有效授权**（`AC-F21-2`） |
| `60001` | 病历系统不可用 | EMR 不可用；**不影响预问诊摘要** |
| `60002` | 病历调阅失败 | EMR 返回异常 |
| `401` | 未认证 | 缺少令牌 |

**业务规则**

- **结构化类别使用精确查询，不走相似度匹配**（`AC-F21-1`、`F45`）——诊断、检验值这类数据近似即错误
- **文书类别使用语义检索**，含**时间衰减重排**（架构文档 §5.3）
- **未授权时返回 `20012`，且不产生任何 EMR 调用**（`AC-F21-2`）
- EMR 不可用返回 `60001`，客户端应展示"既往病历暂不可用"，**不影响预问诊摘要展示**
- 检索无结果时返回空 `items`，**不返回错误**
- 本接口调用写审计日志（`action_type = 'EMR_READ'`）

**幂等性**：天然幂等 ｜ **限流**：默认 600 次 / 分钟

**示例请求**

```bash
curl -X GET "https://medical-guidance.example.com/api/v1/doctor/patients/d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9/records?category=DOCUMENT&keywords=%E8%85%B9%E7%97%9B&start_date=2025-10-15&end_date=2026-10-15&page=1&size=20" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### 12.6.2 查询患者预问诊摘要列表

**接口路径**：`GET /api/v1/doctor/patients/{patient_id}/summaries`
**功能说明**：查询该患者在本院的历次预问诊摘要（对应 `F15`、`F21`）
**权限要求**：`DOCTOR`（仅自己接诊的患者）

**请求头**：`Authorization` 是

**路径参数**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `patient_id` | string | 是 | 患者标识 |

**查询参数**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `page` | integer | 否 | `1` | 页码 |
| `size` | integer | 否 | `20` | 每页条数，1~100 |
| `start_date` | string | 否 | — | 开始日期 |
| `end_date` | string | 否 | — | 结束日期 |

**请求体**：无

**响应示例**

```json
{
  "code": 200,
  "data": {
    "total": 2,
    "page": 1,
    "size": 20,
    "items": [
      {
        "session_id": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
        "session_no": "S20261015000001",
        "chief_complaint": "肚子疼三天了，还有点拉肚子",
        "dept_code": "DIG",
        "dept_name": "消化内科",
        "route": "DIRECT",
        "inquiry_rounds": 3,
        "started_time": "2026-10-15T19:23:41+08:00"
      }
    ]
  },
  "message": "成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `route` | string | 当次的分诊路由去向 |

**错误码**

| code | message | 说明 |
|---|---|---|
| `404` | 资源不存在 | 患者不存在或非本人接诊 |
| `403` | 无权限 | 非医生角色 |
| `401` | 未认证 | 缺少令牌 |

**业务规则**

- 只返回**当前医生接诊过的**该患者的会话（行级隔离）
- 按开始时间倒序
- 该接口**不涉及 EMR 调阅**，因此不需要患者授权

**幂等性**：天然幂等 ｜ **限流**：默认 600 次 / 分钟

**示例请求**

```bash
curl -X GET "https://medical-guidance.example.com/api/v1/doctor/patients/d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9/summaries?page=1&size=20" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### 12.7 知识库管理

> 本模块全部接口权限要求：**`KB_ADMIN`**（`ORG_ADMIN` 仅具备读权限）。统一限流 **600 次 / 分钟**，写接口支持 `Idempotency-Key`。

#### 12.7.1 查询知识库条目列表

**接口路径**：`GET /api/v1/admin/kb/entries`
**功能说明**：按知识类型、科室、状态筛选条目，支持关键词搜索与分页（对应 `F24`）

**请求头**：`Authorization` 是

**路径参数**：无

**查询参数**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `page` / `size` | integer | 否 | `1` / `20` | 分页，`size` 上限 100 |
| `kb_type` | string | 否 | — | 知识类型，见 6.3 节枚举字典 |
| `dept_code` | string | 否 | — | 科室编码 |
| `status` | string | 否 | — | 状态：`0` 草稿 / `1` 已发布 / `2` 已停用 |
| `is_active` | boolean | 否 | — | 是否参与检索 |
| `keyword` | string | 否 | — | 关键词，匹配标题与正文 |
| `sort_by` | string | 否 | `update_time` | 白名单：`update_time` / `entry_code` / `create_time` |
| `sort_order` | string | 否 | `desc` | `asc` / `desc` |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "total": 512,
    "page": 1,
    "size": 20,
    "items": [
      {
        "entry_id": "e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6",
        "entry_code": "DEPT-DIG-001",
        "kb_type": "DEPT_EXPERTISE",
        "title": "消化内科",
        "dept_code": "DIG",
        "dept_name": "消化内科",
        "status": "1",
        "is_active": true,
        "entry_version": "2026-09-01",
        "update_time": "2026-10-14T11:02:33+08:00"
      }
    ]
  },
  "message": "成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `entry_id` | string | 条目标识 |
| `entry_code` | string | 条目标识编码，**入库幂等键** |
| `status` | string | 状态码，取值见 6.3 节 |
| `is_active` | boolean | 是否参与检索。**与 `status` 是两个不同维度** |

**错误码**

| code | message | 说明 |
|---|---|---|
| `401` | 未认证 | 缺少令牌 |
| `403` | 无权限 | 非知识库管理员或机构管理员 |
| `400` | 参数校验失败 | `sort_by` 不在白名单 |

**业务规则**

- 默认只返回**当前租户**的条目与**全局共享**条目
- 筛选与搜索下推到 SQL，不在应用层过滤（`AC-F24-1`）
- `page * size` 超过 10000 时返回 `400`

**示例请求**

```bash
curl -X GET "https://medical-guidance.example.com/api/v1/admin/kb/entries?page=1&size=20&kb_type=DEPT_EXPERTISE&status=1" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### 12.7.2 新增知识库条目

**接口路径**：`POST /api/v1/admin/kb/entries`
**功能说明**：新增一条知识库条目（对应 `F25`）

**请求头**：`Authorization` 是 ｜ `Content-Type` 是 ｜ `Idempotency-Key` 建议

**请求体**

```json
{
  "entry_code": "DEPT-DIG-019",
  "kb_type": "DEPT_EXPERTISE",
  "title": "消化内科 · 胰腺疾病亚专科",
  "content": "诊治急性胰腺炎、慢性胰腺炎、胰腺肿瘤等疾病。门诊常见主诉：上腹剧痛向腰背放射、脂肪泻、体重下降。",
  "content_json": {
    "dept_code": "DIG",
    "sub_specialty": ["胰胆疾病"],
    "common_complaints": ["上腹剧痛", "腰背放射痛", "脂肪泻"]
  },
  "dept_code": "DIG",
  "icd10_codes": ["K85.9"],
  "age_group": "all",
  "gender": "0",
  "source": "院内科室简介_v4",
  "entry_version": "2026-10-15"
}
```

**请求体字段说明**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `entry_code` | string | 是 | 条目标识，租户内唯一，不超过 128 字符 |
| `kb_type` | string | 是 | 知识类型 |
| `content` | string | 是 | 正文，用于向量化与全文检索 |
| `content_json` | object | 否 | 结构化附加内容，**按知识类型不同** |
| `dept_code` | string | 否 | 归属科室，**须存在于当前租户科室表** |
| `icd10_codes` | array | 否 | 疾病编码列表 |
| `age_group` | string | 否 | `child` / `adult` / `elderly` / `all`，默认 `all` |
| `gender` | string | 否 | `1` 男 / `2` 女 / `0` 通用，默认 `0` |
| `source` | string | 否 | 来源说明 |
| `entry_version` | string | 否 | 条目版本 |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "entry_id": "f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7",
    "entry_code": "DEPT-DIG-019",
    "status": "0",
    "is_active": false,
    "history_id": "a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8",
    "created_time": "2026-10-15T19:45:00+08:00"
  },
  "message": "新增成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `status` | string | 新条目初始状态为 `0`（草稿） |
| `is_active` | boolean | 初始为 `false`，**需发布后才参与检索** |
| `history_id` | string | 本次变更的历史记录标识（`AC-F25-2`） |

**错误码**

| code | message | 说明 |
|---|---|---|
| `40002` | 条目标识已存在 | `entry_code` 唯一性冲突 |
| `40003` | 条目标识不存在 | 引用的 `dept_code` 或编码不存在 |
| `40005` | 条目校验失败 | 必填项缺失或字段格式不符 |
| `403` | 无权限 | 非知识库管理员 |
| `401` | 未认证 | 缺少令牌 |

**业务规则**

- 新增后状态为**草稿**（`status=0`），不参与检索
- 保存成功时**恰好新增 1 条变更历史**（`AC-F25-2`）
- **引用完整性校验**：`dept_code` 与 `icd10_codes` 须存在，否则拒绝保存（`AC-F25-3`）
- 写审计日志（`action_type = 'KB_CHANGE'`）

**示例请求**

```bash
curl -X POST "https://medical-guidance.example.com/api/v1/admin/kb/entries" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9" \
  -d '{
    "entry_code": "DEPT-DIG-019",
    "kb_type": "DEPT_EXPERTISE",
    "title": "消化内科 · 胰腺疾病亚专科",
    "content": "诊治急性胰腺炎、慢性胰腺炎、胰腺肿瘤等疾病。",
    "dept_code": "DIG",
    "icd10_codes": ["K85.9"],
    "source": "院内科室简介_v4",
    "entry_version": "2026-10-15"
  }'
```

#### 12.7.3 查询条目详情

**接口路径**：`GET /api/v1/admin/kb/entries/{entry_id}`
**功能说明**：查询单条知识库条目的完整内容（对应 `F24`）

**路径参数**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `entry_id` | string | 是 | 条目标识 |

**查询参数**：无

**响应示例**

```json
{
  "code": 200,
  "data": {
    "entry_id": "e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6",
    "entry_code": "DEPT-DIG-001",
    "kb_type": "DEPT_EXPERTISE",
    "kb_type_label": "科室专长",
    "title": "消化内科",
    "content": "诊治食管、胃、十二指肠、小肠、结肠、肝、胆、胰腺疾病。下设炎症性肠病、肝病、胰胆疾病三个亚专科。",
    "content_json": {
      "dept_code": "DIG",
      "sub_specialty": ["炎症性肠病", "肝病", "胰胆疾病"],
      "common_complaints": ["上腹痛", "反酸", "腹泻", "黄疸"]
    },
    "dept_code": "DIG",
    "dept_name": "消化内科",
    "icd10_codes": ["K25.9", "K29.7"],
    "age_group": "all",
    "gender": "0",
    "source": "院内科室简介_v3",
    "entry_version": "2026-09-01",
    "status": "1",
    "status_label": "已发布",
    "is_active": true,
    "create_by": "kbadmin",
    "create_time": "2026-09-01T09:12:00+08:00",
    "update_by": "kbadmin",
    "update_time": "2026-10-14T11:02:33+08:00"
  },
  "message": "成功"
}
```

**错误码**

| code | message | 说明 |
|---|---|---|
| `40001` | 知识库条目不存在 | `entry_id` 无效 |
| `404` | 资源不存在 | 条目属于其他租户 |
| `401` | 未认证 | 缺少令牌 |

**业务规则**：返回完整字段含 `content_json`（列表接口不返回该字段以减小响应体积）

**示例请求**

```bash
curl -X GET "https://medical-guidance.example.com/api/v1/admin/kb/entries/e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### 12.7.4 修改知识库条目

**接口路径**：`PUT /api/v1/admin/kb/entries/{entry_id}`
**功能说明**：全量更新条目内容（对应 `F25`）

**路径参数**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `entry_id` | string | 是 | 条目标识 |

**请求体**

```json
{
  "title": "消化内科 · 含胰胆亚专科",
  "content": "诊治食管、胃、十二指肠、小肠、结肠、肝、胆、胰腺疾病。下设炎症性肠病、肝病、胰胆疾病三个亚专科。新增：常见主诉含消瘦与脂肪泻。",
  "content_json": {
    "dept_code": "DIG",
    "sub_specialty": ["炎症性肠病", "肝病", "胰胆疾病"],
    "common_complaints": ["上腹痛", "反酸", "腹泻", "黄疸", "消瘦", "脂肪泻"]
  },
  "dept_code": "DIG",
  "icd10_codes": ["K25.9", "K29.7", "K85.9"],
  "source": "院内科室简介_v4",
  "entry_version": "2026-10-15",
  "expected_update_time": "2026-10-14T11:02:33+08:00"
}
```

**请求体字段说明**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `expected_update_time` | string | 否 | **乐观锁**：传入查询到的 `update_time`，若已被他人修改则拒绝保存（`AC-F25-4`） |
| 其余字段 | — | 否 | 同 12.7.2，未传的字段保持原值 |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "entry_id": "e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6",
    "entry_version": "2026-10-15",
    "changed_fields": ["title", "content", "common_complaints", "icd10_codes", "entry_version"],
    "history_id": "b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9",
    "update_time": "2026-10-15T19:50:12+08:00"
  },
  "message": "修改成功"
}
```

**错误码**

| code | message | 说明 |
|---|---|---|
| `40001` | 知识库条目不存在 | `entry_id` 无效 |
| `409` | 资源冲突 | **乐观锁失败**：`expected_update_time` 与当前不一致 |
| `40003` | 条目标识不存在 | 引用完整性校验失败 |
| `40005` | 条目校验失败 | 必填项缺失 |
| `401` | 未认证 | 缺少令牌 |

**业务规则**

- 修改成功后新增 **1 条变更历史**，含变更前后快照与 `changed_fields`
- **乐观锁**：并发编辑时后提交者返回 `409`，提示"该条目已被修改，请刷新后重试"（`AC-F25-4`）
- 修改**不改变** `status` 与 `is_active`

**示例请求**

```bash
curl -X PUT "https://medical-guidance.example.com/api/v1/admin/kb/entries/e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{
    "title": "消化内科 · 含胰胆亚专科",
    "content": "诊治食管、胃、十二指肠、小肠、结肠、肝、胆、胰腺疾病。",
    "dept_code": "DIG",
    "source": "院内科室简介_v4",
    "entry_version": "2026-10-15",
    "expected_update_time": "2026-10-14T11:02:33+08:00"
  }'
```

#### 12.7.5 启停知识库条目

**接口路径**：`POST /api/v1/admin/kb/entries/{entry_id}/status`
**功能说明**：发布、停用或重新启用条目（对应 `F26`、`R09`）

**路径参数**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `entry_id` | string | 是 | 条目标识 |

**请求体**

```json
{
  "status": "1",
  "reason": "新增胰胆亚专科内容，完成审核后发布"
}
```

**请求体字段说明**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `status` | string | 是 | 目标状态：`1` 发布 / `2` 停用 |
| `reason` | string | 否 | 变更原因，不超过 200 字 |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "entry_id": "e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6",
    "status": "1",
    "status_label": "已发布",
    "is_active": true,
    "history_id": "c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0",
    "need_ingest": true
  },
  "message": "已发布"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `need_ingest` | boolean | **是否需要重新入库才能生效**。为 `true` 时前端应提示管理员执行入库 |

**错误码**

| code | message | 说明 |
|---|---|---|
| `40001` | 知识库条目不存在 | `entry_id` 无效 |
| `40004` | 该条目已被引用，不可停用 | 存在引用关系 |
| `422` | 业务规则校验失败 | 目标状态与当前状态相同 |
| `401` | 未认证 | 缺少令牌 |

**业务规则**

- **系统不提供物理删除**：停用即软删除（`del_flag=1`），数据与变更记录长期保留（`R09`、`AC-F26-1`、`AC-F26-3`）
- 停用后**需重新入库**才从检索结果中消失（`AC-F26-2`）
- 停用被其他知识引用的条目时返回 `40004` 并提示引用来源
- 状态变更写审计日志

**示例请求**

```bash
curl -X POST "https://medical-guidance.example.com/api/v1/admin/kb/entries/e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6/status" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{"status": "1", "reason": "新增胰胆亚专科内容，完成审核后发布"}'
```

#### 12.7.6 查询条目变更历史

**接口路径**：`GET /api/v1/admin/kb/entries/{entry_id}/history`
**功能说明**：查询条目的变更留痕，数据来自数据库变更记录而非版本控制工具（对应 `F27`）

**路径参数**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `entry_id` | string | 是 | 条目标识 |

**查询参数**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `page` / `size` | integer | 否 | `1` / `20` | 分页 |
| `change_type` | string | 否 | — | `CREATE` / `UPDATE` / `ENABLE` / `DISABLE` |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "total": 4,
    "page": 1,
    "size": 20,
    "items": [
      {
        "history_id": "c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0",
        "change_type": "UPDATE",
        "change_type_label": "修改",
        "changed_fields": ["content", "icd10_codes", "entry_version"],
        "before_json": {
          "content": "诊治食管、胃、十二指肠、小肠、结肠、肝、胆、胰腺疾病。",
          "entry_version": "2026-09-01"
        },
        "after_json": {
          "content": "诊治食管、胃、十二指肠、小肠、结肠、肝、胆、胰腺疾病。新增：常见主诉含消瘦与脂肪泻。",
          "entry_version": "2026-10-15"
        },
        "operator": "kbadmin",
        "operator_name": "知识库管理员",
        "kb_version": "kb-v2026.10.15",
        "create_time": "2026-10-15T19:50:12+08:00"
      }
    ]
  },
  "message": "成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `changed_fields` | array | **本次变更涉及的具体字段名**，可据此看出改了哪些项（`AC-F27-2`） |
| `before_json` / `after_json` | object | 变更前后快照，新增时 `before_json` 为 `null` |
| `operator_name` | string | 操作人姓名快照 |

**错误码**

| code | message | 说明 |
|---|---|---|
| `40001` | 知识库条目不存在 | `entry_id` 无效 |
| `401` | 未认证 | 缺少令牌 |

**业务规则**

- 按时间**倒序**返回
- 每条记录含变更前值、变更后值、操作人、时间（`AC-F27-1`）
- 历史记录**只追加，不可修改**
- 变更历史独立于条目状态：条目停用后历史仍可查

**示例请求**

```bash
curl -X GET "https://medical-guidance.example.com/api/v1/admin/kb/entries/e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6/history?page=1&size=20" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### 12.7.7 发布知识库

**接口路径**：`POST /api/v1/admin/kb/publish`
**功能说明**：将已发布条目导出为不可变快照并生成版本标识，用于发布留痕与跨环境迁移（对应 `F28`）

**请求头**：`Authorization` 是 ｜ `Content-Type` 是 ｜ `Idempotency-Key` 建议

**请求体**

```json
{
  "version_tag": "kb-v2026.10.15",
  "remark": "十月知识库例行更新：新增胰胆亚专科条目，修订 3 条用药禁忌"
}
```

**请求体字段说明**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `version_tag` | string | 否 | 版本标识，留空时服务端按 `kb-v<日期>` 生成 |
| `remark` | string | 否 | 发布说明，不超过 500 字 |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "publish_id": "d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1",
    "version_tag": "kb-v2026.10.15",
    "entry_count": 512,
    "snapshot_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "draft_count": 2,
    "published_by": "kbadmin",
    "published_time": "2026-10-15T20:05:33+08:00"
  },
  "message": "发布成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `entry_count` | integer | 导出的已发布条目数 |
| `snapshot_hash` | string | 快照内容哈希，**用于校验完整性** |
| `draft_count` | integer | 未发布的草稿条目数，**提示但不阻断发布** |

**错误码**

| code | message | 说明 |
|---|---|---|
| `40014` | 版本标识已存在 | `version_tag` 冲突 |
| `40013` | 发布快照生成失败 | 快照写入异常，**已回滚不产生半成品** |
| `403` | 无权限 | 非知识库管理员 |
| `401` | 未认证 | 缺少令牌 |

**业务规则**

- **快照不作为数据源**：数据源始终是数据库中的条目（`R08`）。快照用途是"发布留痕 + 跨环境迁移介质"
- 存在草稿时返回 `draft_count` 提示，**但不阻断发布**
- **快照生成失败时不产生半成品文件**（`AC-F28-3`）
- **入库流程不依赖本接口的快照**（`AC-F28-2`）
- 发布动作写审计日志

**示例请求**

```bash
curl -X POST "https://medical-guidance.example.com/api/v1/admin/kb/publish" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{
    "version_tag": "kb-v2026.10.15",
    "remark": "十月知识库例行更新"
  }'
```

#### 12.7.8 查询发布版本列表

**接口路径**：`GET /api/v1/admin/kb/publish`
**功能说明**：分页查询历史发布版本（对应 `F28`）

**查询参数**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `page` / `size` | integer | 否 | `1` / `20` | 分页 |
| `start_date` / `end_date` | string | 否 | — | 发布日期范围 |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "total": 6,
    "page": 1,
    "size": 20,
    "items": [
      {
        "publish_id": "d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1",
        "version_tag": "kb-v2026.10.15",
        "entry_count": 512,
        "snapshot_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "published_by": "kbadmin",
        "published_time": "2026-10-15T20:05:33+08:00",
        "rollback_supported": false
      }
    ]
  },
  "message": "成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `rollback_supported` | boolean | **一期恒为 `false`**。版本回滚属二期工程（`F32`） |

**错误码**：`401` 未认证 ｜ `403` 无权限

**示例请求**

```bash
curl -X GET "https://medical-guidance.example.com/api/v1/admin/kb/publish?page=1&size=20" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### 12.7.9 触发知识库入库

**接口路径**：`POST /api/v1/admin/kb/tasks/ingest`
**功能说明**：异步触发知识库入库任务，将条目向量化写入向量库（对应 `F29`）

**请求头**：`Authorization` 是 ｜ `Content-Type` 是 ｜ `Idempotency-Key` **强烈建议**

**请求体**

```json
{
  "kb_types": ["DEPT_EXPERTISE", "GUIDELINE"],
  "full_rebuild": false,
  "remark": "十月例行入库"
}
```

**请求体字段说明**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `kb_types` | array | 否 | 只入库指定类型；不传表示全部类型 |
| `full_rebuild` | boolean | 否 | 是否全量重建。默认 `false`（按 `entry_code` 幂等 upsert） |
| `remark` | string | 否 | 任务说明 |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "task_id": "d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9",
    "task_no": "ING20261015001",
    "status": "PENDING",
    "stage": null,
    "progress": 0,
    "created_time": "2026-10-15T20:10:00+08:00",
    "ws_url": "wss://medical-guidance.example.com/api/v1/ws/tasks/d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9",
    "ws_ticket_required": true
  },
  "message": "入库任务已创建"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `task_no` | string | 任务业务编号，格式 `ING` + 日期 + 序号 |
| `status` | string | 任务状态，取值见 6.3 节枚举字典 |
| `ws_url` | string | 任务进度 WebSocket 地址 |
| `ws_ticket_required` | boolean | 恒为 `true`，连接前需先获取票据 |

**错误码**

| code | message | 说明 |
|---|---|---|
| `40006` | 存在未完成的入库任务 | **并发冲突**：已有 `PENDING` 或 `RUNNING` 任务 |
| `409` | 资源冲突 | 同一幂等键的请求正在处理中 |
| `403` | 无权限 | 非知识库管理员 |
| `60005` | 向量化服务不可用 | 向量化后端不可用，暂不可入库 |
| `401` | 未认证 | 缺少令牌 |

**业务规则**

- **同一租户同时只允许一个未完成的入库任务**（`40006`）——重复触发会造成向量库写入竞争
- 任务为**异步执行**，接口只返回任务标识，进度通过 WebSocket 推送（架构文档 §6.6）
- 任务执行含五个阶段：`VALIDATE` → `DIFF` → `EMBED` → `WRITE` → `VERIFY`
- **入库流程只读数据库条目，不读发布快照**（`AC-F28-2`）
- 任一条目校验失败则**整批不写入**（`AC-F29-2`）

**幂等性**：支持（**强烈建议携带 `Idempotency-Key`**）
**限流**：**6 次 / 分钟**（按账号标识，任务创建类单独限流）

**示例请求**

```bash
curl -X POST "https://medical-guidance.example.com/api/v1/admin/kb/tasks/ingest" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2" \
  -d '{
    "kb_types": ["DEPT_EXPERTISE", "GUIDELINE"],
    "full_rebuild": false,
    "remark": "十月例行入库"
  }'
```

#### 12.7.10 查询入库任务列表

**接口路径**：`GET /api/v1/admin/kb/tasks`
**功能说明**：分页查询入库任务记录（对应 `F29`）

**查询参数**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `page` / `size` | integer | 否 | `1` / `20` | 分页 |
| `status` | string | 否 | — | `PENDING` / `RUNNING` / `SUCCESS` / `FAILED` / `ABORTED` |
| `start_date` / `end_date` | string | 否 | — | 创建日期范围 |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "total": 12,
    "page": 1,
    "size": 20,
    "items": [
      {
        "task_id": "d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9",
        "task_no": "ING20261015001",
        "status": "SUCCESS",
        "stage": "VERIFY",
        "progress": 100,
        "total_count": 512,
        "added_count": 38,
        "updated_count": 12,
        "disabled_count": 3,
        "failed_count": 0,
        "duration_ms": 184320,
        "triggered_by": "kbadmin",
        "create_time": "2026-10-15T20:10:00+08:00",
        "finished_time": "2026-10-15T20:13:04+08:00"
      }
    ],
    "backlog_count": 0
  },
  "message": "成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `added_count` / `updated_count` / `disabled_count` | integer | 差异统计，与 `AC-F29-1` 要求一致 |
| `backlog_count` | integer | **未完成任务数量**，用于积压告警 |

**错误码**：`401` 未认证 ｜ `403` 无权限

**示例请求**

```bash
curl -X GET "https://medical-guidance.example.com/api/v1/admin/kb/tasks?page=1&size=20&status=SUCCESS" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### 12.7.11 查询入库任务详情

**接口路径**：`GET /api/v1/admin/kb/tasks/{task_id}`
**功能说明**：查询单个入库任务的完整信息与失败明细（对应 `F29`）

**路径参数**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `task_id` | string | 是 | 任务标识，也可传 `task_no` |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "task_id": "d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9",
    "task_no": "ING20261015001",
    "status": "FAILED",
    "stage": "VALIDATE",
    "progress": 0,
    "total_count": 512,
    "added_count": 0,
    "updated_count": 0,
    "disabled_count": 0,
    "failed_count": 2,
    "error_json": {
      "failed_entries": [
        {"entry_code": "DEPT-DIG-018", "reason": "dept_code 不存在：DIGEST"},
        {"entry_code": "DRUG-0007", "reason": "缺少必填项 contraindication_type"}
      ]
    },
    "triggered_by": "kbadmin",
    "create_time": "2026-10-15T20:10:00+08:00",
    "finished_time": "2026-10-15T20:10:08+08:00"
  },
  "message": "成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `error_json.failed_entries` | array | 失败条目清单与原因（`AC-F29-2` 的展示依据） |
| `failed_count` | integer | 失败条目数。**大于 0 时整批未写入** |

**错误码**

| code | message | 说明 |
|---|---|---|
| `40007` | 入库任务不存在 | `task_id` 与 `task_no` 均未命中 |
| `401` | 未认证 | 缺少令牌 |

**示例请求**

```bash
curl -X GET "https://medical-guidance.example.com/api/v1/admin/kb/tasks/ING20261015001" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### 12.7.12 换取 WebSocket 票据

**接口路径**：`POST /api/v1/ws/ticket`
**功能说明**：换取一次性短效票据，用于建立 WebSocket 连接（见 11.1 节）

**请求头**：`Authorization` 是 ｜ `Content-Type` 是

**请求体**

```json
{
  "resource_type": "SESSION",
  "resource_id": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
}
```

**请求体字段说明**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `resource_type` | string | 是 | `SESSION` 对话通道 / `TASK` 任务通道 |
| `resource_id` | string | 是 | 目标资源标识（会话标识或任务标识） |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "ws_ticket": "wt_8f7e6d5c4b3a29182706f5e4d3c2b1a0",
    "expires_in": 60,
    "ws_url": "wss://medical-guidance.example.com/api/v1/ws/sessions/a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6?token=wt_8f7e6d5c4b3a29182706f5e4d3c2b1a0"
  },
  "message": "成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `ws_ticket` | string | 一次性票据，**有效期 60 秒，使用一次即失效** |
| `ws_url` | string | 已拼好票据的完整连接地址 |

**错误码**

| code | message | 说明 |
|---|---|---|
| `404` | 资源不存在 | 目标会话或任务不存在 |
| `403` | 无权限 | 非本人会话，或医生未接诊该患者 |
| `400` | 参数校验失败 | `resource_type` 取值非法 |
| `401` | 未认证 | 缺少令牌 |

**业务规则**

- **票据绑定资源**：用于其他 `session_id` / `task_id` 时连接被拒绝
- **一次性**：连接建立后立即作废，重连需重新获取
- **替代方案说明**：不使用长期 `access_token` 直接拼在 URL 上，避免令牌被网关与浏览器历史记录

**限流**：60 次 / 分钟

**示例请求**

```bash
curl -X POST "https://medical-guidance.example.com/api/v1/ws/ticket" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{
    "resource_type": "SESSION",
    "resource_id": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
  }'
```

### 12.8 检索验证

#### 12.8.1 检索测试台

**接口路径**：`POST /api/v1/admin/retrieval/search`
**功能说明**：执行检索并**逐路返回**结果，用于对比不同检索模式的效果（对应 `F30`）

**请求头**：`Authorization` 是 ｜ `Content-Type` 是

**请求体**

```json
{
  "query": "拉肚子三天了",
  "kb_types": ["DEPT_EXPERTISE", "SYMPTOM_DISEASE"],
  "retrieval_mode": "ALL",
  "limit": 10,
  "enable_rerank": true
}
```

**请求体字段说明**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `query` | string | 是 | 查询文本，1~500 字 |
| `kb_types` | array | 否 | 限定知识类型；不传表示全部 |
| `retrieval_mode` | string | 否 | `DENSE` 仅语义 / `SPARSE` 仅词元 / `HYBRID` 融合 / **`ALL` 三路全返回**（默认，供对比） |
| `limit` | integer | 否 | 每路返回条数，1~50，默认 10 |
| `enable_rerank` | boolean | 否 | 是否启用精排，默认 `true` |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "query": "拉肚子三天了",
    "elapsed_ms": 287,
    "rerank_applied": true,
    "sparse_available": true,
    "results": {
      "dense_only": [
        {"entry_id": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6", "entry_code": "DEPT-DIG-001", "title": "消化内科", "score": 0.8123}
      ],
      "sparse_only": [
        {"entry_id": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6", "entry_code": "DEPT-DIG-001", "title": "消化内科", "score": 0.6402}
      ],
      "hybrid": [
        {"entry_id": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6", "entry_code": "DEPT-DIG-001", "title": "消化内科", "score": 0.8731, "rerank_score": 0.9105}
      ]
    },
    "dept_aggregation": [
      {"dept_code": "DIG", "dept_name": "消化内科", "max_score": 0.8731}
    ]
  },
  "message": "成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `results` | object | **三路结果并列返回**（`retrieval_mode=ALL`），供人工对比（`AC-F30-1`） |
| `sparse_available` | boolean | 稀疏向量是否可用。**为 `false` 时说明向量化模型未产出稀疏向量，混合检索已退化为纯语义** |
| `results.hybrid[].rerank_score` | number | 精排分数，未启用精排时为 `null` |
| `dept_aggregation` | array | 按科室聚合的结果，对应分诊的实际使用方式 |

**错误码**

| code | message | 说明 |
|---|---|---|
| `40009` | 检索查询为空 | `query` 为空 |
| `400` | 参数校验失败 | `limit` 超出范围 |
| `40012` | 知识库检索超时 | 检索耗时超过阈值 |
| `60005` | 向量化服务不可用 | 向量化后端不可用 |
| `403` | 无权限 | 非知识库管理员或机构管理员 |
| `401` | 未认证 | 缺少令牌 |

**业务规则**

- **必须支持三路并列返回**，这是判断混合检索是否值得保留的操作依据（ADR-005）
- 精排不可用时**自动降级**并在 `message` 中说明，不返回错误（`AC-F30-3` 关联规则）
- 检索超时时保留上次结果，界面提示超时
- 无结果时 `results` 各数组为 `[]`，**不返回错误**

**限流**：**30 次 / 分钟**（按账号标识，单次检索开销较大）

**示例请求**

```bash
curl -X POST "https://medical-guidance.example.com/api/v1/admin/retrieval/search" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{
    "query": "拉肚子三天了",
    "kb_types": ["DEPT_EXPERTISE", "SYMPTOM_DISEASE"],
    "retrieval_mode": "ALL",
    "limit": 10,
    "enable_rerank": true
  }'
```

#### 12.8.2 查询黄金查询用例列表

**接口路径**：`GET /api/v1/admin/retrieval/golden-queries`
**功能说明**：分页查询黄金查询集（对应 `F31`）

**查询参数**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `page` / `size` | integer | 否 | `1` / `20` | 分页 |
| `category` | string | 否 | — | 用例分类 |
| `is_active` | boolean | 否 | — | 是否启用 |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "total": 32,
    "page": 1,
    "size": 20,
    "items": [
      {
        "query_id": "b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8",
        "query_code": "GQ-0001",
        "query_text": "肚子疼",
        "expect_depts": ["DIG", "GEN_SURG"],
        "expect_not_depts": ["OPHTH", "DERM"],
        "expect_route": null,
        "category": "跨科室歧义",
        "is_active": true,
        "description": "验证腹痛能召回消化内科与普通外科，且不串扰无关科室"
      }
    ],
    "active_count": 30,
    "suggest_ingest": false
  },
  "message": "成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `expect_not_depts` | array | **期望不应出现的科室**，用于验证串扰——比"期望项"更能发现退化 |
| `active_count` | integer | 启用中的用例数。**少于 30 条时 `suggest_ingest=true`** 提示补充 |
| `suggest_ingest` | boolean | 是否建议补充用例 |

**错误码**：`401` 未认证 ｜ `403` 无权限

**业务规则**

- 用例按 `category` 分类，便于按类别分析退化
- `expect_route` 用于验证危重症类用例的路由正确性
- 一期要求启用中的用例**不少于 30 条**

**示例请求**

```bash
curl -X GET "https://medical-guidance.example.com/api/v1/admin/retrieval/golden-queries?page=1&size=20&is_active=true" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### 12.8.3 新增黄金查询用例

**接口路径**：`POST /api/v1/admin/retrieval/golden-queries`
**功能说明**：新增一条回归验证用例（对应 `F31`）

**请求头**：`Authorization` 是 ｜ `Content-Type` 是

**请求体**

```json
{
  "query_code": "GQ-0033",
  "query_text": "胸口疼 出汗 后背疼",
  "expect_depts": [],
  "expect_not_depts": [],
  "expect_route": "EMERGENCY",
  "category": "危重症",
  "description": "验证心梗先兆表述能触发急诊通道"
}
```

**请求体字段说明**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `query_code` | string | 是 | 用例编号，租户内唯一 |
| `query_text` | string | 是 | 查询文本，模拟患者主诉 |
| `expect_depts` | array | 否 | 期望召回的科室编码 |
| `expect_not_depts` | array | 否 | 期望不应出现的科室编码 |
| `expect_route` | string | 否 | 期望路由去向 |
| `category` | string | 否 | 用例分类 |
| `description` | string | 否 | 用例说明 |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "query_id": "c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9",
    "query_code": "GQ-0033",
    "is_active": true,
    "created_time": "2026-10-15T20:20:00+08:00"
  },
  "message": "新增成功"
}
```

**错误码**

| code | message | 说明 |
|---|---|---|
| `400` | 参数校验失败 | `query_code` 重复或 `query_text` 为空 |
| `401` | 未认证 | 缺少令牌 |
| `403` | 无权限 | 非知识库管理员 |

**业务规则**：新增用例后**需执行一次回归**才能纳入基线对比

**示例请求**

```bash
curl -X POST "https://medical-guidance.example.com/api/v1/admin/retrieval/golden-queries" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{
    "query_code": "GQ-0033",
    "query_text": "胸口疼 出汗 后背疼",
    "expect_route": "EMERGENCY",
    "category": "危重症"
  }'
```

#### 12.8.4 执行回归验证

**接口路径**：`POST /api/v1/admin/retrieval/verify`
**功能说明**：执行黄金查询集回归，返回通过率与失败明细（对应 `F31`）

**请求头**：`Authorization` 是 ｜ `Content-Type` 是 ｜ `Idempotency-Key` **强烈建议**

**请求体**

```json
{
  "retrieval_mode": "HYBRID",
  "category": null,
  "remark": "十月知识库更新后回归"
}
```

**请求体字段说明**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `retrieval_mode` | string | 否 | `DENSE` / `SPARSE` / `HYBRID`，默认 `HYBRID`。**同批用例在不同模式下各跑一次，即可对比增益** |
| `category` | string | 否 | 只跑指定分类的用例 |
| `remark` | string | 否 | 执行说明 |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "run_id": "d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0",
    "run_no": "RUN20261015001",
    "kb_version": "kb-v2026.10.15",
    "retrieval_mode": "HYBRID",
    "total_count": 30,
    "passed_count": 28,
    "failed_count": 2,
    "pass_rate": 0.9333,
    "baseline_rate": 0.9000,
    "is_regression": false,
    "duration_ms": 12400,
    "failed_cases": [
      {
        "query_code": "GQ-0012",
        "query_text": "头晕",
        "expect_depts": ["NEU"],
        "actual_depts": ["NEU", "CAR"],
        "reason": "出现期望外的科室：CAR"
      }
    ]
  },
  "message": "回归完成"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `pass_rate` | number | 通过率。**`H3/30 = 93.3%` 的展示要求见 `AC-F31-1`** |
| `baseline_rate` | number | 基线通过率，来自系统配置 `kb.regression_baseline` |
| `is_regression` | boolean | **是否低于基线**。`true` 时前端须红色告警（`AC-F31-2`） |
| `failed_cases[].reason` | string | 失败原因，区分"漏召回"与"串扰" |

**错误码**

| code | message | 说明 |
|---|---|---|
| `40011` | 无启用中的黄金查询用例 | 用例集为空或全部停用 |
| `40010` | 黄金查询用例不存在 | `category` 指定的分类下无用例 |
| `40012` | 知识库检索超时 | 批量执行超时 |
| `409` | 资源冲突 | 同一幂等键的请求正在处理中 |
| `403` | 无权限 | 非知识库管理员或机构管理员 |
| `401` | 未认证 | 缺少令牌 |

**业务规则**

- **单条用例异常不阻断整体执行**，该条标记为失败并继续（`AC-F31-3`）
- 通过率低于基线时 `is_regression=true`，作为知识库变更的**质量闸门**（`NFR34`）
- 每次执行**记录一条回归记录**，含 `retrieval_mode`，供后续按模式对比（ADR-005 的数据来源）
- 执行结果可导出为《评测报告》的附件

**限流**：**6 次 / 分钟**（按账号标识，任务创建类）

**示例请求**

```bash
curl -X POST "https://medical-guidance.example.com/api/v1/admin/retrieval/verify" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3" \
  -d '{
    "retrieval_mode": "HYBRID",
    "remark": "十月知识库更新后回归"
  }'
```

#### 12.8.5 查询回归执行记录

**接口路径**：`GET /api/v1/admin/retrieval/runs`
**功能说明**：分页查询历史回归执行记录，可按检索模式对比通过率（对应 `F31`）

**查询参数**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `page` / `size` | integer | 否 | `1` / `20` | 分页 |
| `retrieval_mode` | string | 否 | — | 按检索模式筛选，用于对比 |
| `only_regression` | boolean | 否 | `false` | 只看低于基线的记录 |
| `start_date` / `end_date` | string | 否 | — | 执行日期范围 |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "total": 18,
    "page": 1,
    "size": 20,
    "items": [
      {
        "run_id": "d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0",
        "run_no": "RUN20261015001",
        "kb_version": "kb-v2026.10.15",
        "retrieval_mode": "HYBRID",
        "total_count": 30,
        "passed_count": 28,
        "pass_rate": 0.9333,
        "baseline_rate": 0.9000,
        "is_regression": false,
        "duration_ms": 12400,
        "triggered_by": "kbadmin",
        "create_time": "2026-10-15T20:25:00+08:00"
      }
    ],
    "mode_comparison": [
      {"retrieval_mode": "DENSE", "avg_pass_rate": 0.8667, "run_count": 6},
      {"retrieval_mode": "SPARSE", "avg_pass_rate": 0.6333, "run_count": 6},
      {"retrieval_mode": "HYBRID", "avg_pass_rate": 0.9333, "run_count": 6}
    ]
  },
  "message": "成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `mode_comparison` | array | **按检索模式的平均通过率对比**。这是"混合检索是否有增益"的直接答案 |

**错误码**：`401` 未认证 ｜ `403` 无权限

**业务规则**

- 按执行时间倒序
- `mode_comparison` 仅统计启用中的用例集上的执行
- 该接口输出可直接用于向评审说明"为什么保留（或关闭）词元检索那一路"

**示例请求**

```bash
curl -X GET "https://medical-guidance.example.com/api/v1/admin/retrieval/runs?page=1&size=20" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### 12.9 账号与机构管理

> 本模块全部接口权限要求：**`ORG_ADMIN`**。统一限流 **600 次 / 分钟**。

#### 12.9.1 查询用户列表

**接口路径**：`GET /api/v1/admin/users`
**功能说明**：分页查询本机构用户账号（对应 `F55`）

**请求头**：`Authorization` 是

**查询参数**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `page` / `size` | integer | 否 | `1` / `20` | 分页，`size` 上限 100 |
| `role` | string | 否 | — | `DOCTOR` / `KB_ADMIN` / `ORG_ADMIN` |
| `dept_code` | string | 否 | — | 科室编码 |
| `status` | string | 否 | — | `1` 启用 / `0` 停用 |
| `keyword` | string | 否 | — | 模糊匹配账号或姓名 |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "total": 24,
    "page": 1,
    "size": 20,
    "items": [
      {
        "user_id": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
        "account": "doctor001",
        "real_name": "张明",
        "role": "DOCTOR",
        "role_label": "医生",
        "title": "副主任医师",
        "dept_code": "DIG",
        "dept_name": "消化内科",
        "status": "1",
        "last_login_time": "2026-10-15T08:12:33+08:00",
        "create_time": "2026-09-01T09:00:00+08:00"
      }
    ]
  },
  "message": "成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `title` | string | 医师职称，非医生角色为 `null` |
| `role_label` | string | 角色中文名，供直接展示 |

**错误码**

| code | message | 说明 |
|---|---|---|
| `403` | 无权限 | 非机构管理员 |
| `401` | 未认证 | 缺少令牌 |

**业务规则**：只返回**当前租户**的用户；不返回口令哈希等敏感字段

**示例请求**

```bash
curl -X GET "https://medical-guidance.example.com/api/v1/admin/users?page=1&size=20&role=DOCTOR&status=1" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### 12.9.2 创建用户

**接口路径**：`POST /api/v1/admin/users`
**功能说明**：创建医生或管理员账号（对应 `F55`、`F13`）

**请求头**：`Authorization` 是 ｜ `Content-Type` 是 ｜ `Idempotency-Key` 建议

**请求体**

```json
{
  "account": "doctor015",
  "real_name": "李静",
  "role": "DOCTOR",
  "title": "主治医师",
  "dept_code": "DIG",
  "initial_password": "Med@2026#Dig",
  "remark": "消化内科新入职医师"
}
```

**请求体字段说明**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `account` | string | 是 | 登录账号，租户内唯一，4~64 位 |
| `real_name` | string | 是 | 真实姓名 |
| `role` | string | 是 | `DOCTOR` / `KB_ADMIN` / `ORG_ADMIN` |
| `title` | string | 条件必填 | **`role=DOCTOR` 时必填**：住院医师 / 主治医师 / 副主任医师 / 主任医师 |
| `dept_code` | string | 条件必填 | **`role=DOCTOR` 时必填**，须存在于科室表 |
| `initial_password` | string | 是 | 初始口令，须满足复杂度要求 |
| `remark` | string | 否 | 备注 |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "user_id": "f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2",
    "account": "doctor015",
    "role": "DOCTOR",
    "status": "1",
    "need_change_password": true,
    "created_time": "2026-10-15T20:30:00+08:00"
  },
  "message": "创建成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `need_change_password` | boolean | 恒为 `true`。**首次登录须强制修改口令** |

**错误码**

| code | message | 说明 |
|---|---|---|
| `50005` | 登录账号已存在 | `account` 冲突 |
| `50001` | 科室不存在 | `dept_code` 不存在 |
| `400` | 参数校验失败 | 角色为医生但未传职称或科室；口令不满足复杂度 |
| `403` | 无权限 | 非机构管理员 |
| `401` | 未认证 | 缺少令牌 |

**业务规则**

- **权限边界**：知识库管理员调用本接口返回 `403`（`AC-F55-1`）
- 初始口令须满足复杂度要求（同 12.1.8）
- `title` 字段是评测样本采纳判定的依据，**医生账号必须设置**
- 创建动作写审计日志（`action_type = 'PERM_CHANGE'`）

**示例请求**

```bash
curl -X POST "https://medical-guidance.example.com/api/v1/admin/users" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4" \
  -d '{
    "account": "doctor015",
    "real_name": "李静",
    "role": "DOCTOR",
    "title": "主治医师",
    "dept_code": "DIG",
    "initial_password": "Med@2026#Dig"
  }'
```

#### 12.9.3 修改用户

**接口路径**：`PUT /api/v1/admin/users/{user_id}`
**功能说明**：修改用户的基本信息与归属（对应 `F55`）

**路径参数**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `user_id` | string | 是 | 用户标识 |

**请求体**

```json
{
  "real_name": "李静",
  "title": "副主任医师",
  "dept_code": "DIG",
  "remark": "职称晋升，2026-10 起"
}
```

**请求体字段说明**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `real_name` | string | 否 | 真实姓名 |
| `title` | string | 否 | 医师职称 |
| `dept_code` | string | 否 | 所属科室 |
| `remark` | string | 否 | 备注 |
| `role` / `account` | — | **不可修改** | 传入时返回 `400` |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "user_id": "f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2",
    "title": "副主任医师",
    "dept_code": "DIG",
    "update_time": "2026-10-15T20:35:00+08:00"
  },
  "message": "修改成功"
}
```

**错误码**

| code | message | 说明 |
|---|---|---|
| `50004` | 用户不存在 | `user_id` 无效 |
| `50001` | 科室不存在 | `dept_code` 不存在 |
| `400` | 参数校验失败 | 尝试修改 `role` 或 `account` |
| `403` | 无权限 | 非机构管理员 |
| `401` | 未认证 | 缺少令牌 |

**业务规则**

- **`role` 与 `account` 不可通过本接口修改**：角色变更需单独流程（一期不做），账号是身份标识不可变
- 修改职称**不影响历史修正记录的采纳判定**——修正记录的 `doctor_title` 是快照（见 12.5.7）
- 修改动作写审计日志

**示例请求**

```bash
curl -X PUT "https://medical-guidance.example.com/api/v1/admin/users/f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{"title": "副主任医师", "dept_code": "DIG", "remark": "职称晋升"}'
```

#### 12.9.4 启停用户

**接口路径**：`POST /api/v1/admin/users/{user_id}/status`
**功能说明**：启用或停用用户账号（对应 `F55`）

**路径参数**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `user_id` | string | 是 | 用户标识 |

**请求体**

```json
{
  "status": "0",
  "reason": "本人申请暂停账号"
}
```

**请求体字段说明**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `status` | string | 是 | `1` 启用 / `0` 停用 |
| `reason` | string | 否 | 变更原因 |
| `force` | boolean | 否 | **停用仍有未完成接诊的医生时，需传 `true` 表示二次确认** |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "user_id": "f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2",
    "status": "0",
    "ongoing_encounters": 3,
    "tokens_revoked": true,
    "update_time": "2026-10-15T20:40:00+08:00"
  },
  "message": "已停用"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `ongoing_encounters` | integer | **未完成的接诊数量**。停用时用于提示影响范围 |
| `tokens_revoked` | boolean | 是否已注销该用户所有令牌。停用时恒为 `true` |

**错误码**

| code | message | 说明 |
|---|---|---|
| `50004` | 用户不存在 | `user_id` 无效 |
| `50006` | 该医生存在未完成接诊 | **未传 `force=true` 时返回**，提示影响范围并要求二次确认 |
| `422` | 业务规则校验失败 | 目标状态与当前相同 |
| `403` | 无权限 | 非机构管理员 |
| `401` | 未认证 | 缺少令牌 |

**业务规则**

- 停用后该用户的**所有令牌立即失效**（`tokens_revoked=true`）
- 存在未完成接诊时**提示影响范围并要求二次确认**（`force=true`）
- 停用是**软删除**（`del_flag=1`），账号数据保留，可重新启用
- 变更动作写审计日志

**示例请求**

```bash
curl -X POST "https://medical-guidance.example.com/api/v1/admin/users/f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2/status" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{"status": "0", "reason": "本人申请暂停账号", "force": false}'
```

#### 12.9.5 查询科室列表

**接口路径**：`GET /api/v1/admin/depts`
**功能说明**：查询本机构的科室设置（对应 `F55`）

**查询参数**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `page` / `size` | integer | 否 | `1` / `100` | 分页 |
| `parent_code` | string | 否 | — | 上级科室编码，不传返回全部 |
| `status` | string | 否 | — | `1` 启用 / `0` 停用 |
| `keyword` | string | 否 | — | 匹配科室名称或编码 |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "total": 42,
    "page": 1,
    "size": 100,
    "items": [
      {
        "dept_id": "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7",
        "dept_code": "DIG",
        "dept_name": "消化内科",
        "sub_specialty": ["炎症性肠病", "肝病", "胰胆疾病"],
        "common_complaints": ["上腹痛", "反酸", "腹泻", "黄疸"],
        "parent_code": null,
        "sort_no": 10,
        "status": "1",
        "referenced_entry_count": 18
      }
    ]
  },
  "message": "成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `common_complaints` | array | 常见主诉，供检索与引导使用 |
| `referenced_entry_count` | integer | **引用该科室的知识条目数**，用于判断能否停用 |

**错误码**：`401` 未认证 ｜ `403` 无权限

**业务规则**：`role=DOCTOR` 与 `KB_ADMIN` 可读，仅 `ORG_ADMIN` 可写

**示例请求**

```bash
curl -X GET "https://medical-guidance.example.com/api/v1/admin/depts?page=1&size=100&status=1" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### 12.9.6 新增科室

**接口路径**：`POST /api/v1/admin/depts`
**功能说明**：新增科室设置（对应 `F55`）

**请求体**

```json
{
  "dept_code": "HEP",
  "dept_name": "肝病科",
  "sub_specialty": ["病毒性肝炎", "肝硬化"],
  "common_complaints": ["乏力", "黄疸", "腹胀"],
  "parent_code": "DIG",
  "sort_no": 20
}
```

**请求体字段说明**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `dept_code` | string | 是 | 科室编码，租户内唯一，不超过 32 字符 |
| `dept_name` | string | 是 | 科室名称，不超过 128 字符 |
| `sub_specialty` | array | 否 | 亚专科列表 |
| `common_complaints` | array | 否 | 常见主诉 |
| `parent_code` | string | 否 | 上级科室编码，为空表示一级科室 |
| `sort_no` | integer | 否 | 排序号，默认 0 |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "dept_id": "c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8",
    "dept_code": "HEP",
    "status": "1",
    "created_time": "2026-10-15T20:45:00+08:00"
  },
  "message": "新增成功"
}
```

**错误码**

| code | message | 说明 |
|---|---|---|
| `50002` | 科室编码已存在 | `dept_code` 冲突 |
| `400` | 参数校验失败 | `parent_code` 不存在，或字段超长 |
| `403` | 无权限 | 非机构管理员 |
| `401` | 未认证 | 缺少令牌 |

**业务规则**：新增后状态为启用；科室数据是知识库条目的引用目标，删除采用停用

**示例请求**

```bash
curl -X POST "https://medical-guidance.example.com/api/v1/admin/depts" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{
    "dept_code": "HEP",
    "dept_name": "肝病科",
    "sub_specialty": ["病毒性肝炎", "肝硬化"],
    "parent_code": "DIG",
    "sort_no": 20
  }'
```

#### 12.9.7 修改科室

**接口路径**：`PUT /api/v1/admin/depts/{dept_id}`
**功能说明**：修改科室的名称、亚专科与常见主诉（对应 `F55`）

**路径参数**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `dept_id` | string | 是 | 科室标识 |

**请求体**

```json
{
  "dept_name": "肝病科（含脂肪肝门诊）",
  "sub_specialty": ["病毒性肝炎", "肝硬化", "脂肪肝"],
  "common_complaints": ["乏力", "黄疸", "腹胀", "右上腹不适"],
  "sort_no": 20
}
```

**请求体字段说明**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `dept_code` | — | **不可修改** | 编码是知识条目的引用键，改编码会导致引用断裂。传入时返回 `400` |
| 其余字段 | — | 否 | 同 12.9.6 |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "dept_id": "c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8",
    "dept_code": "HEP",
    "update_time": "2026-10-15T20:50:00+08:00"
  },
  "message": "修改成功"
}
```

**错误码**

| code | message | 说明 |
|---|---|---|
| `50001` | 科室不存在 | `dept_id` 无效 |
| `400` | 参数校验失败 | 尝试修改 `dept_code` |
| `403` | 无权限 | 非机构管理员 |
| `401` | 未认证 | 缺少令牌 |

**业务规则**：修改科室名称**不影响**已引用该科室编码的知识条目（引用基于编码而非名称）

**示例请求**

```bash
curl -X PUT "https://medical-guidance.example.com/api/v1/admin/depts/c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{"dept_name": "肝病科（含脂肪肝门诊）", "sub_specialty": ["病毒性肝炎", "肝硬化", "脂肪肝"]}'
```

#### 12.9.8 启停科室

**接口路径**：`POST /api/v1/admin/depts/{dept_id}/status`
**功能说明**：启用或停用科室（对应 `F55`）

**路径参数**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `dept_id` | string | 是 | 科室标识 |

**请求体**

```json
{
  "status": "0",
  "reason": "科室合并至消化内科",
  "force": false
}
```

**请求体字段说明**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `status` | string | 是 | `1` 启用 / `0` 停用 |
| `reason` | string | 否 | 变更原因 |
| `force` | boolean | 否 | **存在引用时需传 `true` 二次确认** |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "dept_id": "c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8",
    "status": "0",
    "referenced_entry_count": 18,
    "update_time": "2026-10-15T20:55:00+08:00"
  },
  "message": "已停用"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `referenced_entry_count` | integer | **引用该科室的知识条目数** |

**错误码**

| code | message | 说明 |
|---|---|---|
| `50001` | 科室不存在 | `dept_id` 无效 |
| `50003` | 该科室已被引用，不可停用 | **未传 `force=true` 时返回**，并提示被哪些条目引用（`AC-F55-2`） |
| `422` | 业务规则校验失败 | 目标状态与当前相同 |
| `403` | 无权限 | 非机构管理员 |
| `401` | 未认证 | 缺少令牌 |

**业务规则**

- **停用被引用的科室须二次确认**（`force=true`），并提示引用来源（`AC-F55-2`）
- 停用后该科室**不再参与分诊匹配**，但历史会话中引用的编码仍可解析
- 停用是软删除，数据保留

**示例请求**

```bash
curl -X POST "https://medical-guidance.example.com/api/v1/admin/depts/c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8/status" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{"status": "0", "reason": "科室合并至消化内科", "force": false}'
```

### 12.10 系统与模型配置

> 12.10.1 ~ 12.10.4 权限：**`ORG_ADMIN`**（`KB_ADMIN` 可读不可写）；12.10.5 ~ 12.10.8 权限：**`ORG_ADMIN`**。统一限流 **600 次 / 分钟**。

#### 12.10.1 查询机构信息

**接口路径**：`GET /api/v1/admin/org`
**功能说明**：查询当前租户的机构信息（对应 `F55`）

**响应示例**

```json
{
  "code": 200,
  "data": {
    "tenant_id": "00000000000000000000000000000001",
    "tenant_code": "HOSP_001",
    "tenant_name": "示例三甲医院",
    "hospital_level": "三级甲等",
    "contact_person": "王主任",
    "contact_phone": "0571-88880000",
    "status": "1",
    "expire_time": null,
    "dept_count": 42,
    "user_count": 24,
    "session_retention_days": 90
  },
  "message": "成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `tenant_id` | string | 机构标识，**与 JWT 中的 `tenant_id` 一致** |
| `dept_count` / `user_count` | integer | 统计信息，供界面展示 |

**错误码**：`401` 未认证 ｜ `403` 无权限 ｜ `50011` 机构信息不存在

**业务规则**：**只返回当前租户自身的信息**，不接受查询其他租户（见第 6 章例外说明）

**示例请求**

```bash
curl -X GET "https://medical-guidance.example.com/api/v1/admin/org" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### 12.10.2 修改机构信息

**接口路径**：`PUT /api/v1/admin/org`
**功能说明**：修改机构基本信息与联系信息（对应 `F55`）

**请求体**

```json
{
  "tenant_name": "示例三甲医院（总院区）",
  "hospital_level": "三级甲等",
  "contact_person": "王主任",
  "contact_phone": "0571-88880000"
}
```

**请求体字段说明**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `tenant_name` | string | 否 | 机构名称，不超过 128 字符 |
| `hospital_level` | string | 否 | 医院等级 |
| `contact_person` | string | 否 | 联系人 |
| `contact_phone` | string | 否 | 联系电话 |
| `tenant_code` | — | **不可修改** | 机构编码是数据隔离标识 |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "tenant_id": "00000000000000000000000000000001",
    "tenant_name": "示例三甲医院（总院区）",
    "update_time": "2026-10-15T21:00:00+08:00"
  },
  "message": "修改成功"
}
```

**错误码**：`400` 参数校验失败（尝试修改 `tenant_code`）｜ `403` 无权限 ｜ `401` 未认证

**业务规则**：修改动作写审计日志（`action_type = 'PERM_CHANGE'`）

**示例请求**

```bash
curl -X PUT "https://medical-guidance.example.com/api/v1/admin/org" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{"tenant_name": "示例三甲医院（总院区）", "hospital_level": "三级甲等"}'
```

#### 12.10.3 查询系统配置

**接口路径**：`GET /api/v1/admin/configs`
**功能说明**：查询租户级系统配置项（对应 `F55`、架构文档 §10.3）

**查询参数**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `config_key` | string | 否 | — | 精确查询某配置项 |
| `prefix` | string | 否 | — | 按键前缀筛选，如 `triage.` |
| `status` | string | 否 | — | `1` 启用 / `0` 停用 |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "items": [
      {
        "config_id": "d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9",
        "config_key": "triage.confidence_threshold",
        "config_value": "0.60",
        "config_type": "number",
        "description": "分诊置信度阈值，低于则转人工",
        "is_encrypted": false,
        "status": "1",
        "value_range": {"min": 0, "max": 1},
        "update_time": "2026-10-15T09:00:00+08:00"
      }
    ],
    "total": 12
  },
  "message": "成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `config_value` | string | 配置值。**统一以字符串返回**，`config_type` 说明如何解析 |
| `is_encrypted` | boolean | 值是否加密存储。为 `true` 时 `config_value` 返回脱敏形式 |
| `value_range` | object | **该配置项的合法取值范围**，供前端做输入校验，避免提交后才知道非法 |

**错误码**：`401` 未认证 ｜ `403` 无权限

**业务规则**：`is_encrypted=true` 的配置项，响应中 `config_value` 以 `****` 形式返回，不返回明文（`NFR17`）

**示例请求**

```bash
curl -X GET "https://medical-guidance.example.com/api/v1/admin/configs?prefix=triage." \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### 12.10.4 修改系统配置

**接口路径**：`PUT /api/v1/admin/configs/{config_key}`
**功能说明**：修改单个系统配置项的值（对应 `F55`）

**路径参数**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `config_key` | string | 是 | 配置键，如 `triage.confidence_threshold` |

**请求体**

```json
{
  "config_value": "0.65",
  "remark": "临床反馈低置信度转人工过多，略微上调阈值"
}
```

**请求体字段说明**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `config_value` | string | 是 | 配置值，**须符合 `config_type` 与 `value_range`** |
| `remark` | string | 否 | 修改原因 |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "config_key": "triage.confidence_threshold",
    "config_value": "0.65",
    "effective_immediately": true,
    "update_time": "2026-10-15T21:05:00+08:00"
  },
  "message": "修改成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `effective_immediately` | boolean | **是否立即生效**。`true` 表示无需重启；涉及检索参数的配置需重新入库才生效，此时为 `false` |

**错误码**

| code | message | 说明 |
|---|---|---|
| `50007` | 配置项不存在 | `config_key` 无效 |
| `50008` | 配置项取值非法 | 超出 `value_range`，或不符合 `config_type` |
| `403` | 无权限 | 非机构管理员 |
| `401` | 未认证 | 缺少令牌 |

**业务规则**

- 取值校验在服务端强制，**不依赖前端校验**
- 修改后**不触发重启**（`NFR31` 要求的"知识库更新不需发版"同理适用于配置）
- 修改动作写审计日志
- 涉及检索模式的配置（`retrieval.mode`）修改后需重新检索才生效

**示例请求**

```bash
curl -X PUT "https://medical-guidance.example.com/api/v1/admin/configs/triage.confidence_threshold" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{"config_value": "0.65", "remark": "临床反馈低置信度转人工过多，略微上调阈值"}'
```

#### 12.10.5 查询模型配置列表

**接口路径**：`GET /api/v1/admin/model-providers`
**功能说明**：查询推理后端的配置列表，支撑配置化切换（对应 `NFR68`）

**查询参数**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `provider_type` | string | 否 | — | `LLM` / `EMBEDDING` / `RERANK` / `ASR` |
| `status` | string | 否 | — | `1` 启用 / `0` 停用 |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "items": [
      {
        "provider_id": "e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0",
        "provider_code": "default_llm",
        "provider_type": "LLM",
        "provider_type_label": "内容生成",
        "provider_name": "默认内容生成服务",
        "base_url": "https://api.siliconflow.cn/v1",
        "model_name": "Qwen/Qwen2.5-32B-Instruct",
        "api_key_masked": "sk-u****wbch",
        "is_default": true,
        "is_on_prem": false,
        "timeout_seconds": 60,
        "status": "1"
      }
    ],
    "total": 3,
    "on_prem_warning": true
  },
  "message": "成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `api_key_masked` | string | 密钥**脱敏展示，仅显示末 4 位**（`NFR17`） |
| `is_on_prem` | boolean | 是否院内地址。供出域守卫直接依据配置判定 |
| `on_prem_warning` | boolean | **是否存在指向院外地址的配置**。交付环境为 `true` 时须告警（`NFR19`） |

**错误码**：`401` 未认证 ｜ `403` 无权限

**业务规则**：`base_url` 与 `model_name` 可读，`api_key` **永不返回明文**

**示例请求**

```bash
curl -X GET "https://medical-guidance.example.com/api/v1/admin/model-providers?provider_type=LLM" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### 12.10.6 新增模型配置

**接口路径**：`POST /api/v1/admin/model-providers`
**功能说明**：新增一个推理后端配置（对应 `NFR68`）

**请求体**

```json
{
  "provider_code": "onprem_vllm",
  "provider_type": "LLM",
  "provider_name": "院内 vLLM 推理服务",
  "base_url": "http://vllm-svc.intranet:8000/v1",
  "model_name": "Qwen2.5-32B-Instruct-AWQ",
  "api_key": "",
  "is_on_prem": true,
  "timeout_seconds": 60,
  "extra_json": {"temperature": 0.2, "max_tokens": 2048}
}
```

**请求体字段说明**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `provider_code` | string | 是 | 配置编码，租户内唯一 |
| `provider_type` | string | 是 | `LLM` / `EMBEDDING` / `RERANK` / `ASR` |
| `base_url` | string | 是 | 服务地址。**须提供 OpenAI 兼容接口** |
| `model_name` | string | 否 | 模型名称 |
| `api_key` | string | 否 | 访问密钥。**服务端加密存储**；内网服务可为空 |
| `is_on_prem` | boolean | 否 | 是否院内地址，默认 `false` |
| `timeout_seconds` | integer | 否 | 调用超时，默认 60 |
| `extra_json` | object | 否 | 扩展参数（温度、最大输出长度等） |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "provider_id": "f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1",
    "provider_code": "onprem_vllm",
    "is_default": false,
    "status": "1",
    "connectivity_checked": true,
    "connectivity_ok": true,
    "created_time": "2026-10-15T21:10:00+08:00"
  },
  "message": "新增成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `connectivity_checked` | boolean | 是否执行了连通性检查 |
| `connectivity_ok` | boolean | **连通性检查结果**。为 `false` 时配置仍保存但 `status` 置为 `0`（停用），避免误启用不可用后端 |

**错误码**

| code | message | 说明 |
|---|---|---|
| `400` | 参数校验失败 | `provider_code` 重复，或 `base_url` 格式非法 |
| `403` | 无权限 | 非机构管理员 |
| `401` | 未认证 | 缺少令牌 |

**业务规则**

- 新增时**执行连通性检查**（发一次轻量请求验证地址与密钥）
- 连通性检查失败时**保存但停用**，需管理员确认后再启用
- `api_key` 加密存储，**不落明文**
- 同类型的**默认配置唯一**（见 12.10.8）

**示例请求**

```bash
curl -X POST "https://medical-guidance.example.com/api/v1/admin/model-providers" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{
    "provider_code": "onprem_vllm",
    "provider_type": "LLM",
    "provider_name": "院内 vLLM 推理服务",
    "base_url": "http://vllm-svc.intranet:8000/v1",
    "model_name": "Qwen2.5-32B-Instruct-AWQ",
    "is_on_prem": true
  }'
```

#### 12.10.7 修改模型配置

**接口路径**：`PUT /api/v1/admin/model-providers/{provider_id}`
**功能说明**：修改推理后端配置（对应 `NFR68`）

**路径参数**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `provider_id` | string | 是 | 配置标识 |

**请求体**

```json
{
  "base_url": "http://vllm-svc.intranet:8080/v1",
  "model_name": "Qwen2.5-32B-Instruct-AWQ",
  "api_key": "new-internal-token",
  "timeout_seconds": 90,
  "status": "1"
}
```

**请求体字段说明**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `api_key` | string | 否 | 传值时**覆盖**原密钥；不传时保持原值（前端展示的是脱敏值，无法回传） |
| 其余字段 | — | 否 | 同 12.10.6 |
| `provider_code` / `provider_type` | — | **不可修改** | 传入时返回 `400` |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "provider_id": "f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1",
    "connectivity_checked": true,
    "connectivity_ok": true,
    "update_time": "2026-10-15T21:15:00+08:00"
  },
  "message": "修改成功"
}
```

**错误码**

| code | message | 说明 |
|---|---|---|
| `50009` | 模型配置不存在 | `provider_id` 无效 |
| `400` | 参数校验失败 | 尝试修改 `provider_code` 或 `provider_type` |
| `403` | 无权限 | 非机构管理员 |
| `401` | 未认证 | 缺少令牌 |

**业务规则**

- 修改 `base_url` 或密钥时**重新执行连通性检查**
- **`provider_type` 不可修改**：同一配置不能从"内容生成"改为"精排"——语义完全不同，应新建配置

**示例请求**

```bash
curl -X PUT "https://medical-guidance.example.com/api/v1/admin/model-providers/f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{"base_url": "http://vllm-svc.intranet:8080/v1", "timeout_seconds": 90, "status": "1"}'
```

#### 12.10.8 设置默认模型配置

**接口路径**：`POST /api/v1/admin/model-providers/{provider_id}/set-default`
**功能说明**：将某个配置设为该类型的默认后端（对应 `NFR68`）

**路径参数**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `provider_id` | string | 是 | 配置标识 |

**请求体**

```json
{
  "effective_scope": "IMMEDIATE"
}
```

**请求体字段说明**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `effective_scope` | string | 否 | `IMMEDIATE` 立即生效（默认）/ `NEXT_SESSION` 下个会话生效 |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "provider_id": "f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1",
    "provider_type": "LLM",
    "is_default": true,
    "previous_default_id": "e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0",
    "effective_scope": "IMMEDIATE",
    "updated_time": "2026-10-15T21:20:00+08:00"
  },
  "message": "已设为默认"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `previous_default_id` | string | 被替换的原默认配置标识。**用于回滚** |

**错误码**

| code | message | 说明 |
|---|---|---|
| `50009` | 模型配置不存在 | `provider_id` 无效 |
| `50010` | 该类型已有默认配置 | 并发设置冲突，需重试 |
| `422` | 业务规则校验失败 | 目标配置状态为停用，不可设为默认 |
| `403` | 无权限 | 非机构管理员 |
| `401` | 未认证 | 缺少令牌 |

**业务规则**

- **同类型默认配置唯一**：设置新默认时自动取消原默认（事务内完成）
- **停用的配置不可设为默认**：避免默认后端不可用
- 该操作是 `NFR68`"配置切换推理后端、业务代码零改动"的落地入口
- 变更动作写审计日志

**示例请求**

```bash
curl -X POST "https://medical-guidance.example.com/api/v1/admin/model-providers/f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1/set-default" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{"effective_scope": "IMMEDIATE"}'
```

### 12.11 审计

> 权限要求：**`ORG_ADMIN`**。统一限流 **600 次 / 分钟**。

#### 12.11.1 查询审计日志

**接口路径**：`GET /api/v1/admin/audit-logs`
**功能说明**：分页查询审计记录，支持按操作类型、患者、操作人筛选（对应 `F53`）

**查询参数**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `page` / `size` | integer | 否 | `1` / `20` | 分页，`size` 上限 100 |
| `action_type` | string | 否 | — | 操作类型，见 6.3 节枚举字典 |
| `actor_id` | string | 否 | — | 操作人标识 |
| `patient_hash` | string | 否 | — | 患者标识哈希 |
| `session_id` | string | 否 | — | 会话标识 |
| `result` | string | 否 | — | `SUCCESS` / `FAILURE` |
| `trace_id` | string | 否 | — | 追踪标识，用于关联可观测链路 |
| `start_time` / `end_time` | string | 否 | — | 操作时间范围（ISO 8601） |
| `sort_order` | string | 否 | `desc` | 固定按 `action_time` 排序 |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "total": 1284,
    "page": 1,
    "size": 20,
    "items": [
      {
        "audit_id": "a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2",
        "actor_id": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
        "actor_role": "DOCTOR",
        "action_type": "EMR_READ",
        "action_type_label": "病历读取",
        "target_type": "mg_emr_document",
        "target_id": "a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2",
        "patient_hash": "9f8e7d6c5b4a39281706f5e4d3c2b1a0",
        "session_id": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
        "result": "SUCCESS",
        "client_ip": "10.20.31.55",
        "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
        "action_time": "2026-10-15T19:41:22+08:00"
      }
    ]
  },
  "message": "成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `action_type_label` | string | 操作类型中文名 |
| `patient_hash` | string | 患者标识哈希，**不返回明文**（`AC-F53-3`） |
| `client_ip` | string | 客户端地址，用于安全审计 |

**错误码**

| code | message | 说明 |
|---|---|---|
| `403` | 无权限 | 非机构管理员。**医生与知识库管理员不可查审计** |
| `400` | 参数校验失败 | 时间范围超过 90 天（须分批查询） |
| `401` | 未认证 | 缺少令牌 |

**业务规则**

- 审计记录**只读**：本模块不提供修改与删除接口（`NFR21`）
- **时间范围跨度限制为 90 天**：避免大范围扫描影响性能
- 查询动作本身也写审计（`action_type = 'PERM_CHANGE'` 不适用，此处记录为查询行为）
- 审计数据保留不少于 1 年（`NFR20`）

**示例请求**

```bash
curl -X GET "https://medical-guidance.example.com/api/v1/admin/audit-logs?page=1&size=20&action_type=EMR_READ&start_time=2026-10-01T00:00:00%2B08:00&end_time=2026-10-15T23:59:59%2B08:00" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### 12.11.2 查询出域拦截记录

**接口路径**：`GET /api/v1/admin/audit-logs/egress-blocks`
**功能说明**：查询数据出域被拦截的记录（对应 `F52`、架构文档 §10.5）

**查询参数**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `page` / `size` | integer | 否 | `1` / `20` | 分页 |
| `start_time` / `end_time` | string | 否 | 近 7 天 | 时间范围 |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "total": 0,
    "page": 1,
    "size": 20,
    "items": [],
    "alert_triggered": false,
    "note": "正常运行的系统中该记录数应为 0。出现非零记录说明存在配置错误或代码绕过守卫的情况"
  },
  "message": "成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `alert_triggered` | boolean | **总数大于 0 时为 `true`**，监控系统据此告警 |
| `note` | string | 说明文案，可直接展示给管理员 |

**错误码**：`403` 无权限 ｜ `401` 未认证

**业务规则**

- **记录数大于 0 即告警**（架构文档 §10.5）——正常系统中不应出现出域拦截
- 该接口是安全巡检的入口，配合监控告警使用
- 每条记录含被拦截的能力名与目标地址，便于定位问题

**示例请求**

```bash
curl -X GET "https://medical-guidance.example.com/api/v1/admin/audit-logs/egress-blocks?page=1&size=20" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### 12.12 文件与系统

#### 12.12.1 上传文件

**接口路径**：`POST /api/v1/files/upload`
**功能说明**：上传图片或音频文件（对应 `F03`、`F21`）
**权限要求**：任意已认证角色

**请求头**：`Authorization` 是 ｜ `Content-Type` 是 `multipart/form-data`

**请求体**（表单字段）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `file` | file | 是 | 文件内容，图片 ≤ 5 MB，音频 ≤ 10 MB |
| `biz_type` | string | 是 | `EMR_ATTACHMENT` / `VOICE_INPUT` / `OTHER` |
| `session_id` | string | 否 | 关联会话标识，`VOICE_INPUT` 时必填 |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "file_id": "a9b8c7d6e5f4a3b2c1d0e9f8a7b6c5d4",
    "file_name": "report.jpg",
    "file_size": 1048576,
    "content_type": "image/jpeg",
    "biz_type": "EMR_ATTACHMENT",
    "url": "/api/v1/files/a9b8c7d6e5f4a3b2c1d0e9f8a7b6c5d4",
    "uploaded_time": "2026-10-15T21:25:00+08:00"
  },
  "message": "成功"
}
```

**响应字段说明**：见第 10 章文件上传规范

**错误码**

| code | message | 说明 |
|---|---|---|
| `60009` | 文件格式不支持 | 扩展名或**魔数**不在白名单 |
| `60010` | 文件大小超限 | 超过对应类型上限 |
| `400` | 参数校验失败 | 缺少 `file` 或 `biz_type` |
| `429` | 请求过于频繁 | 超过 20 次 / 分钟 |
| `401` | 未认证 | 缺少令牌 |

**业务规则**

- **类型校验以文件魔数为准**，不信任 `Content-Type` 与扩展名（第 10 章）
- **服务端重命名文件**，不使用客户端提供的文件名做存储路径（防路径穿越）
- **图片去除 EXIF 信息**（含 GPS 定位等个人标识）
- 存储按 `tenant_id` 分目录前缀

**限流**：20 次 / 分钟（按账号标识）

**示例请求**

```bash
curl -X POST "https://medical-guidance.example.com/api/v1/files/upload" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -F "file=@/path/to/report.jpg" \
  -F "biz_type=EMR_ATTACHMENT" \
  -F "session_id=a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
```

#### 12.12.2 下载文件

**接口路径**：`GET /api/v1/files/{file_id}`
**功能说明**：下载或预览已上传的文件
**权限要求**：任意已认证角色（**须校验文件归属租户与会话权限**）

**路径参数**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `file_id` | string | 是 | 文件标识 |

**查询参数**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `disposition` | string | 否 | `inline` | `inline` 预览 / `attachment` 下载 |

**响应**：**二进制流**，不适用统一响应结构

| Header | 说明 |
|---|---|
| `Content-Type` | 文件 MIME 类型 |
| `Content-Length` | 文件大小 |
| `Content-Disposition` | 由 `disposition` 参数决定 |
| `Cache-Control` | `private, max-age=3600` |

**错误码**

| code | message | 说明 |
|---|---|---|
| `404` | 资源不存在 | 文件不存在或不属于当前租户 |
| `403` | 无权限 | 医生未接诊该患者，或患者访问他人文件 |
| `401` | 未认证 | 缺少令牌 |

**业务规则**：**不允许通过 URL 直接访问对象存储**，所有文件访问经本接口鉴权

**示例请求**

```bash
curl -X GET "https://medical-guidance.example.com/api/v1/files/a9b8c7d6e5f4a3b2c1d0e9f8a7b6c5d4?disposition=attachment" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -o report.jpg
```

#### 12.12.3 系统自检

**接口路径**：`GET /api/v1/system/info`
**功能说明**：返回当前系统状态与生效配置（脱敏），用于排查"改了配置是否生效"（对应 `NFR69`）
**权限要求**：`ORG_ADMIN`

**响应示例**

```json
{
  "code": 200,
  "data": {
    "app_env": "development",
    "egress_policy": "dev_sandbox",
    "version": "0.1.0",
    "started_time": "2026-10-15T18:00:00+08:00",
    "llm": {
      "base_url": "https://api.siliconflow.cn/v1",
      "model": "Qwen/Qwen2.5-32B-Instruct",
      "is_on_prem": false
    },
    "embedding": {
      "provider": "local",
      "model": "BAAI/bge-m3",
      "supports_sparse": true
    },
    "rerank": {
      "base_url": "https://api.siliconflow.cn/v1",
      "model": "BAAI/bge-reranker-v2-m3",
      "enabled": true
    },
    "storage": {
      "milvus_uri": "./data/milvus/dev.db",
      "database": "postgresql",
      "redis": "connected"
    },
    "features": {
      "asr_enabled": false,
      "tracing_enabled": false
    }
  },
  "message": "成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `app_env` | string | 运行环境：`development` / `on_prem` |
| `egress_policy` | string | 数据出域策略：`strict`（交付形态，**默认**）/ `dev_sandbox`（开发形态）。为 `dev_sandbox` 时**前端必须展示醒目标识条**，提示当前含合成数据出域（`NFR70`） |
| `embedding.supports_sparse` | boolean | **向量化后端是否产出稀疏向量**。为 `false` 说明混合检索已退化为纯语义 |
| `storage.redis` | string | 缓存连接状态 |

**错误码**

| code | message | 说明 |
|---|---|---|
| `403` | 无权限 | 非机构管理员 |
| `401` | 未认证 | 缺少令牌 |

**业务规则**

- **所有密钥类字段以脱敏形式返回**
- 该接口用于确认"配置切换是否真的生效"——这是 `NFR68` 可运维性的保障
- **不在响应中返回任何患者数据**
- `egress_policy` 是开发形态能否调用院外推理服务的**唯一判据**，取值定义见 01 文档 8.1.2 与 02 文档 8.2 节。**取值拼写错误必须导致启动失败**，不得静默回退到默认值——否则会出现"以为在 strict 下运行，实际在放行"的情况

**示例请求**

```bash
curl -X GET "https://medical-guidance.example.com/api/v1/system/info" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### 12.12.4 健康检查

**接口路径**：`GET /healthz`
**功能说明**：容器探针使用的健康检查端点（**不带 `/api/v1` 前缀**）
**权限要求**：**无需认证**

**请求头**：无 ｜ **路径参数**：无 ｜ **查询参数**：无 ｜ **请求体**：无

**响应示例**

```json
{
  "code": 200,
  "data": {
    "status": "ok",
    "app_env": "development",
    "egress_policy": "dev_sandbox"
  },
  "message": "成功"
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| `status` | string | `ok` 正常 / `degraded` 降级中 |

**错误码**

| code | message | 说明 |
|---|---|---|
| `503` | 服务暂不可用 | 关键依赖不可用。**此时返回此码使探针判定为不健康** |

**业务规则**

- **不受限流限制**（第 9 章）——探针若被限流会导致误判服务不可用
- **不校验认证**——探针无法携带令牌
- **不返回任何敏感信息**：只有环境与出域策略，无地址、无密钥
- 响应时间应小于 100 毫秒，不做依赖深度探测

**示例请求**

```bash
curl -X GET "https://medical-guidance.example.com/healthz"
```

---

## 13. OpenAPI 文档

系统基于 FastAPI 构建，**自动生成** OpenAPI 3.1 规范文档，无需手工维护。

| 路径 | 说明 | 访问权限 |
|---|---|---|
| `/docs` | Swagger UI 交互式文档，可直接发请求调试 | 仅开发环境开放 |
| `/redoc` | ReDoc 只读文档，适合阅读与打印 | 仅开发环境开放 |
| `/openapi.json` | OpenAPI 3.1 规范原始文件，供代码生成与工具集成 | 仅开发环境开放 |

**开关控制**

| 配置项 | 取值 | 说明 |
|---|---|---|
| `DEBUG_ENDPOINTS` | `true` / `false` | 控制 `/docs`、`/redoc`、`/openapi.json` 是否开放。**交付环境必须为 `false`** |

**为什么交付环境关闭**

三个文档端点会暴露完整的接口清单与字段结构，属于信息泄露面。医院内网部署时关闭，接口文档以本文档为准离线提供。

**FastAPI 中的应用配置示例**

```python
from fastapi import FastAPI

app = FastAPI(
    title="MedicalGuidance API",
    version="1.0.0",
    description="医疗智能导诊分诊与多学科会诊多智能体系统接口",
    docs_url="/docs" if settings.debug_endpoints else None,
    redoc_url="/redoc" if settings.debug_endpoints else None,
    openapi_url="/openapi.json" if settings.debug_endpoints else None,
    openapi_tags=[
        {"name": "认证与用户", "description": "登录、令牌、身份信息"},
        {"name": "患者端", "description": "预问诊、分诊、挂号"},
        {"name": "医生端", "description": "接诊、分诊处理、病历查阅"},
        {"name": "知识库管理", "description": "条目、发布、入库任务"},
        {"name": "检索验证", "description": "检索测试台、回归验证"},
        {"name": "账号与机构", "description": "用户与科室管理"},
        {"name": "系统与模型配置", "description": "机构信息、系统配置、模型后端"},
        {"name": "审计", "description": "审计日志与出域拦截记录"},
    ],
)
```

**代码生成**：前端的类型定义可从 `/openapi.json` 生成，避免手工维护两套类型定义导致字段不一致。

```bash
# 示例：使用 openapi-typescript 生成前端类型
npx openapi-typescript http://localhost:8000/openapi.json -o frontend/packages/shared/src/types/api.d.ts
```

---

## 14. 接口清单汇总

共 **12 个模块、75 个接口**。

**图例**：权限列中，`公开` 表示无需认证；`任意` 表示任意已认证角色。

| # | 模块 | 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|---|---|
| 1 | 认证与用户 | POST | `/api/v1/auth/patient/session` | 患者匿名会话创建 | 公开 |
| 2 | 认证与用户 | POST | `/api/v1/auth/sms-code` | 发送手机验证码 | 公开 |
| 3 | 认证与用户 | POST | `/api/v1/auth/patient/verify` | 患者手机号验证 | `PATIENT`（匿名） |
| 4 | 认证与用户 | POST | `/api/v1/auth/staff/login` | 院内用户登录 | 公开 |
| 5 | 认证与用户 | POST | `/api/v1/auth/refresh` | 刷新访问令牌 | 公开（需 refresh_token） |
| 6 | 认证与用户 | POST | `/api/v1/auth/logout` | 登出 | 任意 |
| 7 | 认证与用户 | GET | `/api/v1/auth/me` | 获取当前身份信息 | 任意 |
| 8 | 认证与用户 | PUT | `/api/v1/auth/password` | 修改口令 | `DOCTOR` / `KB_ADMIN` / `ORG_ADMIN` |
| 9 | 患者端·预问诊 | POST | `/api/v1/patient/sessions` | 创建预问诊会话 | `PATIENT` |
| 10 | 患者端·预问诊 | GET | `/api/v1/patient/sessions` | 查询会话列表 | `PATIENT` |
| 11 | 患者端·预问诊 | GET | `/api/v1/patient/sessions/{session_id}` | 查询会话详情 | `PATIENT`（仅本人） |
| 12 | 患者端·预问诊 | POST | `/api/v1/patient/sessions/{session_id}/messages` | 发送消息 | `PATIENT`（仅本人） |
| 13 | 患者端·预问诊 | GET | `/api/v1/patient/sessions/{session_id}/messages` | 查询消息列表 | `PATIENT`（仅本人） |
| 14 | 患者端·预问诊 | POST | `/api/v1/patient/sessions/{session_id}/resume` | 恢复会话 | `PATIENT`（仅本人） |
| 15 | 患者端·预问诊 | POST | `/api/v1/patient/sessions/{session_id}/consent` | 提交既往病历调阅授权 | `PATIENT`（须实名） |
| 16 | 患者端·预问诊 | GET | `/api/v1/patient/body-map` | 获取人体部位图 | `PATIENT` |
| 17 | 患者端·分诊挂号 | GET | `/api/v1/patient/sessions/{session_id}/triage` | 查询分诊结果 | `PATIENT`（仅本人） |
| 18 | 患者端·分诊挂号 | GET | `/api/v1/patient/sessions/{session_id}/emr` | 查询预问诊病历（患者视图） | `PATIENT`（仅本人） |
| 19 | 患者端·分诊挂号 | GET | `/api/v1/patient/slots` | 查询号源 | `PATIENT` |
| 20 | 患者端·分诊挂号 | POST | `/api/v1/patient/appointments` | 提交挂号 | `PATIENT`（须实名） |
| 21 | 患者端·分诊挂号 | GET | `/api/v1/patient/appointments` | 查询挂号列表 | `PATIENT` |
| 22 | 患者端·分诊挂号 | DELETE | `/api/v1/patient/appointments/{appointment_id}` | 取消挂号 | `PATIENT`（仅本人） |
| 23 | 患者端·语音摘要 | POST | `/api/v1/patient/asr/transcribe` | 语音转写 | `PATIENT` |
| 24 | 患者端·语音摘要 | GET | `/api/v1/patient/sessions/{session_id}/summary` | 查询症状摘要 | `PATIENT`（仅本人） |
| 25 | 患者端·语音摘要 | GET | `/api/v1/patient/history` | 查询历史会话【二期工程】 | `PATIENT`（须实名） |
| 26 | 医生端·接诊分诊 | GET | `/api/v1/doctor/encounters` | 查询今日接诊列表 | `DOCTOR` |
| 27 | 医生端·接诊分诊 | GET | `/api/v1/doctor/sessions/{session_id}` | 查询会话详情（医生视图） | `DOCTOR`（仅接诊） |
| 28 | 医生端·接诊分诊 | GET | `/api/v1/doctor/sessions/{session_id}/messages` | 查询完整对话记录 | `DOCTOR`（仅接诊） |
| 29 | 医生端·接诊分诊 | GET | `/api/v1/doctor/sessions/{session_id}/emr` | 查询 SOAP 病历（医生视图） | `DOCTOR`（仅接诊） |
| 30 | 医生端·接诊分诊 | GET | `/api/v1/doctor/sessions/{session_id}/diagnosis` | 查询鉴别诊断候选与依据 | `DOCTOR`（仅接诊，**患者不可访问**） |
| 31 | 医生端·接诊分诊 | POST | `/api/v1/doctor/sessions/{session_id}/confirm` | 确认分诊建议 | `DOCTOR`（仅接诊） |
| 32 | 医生端·接诊分诊 | POST | `/api/v1/doctor/sessions/{session_id}/correct` | 修正分诊建议 | `DOCTOR`（仅接诊） |
| 33 | 医生端·接诊分诊 | GET | `/api/v1/doctor/takeover-queue` | 查询待接管队列 | `DOCTOR` |
| 34 | 医生端·接诊分诊 | POST | `/api/v1/doctor/takeover-queue/{session_id}/take` | 接管会话 | `DOCTOR` |
| 35 | 医生端·病历患者 | GET | `/api/v1/doctor/patients/{patient_id}/records` | 查阅患者既往病历 | `DOCTOR`（仅接诊 + 患者已授权） |
| 36 | 医生端·病历患者 | GET | `/api/v1/doctor/patients/{patient_id}/summaries` | 查询患者预问诊摘要列表 | `DOCTOR`（仅接诊） |
| 37 | 知识库管理 | GET | `/api/v1/admin/kb/entries` | 查询知识库条目列表 | `KB_ADMIN` / `ORG_ADMIN`（只读） |
| 38 | 知识库管理 | POST | `/api/v1/admin/kb/entries` | 新增知识库条目 | `KB_ADMIN` |
| 39 | 知识库管理 | GET | `/api/v1/admin/kb/entries/{entry_id}` | 查询条目详情 | `KB_ADMIN` / `ORG_ADMIN`（只读） |
| 40 | 知识库管理 | PUT | `/api/v1/admin/kb/entries/{entry_id}` | 修改知识库条目 | `KB_ADMIN` |
| 41 | 知识库管理 | POST | `/api/v1/admin/kb/entries/{entry_id}/status` | 启停知识库条目 | `KB_ADMIN` |
| 42 | 知识库管理 | GET | `/api/v1/admin/kb/entries/{entry_id}/history` | 查询条目变更历史 | `KB_ADMIN` / `ORG_ADMIN`（只读） |
| 43 | 知识库管理 | POST | `/api/v1/admin/kb/publish` | 发布知识库 | `KB_ADMIN` |
| 44 | 知识库管理 | GET | `/api/v1/admin/kb/publish` | 查询发布版本列表 | `KB_ADMIN` / `ORG_ADMIN`（只读） |
| 45 | 知识库管理 | POST | `/api/v1/admin/kb/tasks/ingest` | 触发知识库入库 | `KB_ADMIN` |
| 46 | 知识库管理 | GET | `/api/v1/admin/kb/tasks` | 查询入库任务列表 | `KB_ADMIN` / `ORG_ADMIN`（只读） |
| 47 | 知识库管理 | GET | `/api/v1/admin/kb/tasks/{task_id}` | 查询入库任务详情 | `KB_ADMIN` / `ORG_ADMIN`（只读） |
| 48 | 知识库管理 | POST | `/api/v1/ws/ticket` | 换取 WebSocket 票据 | 任意 |
| 49 | 检索验证 | POST | `/api/v1/admin/retrieval/search` | 检索测试台（三路并列返回） | `KB_ADMIN` / `ORG_ADMIN` |
| 50 | 检索验证 | GET | `/api/v1/admin/retrieval/golden-queries` | 查询黄金查询用例列表 | `KB_ADMIN` / `ORG_ADMIN`（只读） |
| 51 | 检索验证 | POST | `/api/v1/admin/retrieval/golden-queries` | 新增黄金查询用例 | `KB_ADMIN` |
| 52 | 检索验证 | POST | `/api/v1/admin/retrieval/verify` | 执行回归验证 | `KB_ADMIN` / `ORG_ADMIN` |
| 53 | 检索验证 | GET | `/api/v1/admin/retrieval/runs` | 查询回归执行记录 | `KB_ADMIN` / `ORG_ADMIN`（只读） |
| 54 | 账号与机构 | GET | `/api/v1/admin/users` | 查询用户列表 | `ORG_ADMIN` |
| 55 | 账号与机构 | POST | `/api/v1/admin/users` | 创建用户 | `ORG_ADMIN` |
| 56 | 账号与机构 | PUT | `/api/v1/admin/users/{user_id}` | 修改用户 | `ORG_ADMIN` |
| 57 | 账号与机构 | POST | `/api/v1/admin/users/{user_id}/status` | 启停用户 | `ORG_ADMIN` |
| 58 | 账号与机构 | GET | `/api/v1/admin/depts` | 查询科室列表 | `DOCTOR` / `KB_ADMIN` / `ORG_ADMIN`（只读） |
| 59 | 账号与机构 | POST | `/api/v1/admin/depts` | 新增科室 | `ORG_ADMIN` |
| 60 | 账号与机构 | PUT | `/api/v1/admin/depts/{dept_id}` | 修改科室 | `ORG_ADMIN` |
| 61 | 账号与机构 | POST | `/api/v1/admin/depts/{dept_id}/status` | 启停科室 | `ORG_ADMIN` |
| 62 | 系统与模型配置 | GET | `/api/v1/admin/org` | 查询机构信息 | `ORG_ADMIN` |
| 63 | 系统与模型配置 | PUT | `/api/v1/admin/org` | 修改机构信息 | `ORG_ADMIN` |
| 64 | 系统与模型配置 | GET | `/api/v1/admin/configs` | 查询系统配置 | `KB_ADMIN`（只读）/ `ORG_ADMIN` |
| 65 | 系统与模型配置 | PUT | `/api/v1/admin/configs/{config_key}` | 修改系统配置 | `ORG_ADMIN` |
| 66 | 系统与模型配置 | GET | `/api/v1/admin/model-providers` | 查询模型配置列表 | `ORG_ADMIN` |
| 67 | 系统与模型配置 | POST | `/api/v1/admin/model-providers` | 新增模型配置 | `ORG_ADMIN` |
| 68 | 系统与模型配置 | PUT | `/api/v1/admin/model-providers/{provider_id}` | 修改模型配置 | `ORG_ADMIN` |
| 69 | 系统与模型配置 | POST | `/api/v1/admin/model-providers/{provider_id}/set-default` | 设置默认模型配置 | `ORG_ADMIN` |
| 70 | 审计 | GET | `/api/v1/admin/audit-logs` | 查询审计日志 | `ORG_ADMIN` |
| 71 | 审计 | GET | `/api/v1/admin/audit-logs/egress-blocks` | 查询出域拦截记录 | `ORG_ADMIN` |
| 72 | 文件与系统 | POST | `/api/v1/files/upload` | 上传文件 | 任意 |
| 73 | 文件与系统 | GET | `/api/v1/files/{file_id}` | 下载文件 | 任意（须校验归属） |
| 74 | 文件与系统 | GET | `/api/v1/system/info` | 系统自检 | `ORG_ADMIN` |
| 75 | 文件与系统 | GET | `/healthz` | 健康检查 | 公开 |

**WebSocket 通道（不计入上述计数）**

| 通道 | 路径 | 用途 | 权限 |
|---|---|---|---|
| 对话流式 | `/api/v1/ws/sessions/{session_id}` | 预问诊流式输出 | `PATIENT`（仅本人）/ `DOCTOR`（仅接诊） |
| 任务进度 | `/api/v1/ws/tasks/{task_id}` | 知识库入库进度 | `KB_ADMIN` / `ORG_ADMIN` |

**按模块统计**

| 模块 | 接口数 | 其中写接口 |
|---|---|---|
| 12.1 认证与用户 | 8 | 6 |
| 12.2 患者端 · 预问诊会话 | 8 | 4 |
| 12.3 患者端 · 分诊与挂号 | 6 | 3 |
| 12.4 患者端 · 语音与摘要 | 3 | 1 |
| 12.5 医生端 · 接诊与分诊 | 9 | 3 |
| 12.6 医生端 · 病历与患者 | 2 | 0 |
| 12.7 知识库管理 | 12 | 6 |
| 12.8 检索验证 | 5 | 3 |
| 12.9 账号与机构管理 | 8 | 6 |
| 12.10 系统与模型配置 | 8 | 5 |
| 12.11 审计 | 2 | 0 |
| 12.12 文件与系统 | 4 | 1 |
| **合计** | **75** | **38** |

---

## 15. 附录

### 15.1 请求/响应示例汇总

**最简请求（健康检查）**

```bash
curl -X GET "https://medical-guidance.example.com/healthz"
```

```json
{"code": 200, "data": {"status": "ok", "app_env": "development", "egress_policy": "dev_sandbox"}, "message": "成功"}
```

**带认证的 GET 请求**

```bash
curl -X GET "https://medical-guidance.example.com/api/v1/doctor/encounters?page=1&size=20" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "X-Request-ID: 7f3a9b2c1d4e5f6a7b8c9d0e1f2a3b4c"
```

**带幂等键的 POST 请求**

```bash
curl -X POST "https://medical-guidance.example.com/api/v1/patient/appointments" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: 3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f" \
  -d '{"slot_id": "HIS_SLOT_20261016_DIG_001", "dept_code": "DIG"}'
```

**按模块的典型响应**

| 模块 | 典型响应结构 | 备注 |
|---|---|---|
| 认证与用户 | `{access_token, refresh_token, expires_in, user{...}}` | 见 12.1.4 |
| 患者端会话 | `{session_id, session_no, status, expire_time, ws_url}` | 见 12.2.1 |
| 患者端分诊 | `{route, confidence, recommended_depts[], symptom_summary{}}` | **不含疾病名称** |
| 患者端挂号 | `{appointment_id, appointment_no, status, notice}` | 见 12.3.4 |
| 医生端接诊列表 | 分页对象，`items[].risk_flag` 为风险标记 | 见 12.5.1 |
| 医生端诊断参考 | `{candidates[], mdt{divergence{}}}` | **患者不可访问** |
| 知识库条目 | `{entry_id, entry_code, kb_type, status, is_active}` | 见 12.7.1 |
| 入库任务 | `{task_id, task_no, status, stage, progress, statistics}` | 见 12.7.11 |
| 检索测试台 | `{results{dense_only[], sparse_only[], hybrid[]}}` | 三路并列 |
| 回归验证 | `{pass_rate, baseline_rate, is_regression, failed_cases[]}` | 见 12.8.4 |
| 审计日志 | 分页对象，`items[].patient_hash` 为哈希 | 见 12.11.1 |

### 15.2 常见错误场景

| # | 场景 | 客户端表现 | 处理方式 |
|---|---|---|---|
| 1 | Token 过期 | `10004` | 自动调用 `/auth/refresh` 换新令牌后重放原请求；刷新失败跳登录 |
| 2 | Token 被篡改 | `10005` | 清除本地凭证，跳登录页 |
| 3 | 医生访问他人接诊患者 | `403` | 提示"无权访问该患者"，返回列表页 |
| 4 | 患者访问他人会话 | `404` | 提示"会话不存在"，返回首页（**不提示"无权限"**，避免探测） |
| 5 | 会话超过 24 小时恢复 | `20003` | 提示"上次问诊已过期，是否开始新问诊" |
| 6 | 向已结束会话发送消息 | `20002` | 禁用输入框，引导查看结果 |
| 7 | 危重症命中后继续发消息 | `20013` | 保持急诊引导全屏，禁用输入框 |
| 8 | 追问轮次达上限 | `20007` | 由服务端强制进入分诊决策，客户端不展示该错误 |
| 9 | 号源被并发占用 | `30002` | 刷新号源列表，提示"该号源已被预约" |
| 10 | 重复提交挂号 | `30004` | 视为成功，跳转到预约成功页（展示返回的原预约单号） |
| 11 | 匿名身份尝试挂号 | `403` | 弹出手机号验证弹窗，验证后重试 |
| 12 | 未授权调用病历查阅 | `20012` | 弹出授权说明弹窗，授权后重试 |
| 13 | 病历系统不可用 | `60001` | 提示"既往病历暂不可用"，**预问诊摘要仍正常展示** |
| 14 | 精排服务不可用 | `60006` | **流程不中断**，仅提示"结果可能略有差异" |
| 15 | 触发限流 | `429` | 按 `retry_after` 秒数倒计时后自动重试；同时展示友好提示 |
| 16 | 知识库条目并发编辑 | `409` | 提示"该条目已被修改，请刷新后重试"，并重新拉取最新内容 |
| 17 | 重复触发入库任务 | `40006` | 提示"已有入库任务执行中"，并提供跳转到任务详情的入口 |
| 18 | 停用被引用的科室 | `50003` | 展示引用该科室的条目清单，提供"强制停用"二次确认（`force=true`） |
| 19 | 修改配置取值非法 | `50008` | 前端按 `value_range` 提前校验；服务端仍拒绝并给出合法范围 |
| 20 | 上传文件格式不支持 | `60009` | 提示允许的格式列表，**以服务端魔数探测结果为准** |
| 21 | 出域拦截出现 | — | **不面向客户端**。由 12.11.2 接口暴露给管理员，记录数 > 0 时告警 |
| 22 | WebSocket 断开超过缓冲期 | `resync_required` 事件 | 通过 REST 重新拉取会话与消息全量，重建界面 |

### 15.3 修订记录

| 版本 | 日期 | 说明 |
|---|---|---|
| v1.0 | 2026-10-15 | 初版。依据《01-需求规格说明书》《02-系统架构设计说明书》《03-数据库设计说明书》编写。12 个模块、75 个 HTTP 接口、2 条 WebSocket 通道 |
| v1.1 | 2026-10-15 | 编码前审查修订：12.3.1 新增 `emergency_guidance` 字段（承载 `F11`），并标注 `disclaimer` 对应 `F12`；12.5.5 新增 `drug_safety` 用药禁忌校验结果（承载 `F47`）；12.12.3 的 `egress_policy` 取值统一为 `strict` / `dev_sandbox`，补充取值错误必须导致启动失败的约束；第 11 章通道表补充需求编号（含 `F40`）。**接口总数仍为 75 个，未新增接口** |
| v1.2 | 2026-10-15 | 对齐设计稿：项目名称补全为「多智能体系统」 |

---

**文档结束**








