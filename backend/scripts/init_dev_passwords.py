"""开发期：为种子账号生成真实 bcrypt 口令哈希。

init.sql 里的种子账号口令哈希是占位符（``$2b$12$REPLACE_WITH...``），
登录前必须替换为真实 bcrypt 哈希，否则 verify_password 恒为 False。

用法：在 backend 目录执行
    python scripts/init_dev_passwords.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import text  # noqa: E402  (需先把 backend 加入 sys.path)

from app.common.database import engine  # noqa: E402
from app.common.security import hash_password  # noqa: E402

# 与 init.sql 种子数据一致（账号 / 明文口令）
DEV_ACCOUNTS = {
    "admin": "admin123",
    "kbadmin": "admin123",
}


async def main() -> None:
    async with engine.begin() as conn:
        for account, password in DEV_ACCOUNTS.items():
            hashed = hash_password(password)
            result = await conn.execute(
                text(
                    "UPDATE mg_user SET credential_hash = :h, update_by = 'system', "
                    "update_time = now() WHERE account = :a"
                ),
                {"h": hashed, "a": account},
            )
            print(f"  {account}: 更新 {result.rowcount} 行口令哈希")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
