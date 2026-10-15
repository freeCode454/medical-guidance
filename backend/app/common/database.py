"""数据库会话工厂：asyncpg 异步引擎 + 会话注入。

- 异步引擎：``create_async_engine``，``database_url`` 已是 ``postgresql+asyncpg://``
- ``pool_pre_ping=True``：连接池取连接前先探活，避免 DB 重启后拿到失效连接
- ``expire_on_commit=False``：提交后不使对象过期，便于在异步上下文里继续使用

多租户约定（与《02 架构》§8、§11.6 一致）：
    tenant_id 一律从 JWT/请求上下文取得，**不接受客户端传参**。
    一期不启用数据库 RLS；应用层以 ``tenant_id`` 条件强制隔离。
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
)

AsyncSessionFactory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI 依赖：提供数据库会话，请求结束自动关闭。"""
    async with AsyncSessionFactory() as session:
        yield session
