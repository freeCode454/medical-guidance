"""开发期种子数据补充：科室 + 医生用户。

init.sql 只种了租户 / admin / kbadmin / 模型配置，缺科室（mg_dept）与医生（mg_user DOCTOR）。
本脚本补充这两块，供医生端接口联调使用。

用法：在 backend 目录执行
    python scripts/seed_dev.py

幂等：ON CONFLICT / 存在则跳过，可重复执行。
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select  # noqa: E402

from app.common.database import AsyncSessionFactory  # noqa: E402
from app.common.security import hash_password  # noqa: E402
from app.models import Dept, User, gen_id  # noqa: E402

DEFAULT_TENANT_ID = "00000000000000000000000000000001"

# 与 scripts/seed_kb.py 的科室保持一致（向量库与关系库同源）
DEPTS = [
    ("DIG", "消化内科"), ("CAR", "心血管内科"), ("RES", "呼吸内科"),
    ("NEU", "神经内科"), ("END", "内分泌科"), ("URO", "泌尿外科"),
    ("GYN", "妇科"), ("OB", "产科"), ("ORTH", "骨科"),
    ("DERM", "皮肤科"), ("ENT", "耳鼻喉科"), ("OPH", "眼科"),
    ("PSY", "精神心理科"), ("EMER", "急诊科"),
]


async def seed_depts() -> int:
    count = 0
    async with AsyncSessionFactory() as db:
        for i, (code, name) in enumerate(DEPTS, start=1):
            existing = await db.scalar(
                select(Dept).where(
                    Dept.tenant_id == DEFAULT_TENANT_ID, Dept.dept_code == code
                )
            )
            if existing is not None:
                continue
            db.add(
                Dept(
                    id=gen_id(),
                    tenant_id=DEFAULT_TENANT_ID,
                    dept_code=code,
                    dept_name=name,
                    sort_no=i,
                    status="1",
                    create_by="system",
                )
            )
            count += 1
        await db.commit()
    return count


async def seed_doctor() -> int:
    count = 0
    async with AsyncSessionFactory() as db:
        existing = await db.scalar(
            select(User).where(
                User.tenant_id == DEFAULT_TENANT_ID, User.account == "doctor01"
            )
        )
        if existing is None:
            db.add(
                User(
                    id=gen_id(),
                    tenant_id=DEFAULT_TENANT_ID,
                    account="doctor01",
                    real_name="示例医生",
                    role="DOCTOR",
                    title="副主任医师",
                    dept_code="DIG",
                    credential_hash=hash_password("admin123"),
                    status="1",
                    create_by="system",
                )
            )
            count += 1
        await db.commit()
    return count


async def main() -> None:
    depts = await seed_depts()
    doctors = await seed_doctor()
    print(f"科室新增 {depts} 条，医生新增 {doctors} 条（幂等，已存在则跳过）")


if __name__ == "__main__":
    asyncio.run(main())
