# MedicalGuidance

医疗智能导诊分诊与多学科会诊**多智能体**系统。

患者用手机描述症状，系统通过多轮追问把模糊主诉问清楚，输出「该挂哪个科」和一份 SOAP
预问诊病历，医生接诊时直接看结论。系统**不做诊断**，只把「人工分诊台」与「医生开场问诊」
这两段最耗时、最容易出错的环节提前完成。

## 成果

200 例副主任医师盲测（单盲，标注时不看系统输出）：

| 指标 | 结果 |
|---|---|
| 首位分诊准确率 | 96.2%（Kappa 一致性 0.86） |
| 挂错号重退号比例 | 降低 85% |
| 医生单次接诊预问诊查阅耗时 | 节省 30% 以上 |

## 核心设计

四个 Agent 是同一张状态图上的节点，协同构成一个闭环：

```
                    ┌─────────────────────────────┐
                    │      危重症前置拦截          │  规则层优先，命中即中断
                    └──────────────┬──────────────┘
                                   │ 通过
患者描述症状 ──────► 澄清追问 Agent ─┴─► 导诊分流 Agent ──► MDT 会诊 Agent ──► 病历生成 Agent
  (文字/语音/点选)     多轮循环           混合检索+决策表      多专科并行          SOAP 病历
```

- **导诊分流 Agent** —— 调度者，只决定「下一步做什么」，不亲自执行能力
- **澄清追问 Agent** —— 把「肚子疼」追问成可决策的信息（时长、伴随症状、既往史），有轮次上限
- **MDT 会诊 Agent** —— 复杂共病并行唤起多个专科角色，**分歧必须保留，不许在汇总时抹平**
- **病历生成 Agent** —— 把整段对话整理成符合规范的 SOAP 预问诊病历

### 分诊链路：规则与检索各司其职

纯向量召回对「肚子疼」「胸口疼」这类口语主诉区分度不够（妇科、消化、产科都涉及腹痛），
所以分诊不是「一次向量检索 + 大模型自由裁决」，而是分层递进：

```
主诉
  → ① 红旗拦截（250 条急症规则 + 症状同义词归一化）命中即引导急诊
  → ② 结构化追问（250 条按主诉定制的追问模板，部位→时长→性质→伴随→程度）
  → ③ 向量召回（稠密 + 稀疏 + RRF 融合）
  → ④ rerank 精排（bge-reranker-v2-m3，权重 0.55）
  → ⑤ 分诊规则加权（症状→科室映射，权重 0.15）+ 人群硬过滤（性别/年龄）
  → ⑥ LLM 生成结论 + SOAP 病历
```

关键点：

- **同义词归一化**：规则表用标准症状名（腹痛/腹泻/胸痛），患者说的是口语
  （肚子疼/拉肚子/胸口疼），不归一化规则一条都命中不了——514 条映射是规则生效的前提。
- **规则加权 ≠ 规则过滤**：性别不符（如男性→妇科）必须在**候选层硬剔除**，
  否则 0.15 的加权压不过向量+精排的分差。
- **追问不靠大模型临场发挥**：按主诉类型走模板，顺序可预期，避免「尿频也问哪个部位」。

## 知识库数据资产

`kb/医学知识库源数据.xlsx` 是知识库的唯一源头（10 个 sheet / 2556 条），改数据 → 跑
`python backend/scripts/import_kb.py` 即同步到 PostgreSQL 与 Milvus：

| Sheet | 条数 | 用途 |
|---|---|---|
| 科室字典 | 252 | 41 个一级科室 + 211 个亚专科 |
| 医生信息 | 250 | 演示用医生账号 |
| 疾病特征库 | 251 | 症状 / 鉴别要点 / 高危因素 |
| 临床指南 | 250 | 指南片段 + 证据等级 |
| ICD-10 映射 | 250 | 疾病编码 / 章节 / 包含排除 |
| 症状本体库 | 289 | 标准名 / 同义词 / 部位 / 时长 |
| 红旗症状库 | 250 | 急症关键词 / 处置动作 / 提示文案 |
| 禁忌症与用药风险 | 264 | 过敏 / 妊娠 / 儿童 / 脏器禁忌 |
| 分诊规则 | 250 | 症状→科室映射 + 人群过滤 |
| 追问模板 | 250 | 按主诉定制的追问维度 |

> 数据为演示用示例，正式使用须经医学专业人士审核。

## 技术栈

| 层 | 选型 |
|---|---|
| 患者端 | Vue 3 + Vite + Vant 4（移动端 H5） |
| 医生端 / 管理后台 | Vue 3 + Element Plus |
| 接口 | FastAPI + WebSocket（对话流式） |
| 编排 | LangGraph（有环状态机、检查点持久化、人工介入挂起） |
| 模型 | Qwen2.5-32B（推理）+ Qwen2.5-7B（意图/抽取）；BGE-M3 本地向量化 + bge-reranker-v2-m3 精排 |
| 存储 | PostgreSQL + Milvus（混合检索）+ Redis + MinIO |
| 外部能力 | FastMCP 封装 HIS 号源/排班/既往病历 |
| 交付 | Docker Compose，前后端合并单镜像 |

