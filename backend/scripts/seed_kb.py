"""知识库种子数据：科室专长集合初始化。

用法：在 backend 目录执行
    python scripts/seed_kb.py

写入 Milvus 的 kb_dept 集合（科室专长），供分诊候选科室召回使用。
向量化走本地 BGE-M3（稠密 + 稀疏）。

⚠️ tenant_id 必须用 mg_tenant.id（32 位无连字符），与 JWT 中的 tenant_id 一致，
不能用 tenant_code（HOSP_001 是编码，不是隔离标识）。
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.common.embedder import build_embedder  # noqa: E402
from app.config import settings  # noqa: E402
from app.retrieval import KB_DEPT, MilvusStore  # noqa: E402

# 默认租户 id（对应 mg_tenant 种子数据 HOSP_001）
DEFAULT_TENANT_ID = "00000000000000000000000000000001"

# 科室专长：(dept_code, dept_name, 症状关键词描述)
DEPTS = [
    ("DIG", "消化内科", "腹痛 腹泻 恶心 呕吐 胃痛 反酸 烧心 便秘 便血 腹胀"),
    ("CAR", "心血管内科", "胸痛 胸闷 心悸 心慌 气短 高血压 心律失常 水肿"),
    ("RES", "呼吸内科", "咳嗽 咳痰 发热 呼吸困难 气短 咯血 哮喘 胸痛"),
    ("NEU", "神经内科", "头痛 头晕 眩晕 肢体无力 麻木 抽搐 意识障碍 面瘫"),
    ("END", "内分泌科", "多饮 多尿 体重下降 甲状腺肿大 糖尿病 肥胖 乏力"),
    ("URO", "泌尿外科", "尿频 尿急 尿痛 血尿 腰痛 肾结石 排尿困难"),
    ("GYN", "妇科", "下腹痛 月经不调 痛经 白带异常 阴道出血 盆腔痛"),
    ("OB", "产科", "停经 早孕 恶心 呕吐 孕期腹痛 胎动异常 阴道出血"),
    ("ORTH", "骨科", "骨折 关节痛 腰背痛 颈椎痛 扭伤 关节炎 肢体畸形"),
    ("DERM", "皮肤科", "皮疹 瘙痒 红肿 脱发 皮肤溃疡 湿疹 荨麻疹"),
    ("ENT", "耳鼻喉科", "咽痛 鼻塞 流涕 耳鸣 听力下降 声音嘶哑 眩晕"),
    ("OPH", "眼科", "眼红 眼痛 视力下降 视物模糊 流泪 复视 眼干"),
    ("PSY", "精神心理科", "失眠 焦虑 抑郁 情绪低落 恐慌 记忆力下降"),
    ("EMER", "急诊科", "剧烈胸痛 呼吸困难 大出血 昏迷 高热 严重外伤 休克"),
]


async def main() -> None:
    embedder = build_embedder(settings)
    store = MilvusStore(settings.milvus_uri)

    store.drop(KB_DEPT.name)
    store.ensure_collection(KB_DEPT)
    store.create_index(KB_DEPT)

    texts = [f"{name}：{symptoms}" for _, name, symptoms in DEPTS]
    embeddings = await embedder.embed(texts)

    rows = []
    for (code, name, symptoms), emb in zip(DEPTS, embeddings, strict=False):
        rows.append(
            {
                "id": f"dept_{code}",
                "dense": emb.dense,
                "sparse": emb.sparse,
                "text": f"{name}：{symptoms}",
                "dept_code": code,
                "dept_name": name,
                "tenant_id": DEFAULT_TENANT_ID,
            }
        )
    store.upsert(KB_DEPT, rows)
    print(f"已写入 kb_dept 集合 {len(rows)} 条科室专长数据")

    await embedder.aclose()
    store.close()


if __name__ == "__main__":
    asyncio.run(main())
