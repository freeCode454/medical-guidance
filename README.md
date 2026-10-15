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

## 技术栈

| 层 | 选型 |
|---|---|
| 患者端 | Vue 3 + Vite + Vant 4（移动端 H5，含人体部位点选） |
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
│   │   ├── api/        # 接口层（patient / doctor / admin / ws）
│   │   ├── services/   # 服务层（业务用例 + 事务 + 审计）
│   │   ├── agents/     # 智能体编排层（LangGraph 图 + 节点）
│   │   ├── retrieval/  # 检索能力（向量化 / 向量库 / 融合精排）
│   │   ├── nlp/        # 医学术语规范化（medical_ner）
│   │   ├── clients/    # 外部能力适配（LLM / 精排 / ASR / MCP）
│   │   ├── models/     # 数据访问层（SQLAlchemy 模型）
│   │   ├── repositories/  # 仓储（强制机构过滤）
│   │   └── jobs/       # 异步任务（知识库入库/发布/回归）
│   └── scripts/        # 工具脚本
├── mcp_servers/        # FastMCP 服务（HIS 挂号 / 病历查询 / 用药禁忌）
├── frontend/           # 三端（patient_h5 / doctor_web / admin_web）
├── kb/                 # 知识库源文件与黄金查询集（数据资产，独立版本管理）
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
```

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
