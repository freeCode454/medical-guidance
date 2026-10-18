# MedicalGuidance 开发快捷命令
#
# ── 设计原则 ────────────────────────────────────────────────────────────
# 基础设施**渐进式启动**：本机可用内存有限，先起 PostgreSQL 验证建表，
# 确认余量后再逐个加 Redis 与 MinIO。每个目标都可以单独执行，出问题好回退。
#
# ── 环境变量 ────────────────────────────────────────────────────────────
# PY       后端解释器（默认当前环境的 python；conda activate medguide 后直接 make）
# COMPOSE  compose 文件路径
#
# 本项目后端依赖以 backend/pyproject.toml 为唯一来源（requirements.txt 已移除）。

SHELL   := /bin/bash
COMPOSE := docker compose -f deploy/docker-compose.infra.yml
PY      ?= python
PG      := docker exec -i mg-postgres psql -U medguide -d medguide

.DEFAULT_GOAL := help

# ══ 帮助 ═══════════════════════════════════════════════════════════════
help:  ## 显示所有可用目标
	@grep -hE '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

# ══ 基础设施（渐进式） ═════════════════════════════════════════════════
db-up:  ## 第 1 步：只起 PostgreSQL
	$(COMPOSE) up -d postgres
	@echo "等待 PostgreSQL 就绪..."
	@$(COMPOSE) ps postgres

vector-up:  ## 第 2 步：起 Milvus Standalone（etcd + minio + milvus）
	$(COMPOSE) --profile vector up -d
	@$(COMPOSE) ps milvus

cache-up:  ## 第 3 步：确认内存余量后再起 Redis
	$(COMPOSE) --profile cache up -d redis
	@$(COMPOSE) ps redis

storage-up:  ## 第 4 步：起 MinIO（内存紧张时可跳过）
	$(COMPOSE) --profile storage up -d
	@$(COMPOSE) ps minio

infra-down:  ## 停止全部基础设施（保留数据）
	$(COMPOSE) --profile cache --profile storage down

infra-logs:  ## 查看基础设施日志
	$(COMPOSE) --profile cache --profile storage logs -f --tail=100

# ══ 数据库 ═════════════════════════════════════════════════════════════
db-verify:  ## 核对 init.sql 的建表结果（表 / 索引 / 触发器 / 种子数据）
	@$(PG) -c "SELECT count(*) AS 表数量 FROM information_schema.tables WHERE table_schema='public' AND table_name LIKE 'mg\_%';"
	@$(PG) -c "SELECT count(*) AS 索引数量 FROM pg_indexes WHERE schemaname='public' AND tablename LIKE 'mg\_%';"
	@$(PG) -c "SELECT count(*) AS 触发器数量 FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid WHERE NOT t.tgisinternal AND c.relname LIKE 'mg\_%';"
	@$(PG) -c "SELECT tenant_code, tenant_name FROM mg_tenant;"
	@$(PG) -c "SELECT account, role FROM mg_user ORDER BY account;"

db-tables:  ## 列出全部业务表
	@$(PG) -c "\dt mg_*"

db-reset:  ## ⚠️ 删除数据卷并重建（会丢失所有数据）
	@read -p "将删除全部数据，确认？[y/N] " ans && [ "$$ans" = "y" ] || exit 1
	$(COMPOSE) --profile cache --profile storage down -v
	rm -rf data/postgres data/redis data/minio
	$(MAKE) db-up

# ══ 应用 ═══════════════════════════════════════════════════════════════
install:  ## 安装后端依赖（pyproject 为唯一来源）
	cd backend && $(PY) -m pip install -e ".[dev]"

dev:  ## 启动后端（Windows 下自动使用 SelectorEventLoop，支持 PG 检查点）
	cd backend && $(PY) -m app

dev-reload:  ## 热重载开发（仅内存检查点；改代码自动重启）
	cd backend && CHECKPOINT_BACKEND=memory $(PY) -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

check:  ## 环境自检（需 DEBUG_ENDPOINTS=true）
	@echo "── 配置 ──"
	@curl -s http://localhost:8000/debug/config | $(PY) -m json.tool || echo "后端未启动"
	@echo "── 云端 API 连通性 ──"
	@curl -s http://localhost:8000/debug/llm | $(PY) -m json.tool || echo "后端未启动"
	@echo "── 出域守卫判定 ──"
	@curl -s http://localhost:8000/debug/egress | $(PY) -m json.tool || echo "后端未启动"

ready:  ## 检查依赖是否就绪（PostgreSQL + Milvus）
	@curl -s http://localhost:8000/readyz | $(PY) -m json.tool || echo "后端未启动"

# ══ 知识库 ═════════════════════════════════════════════════════════════
kb-gen:  ## 生成知识库源数据 Excel（kb/医学知识库源数据.xlsx）
	cd backend && $(PY) scripts/gen_kb_excel.py

kb-import:  ## Excel → PostgreSQL + Milvus + kb/rules.json
	cd backend && $(PY) scripts/import_kb.py

kg-build:  ## 从 Excel 抽三元组构建 Neo4j 知识图谱（需 Neo4j 运行）
	cd backend && $(PY) scripts/build_kg.py

kg-dept-network:  ## 图谱科室视角自检（示例：心血管内科）
	@curl -s "http://localhost:8000/api/v1/kg/dept-network?dept_code=CAR&limit=5" | $(PY) -m json.tool || echo "后端未启动"

neo4j:  ## 启动 Neo4j（绕过 Windows PowerShell 5.1 下有兼容 bug 的 neo4j.bat）
	cd /d/neo4jcommunity2026 && java -cp "lib/*;plugins/*" org.neo4j.server.startup.Neo4jCommand console

# ══ 质量 ═══════════════════════════════════════════════════════════════
lint:  ## 静态检查（后端 ruff）
	cd backend && $(PY) -m ruff check app tests scripts

fmt:  ## 格式化（后端 ruff format）
	cd backend && $(PY) -m ruff format app tests scripts

typecheck:  ## 后端类型检查（当前为报告模式，逐步收敛）
	cd backend && $(PY) -m mypy app

test-unit:  ## 后端单元测试（不依赖数据库/模型/向量库）
	cd backend && $(PY) -m pytest tests/unit -q

test-e2e:  ## 端到端冒烟（需后端 + PostgreSQL + Milvus + LLM）
	cd backend && $(PY) -m pytest tests/test_e2e_smoke.py -q

front-check:  ## 三端前端类型检查 + 构建
	cd frontend/patient_h5 && npm run typecheck && npm run build
	cd frontend/doctor_web && npm run typecheck && npm run build
	cd frontend/admin_web && npm run typecheck && npm run build

verify:  ## 提交前一次跑完：lint + 单测 + 三端构建
	$(MAKE) lint
	$(MAKE) test-unit
	$(MAKE) front-check

.PHONY: help db-up vector-up cache-up storage-up infra-down infra-logs \
        db-verify db-tables db-reset install dev dev-reload check ready \
        kb-gen kb-import kg-build kg-dept-network neo4j \
        lint fmt typecheck test-unit test-e2e front-check verify
