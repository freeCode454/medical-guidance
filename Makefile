# MedicalGuidance 开发快捷命令
#
# ── 设计原则 ────────────────────────────────────────────────────────────
# 基础设施**渐进式启动**：本机可用内存有限，先起 PostgreSQL 验证建表，
# 确认余量后再逐个加 Redis 与 MinIO。每个目标都可以单独执行，出问题好回退。
#
# ── 环境变量 ────────────────────────────────────────────────────────────
# PY      后端解释器（默认用 backend/.venv，Windows 路径）
# COMPOSE compose 文件路径

SHELL   := /bin/bash
COMPOSE := docker compose -f deploy/docker-compose.infra.yml
PY      ?= backend/.venv/Scripts/python.exe
PIP     := backend/.venv/Scripts/pip.exe
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
	@$(PG) -c "SELECT count(*) AS 审计拦截函数 FROM pg_proc WHERE proname='fn_mg_audit_log_immutable';"
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
venv:  ## 创建后端虚拟环境
	python -m venv backend/.venv
	$(PIP) install -U pip
	@echo "虚拟环境已创建：backend/.venv"

install:  ## 安装后端依赖
	$(PIP) install -r backend/requirements.txt

dev:  ## 启动后端（热重载）
	cd backend && ../$(PY) -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

check:  ## 开发第一天必跑：环境自检
	@echo "── 配置 ──"
	@curl -s http://localhost:8000/debug/config | python -m json.tool || echo "后端未启动"
	@echo "── 云端 API 连通性 ──"
	@curl -s http://localhost:8000/debug/llm | python -m json.tool || echo "后端未启动"
	@echo "── 出域守卫判定 ──"
	@curl -s http://localhost:8000/debug/egress | python -m json.tool || echo "后端未启动"

probe-vector:  ## 探测向量库能力边界（Milvus Lite）
	cd backend && ../$(PY) scripts/probe_milvus_lite.py

# ══ 知识库 ═════════════════════════════════════════════════════════════
kb-validate:  ## 校验知识库源文件的 schema 与引用完整性
	cd backend && ../$(PY) -m app.jobs.kb_validate

kb-ingest:  ## 全量入库（长任务）
	cd backend && ../$(PY) -m app.jobs.kb_ingest

kb-verify:  ## 黄金查询集回归验证
	cd backend && ../$(PY) -m app.jobs.kb_verify

# ══ 质量 ═══════════════════════════════════════════════════════════════
lint:  ## 静态检查
	cd backend && ../.venv/Scripts/ruff.exe check app scripts

fmt:  ## 格式化
	cd backend && ../.venv/Scripts/ruff.exe format app scripts

typecheck:  ## 类型检查
	cd backend && ../.venv/Scripts/mypy.exe app

test:  ## 运行测试
	cd backend && ../.venv/Scripts/pytest.exe -q

.PHONY: help db-up vector-up cache-up storage-up infra-down infra-logs \
        db-verify db-tables db-reset venv install dev check probe-vector \
        kb-validate kb-ingest kb-verify lint fmt typecheck test
