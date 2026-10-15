"""SQLAlchemy 声明基类与通用工具。

主键约定
--------
全库统一 32 位无连字符字符串主键，由**应用层**生成（``uuid4().hex``），
与 init.sql 中 ``replace(gen_random_uuid()::text, '-', '')`` 的结果一致。

不依赖数据库 ``server_default`` 生成主键的原因：插入后需要立即拿到 id
（如 audit_log 的 trace_id 关联、mg_session.id 直接作为编排层线程标识与
LangGraph 检查点 thread_id）。应用层生成可避免一次额外的 RETURNING 往返。

约束命名约定与 init.sql 显式命名一致（pk_/uk_/idx_），保证将来从模型生成
DDL 或 Alembic 迁移时不会产生与 init.sql 冲突的随机命名。
"""
from __future__ import annotations

from uuid import uuid4

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# 约束命名约定：与 init.sql 显式命名一致
NAMING_CONVENTION: dict[str, str] = {
    "ix": "idx_%(table_name)s_%(column_0_label)s",
    "uq": "uk_%(table_name)s_%(column_0_label)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """全库声明基类。"""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def gen_id() -> str:
    """生成 32 位无连字符主键。"""
    return uuid4().hex