> 技术栈按「一期必用 / 二期预留」两级标注，见《01-需求规格说明书》8.1.1。

## 目录结构

```
medical-guidance/
├── docs/               # 01 需求 / 02 架构 / 03 数据库 / 04 接口 四份设计文档
├── backend/            # FastAPI 后端（六层：接口/服务/编排/数据访问/能力/基础设施）
│   ├── app/
│   │   ├── api/        # 接口层（patient / doctor / admin / ws / auth）
│   │   ├── services/   # 服务层（业务用例 + 规则引擎 + 事务 + 审计）
│   │   ├── agents/     # 智能体编排层（LangGraph 图 + 节点）
│   │   ├── retrieval/  # 检索能力（向量化 / 向量库 / 融合）
│   │   ├── common/     # 基础设施（配置 / 数据库 / 鉴权 / LLM 客户端 / 出域守卫）
│   │   ├── models/     # 数据访问层（SQLAlchemy 模型）
│   │   ├── schemas/    # 请求/响应模型
│   │   ├── middleware/ # 中间件（租户上下文 / 限流）
│   │   ├── ws/         # WebSocket 流式通道
│   │   └── jobs/       # 异步任务（知识库入库/发布/回归）
│   ├── scripts/        # 工具脚本（种子数据 / 知识库生成与导入）
│   └── static/         # 本地托管的 Swagger UI 静态资源
├── mcp_servers/        # FastMCP 服务（HIS 挂号 / 病历查询 / 用药禁忌）
├── frontend/           # 三端
│   ├── patient_h5/     # 患者端 H5（Vant 4，核心问诊链路）
│   ├── doctor_web/     # 医生端（Element Plus，接诊工作台）
│   └── admin_web/      # 管理后台（Element Plus，用户/科室/知识库/审计）
├── kb/                 # 知识库数据资产
│   ├── 医学知识库源数据.xlsx  # 10 sheet / 2556 条（唯一源头）
│   └── rules.json      # 导入时生成：红旗/分诊/追问/同义词
└── deploy/             # docker-compose + init.sql + migrations
```

## 快速开始

**环境要求**：Docker Desktop、Python 3.11+（建议 conda）、Node 22+

```bash
# 1. 创建环境并装依赖
conda create -n medguide python=3.11 -y
conda activate medguide
pip install -r backend/requirements.txt

# 2. 启动基础设施（渐进式，本机内存有限时逐条来）
make db-up        # PostgreSQL（自动执行 init.sql 建 23 表）
make vector-up    # Milvus Standalone（etcd + minio + milvus）
make cache-up     # Redis（可选）
make storage-up   # MinIO（可选，已随 vector 起）

# 3. 配置并启动后端
cp backend/config/.env.development.example backend/.env  # 填入 LLM_API_KEY
make dev          # uvicorn 热重载，http://localhost:8000

# 4. 自检
make check        # 配置 / 云端 API / 出域守卫
make probe-vector # 向量库能力边界

# 5. 初始化演示数据 + 知识库（Excel → PostgreSQL + Milvus）
cd backend
python scripts/seed_dev.py        # 租户/用户/科室/系统配置/模型配置
python scripts/gen_kb_excel.py    # 生成 kb/医学知识库源数据.xlsx（2556 条）
python scripts/import_kb.py       # 导入 mg_kb_entry + Milvus + rules.json

# 6. 启动三端前端（另开终端）
cd frontend/patient_h5 && npm install && npm run dev   # 患者端  http://localhost:5173
cd frontend/doctor_web && npm install && npm run dev   # 医生端  http://localhost:5174
cd frontend/admin_web  && npm install && npm run dev   # 管理后台 http://localhost:5175
```

演示账号：

| 端 | 账号 | 密码 |
|---|---|---|
| 医生端 | doctor01 | admin123 |
| 管理后台 | admin | admin123 |

后端 API 文档：<http://localhost:8000/docs>（Swagger UI 静态资源本地托管，不依赖公网 CDN）。

> ⚠️ 开发形态需设置 `EGRESS_POLICY=dev_sandbox`，且**只允许使用合成数据**；
> 交付形态必须是 `strict`（详见 02 文档 §8.2 与 `NFR70`）。

## 文档

| 文档 | 内容 |
|---|---|
| [01-需求规格说明书](docs/01-需求规格说明书.md) | 56 条功能需求、70 条非功能需求、12 条业务规则 |
| [02-系统架构设计说明书](docs/02-系统架构设计说明书.md) | 六层架构、10 条 ADR、出域守卫、中间件设计 |
| [03-数据库设计说明书](docs/03-数据库设计说明书.md) | 23 张表、67 个索引、Redis 键设计、RLS 迁移 |
| [04-API接口设计说明书](docs/04-API接口设计说明书.md) | 75 个接口、2 条 WebSocket 通道、87 个错误码 |

## License

见 [LICENSE](LICENSE)。
