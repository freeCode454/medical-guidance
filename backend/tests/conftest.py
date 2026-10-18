"""测试环境默认值：单元测试不依赖真实数据库 / 模型 / 向量库。

必须在导入 `app.*` 之前设置，因此放在 conftest 顶层（pytest 会先导入它）。
真实 `.env` 的优先级低于进程环境变量，这里的值会覆盖开发配置。
"""
from __future__ import annotations

import asyncio
import os
import sys

# psycopg 异步连接不支持 Windows 默认的 ProactorEventLoop（检查点集成测试需要）
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

os.environ.setdefault("LLM_BASE_URL", "http://127.0.0.1:9999/v1")
os.environ.setdefault("EGRESS_POLICY", "strict")
os.environ.setdefault("EMBEDDING_PROVIDER", "api")
os.environ.setdefault("RERANK_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@127.0.0.1:5999/test")
os.environ.setdefault("MILVUS_URI", "http://127.0.0.1:5999")
os.environ.setdefault("DEPLOY_MODE", "dev")
