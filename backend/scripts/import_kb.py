"""从 Excel 源数据导入知识库（关系库 + 向量库）+ 生成规则 JSON。

读取 kb/医学知识库源数据.xlsx，分流处理：
- 知识库类（科室字典/疾病特征/临床指南/ICD-10/症状本体/禁忌症）→ mg_kb_entry
- 科室专长额外向量化 → Milvus kb_dept（供候选科室召回）
- 医生信息 → mg_user（幂等）
- 规则类（红旗症状/分诊规则/追问模板）→ 生成 kb/rules.json（供代码层硬编码护栏读取）

用法：在 backend 目录执行
    python scripts/import_kb.py

幂等：entry_code 唯一，重复导入更新不重复插入。
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from openpyxl import load_workbook

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select  # noqa: E402

from app.common.database import AsyncSessionFactory  # noqa: E402
from app.common.embedder import build_embedder  # noqa: E402
from app.config import settings  # noqa: E402
from app.models import KbEntry, User, gen_id  # noqa: E402
from app.retrieval import KB_DEPT, MilvusStore  # noqa: E402

DEFAULT_TENANT_ID = "00000000000000000000000000000001"
EXCEL_PATH = PROJECT_ROOT / "kb" / "医学知识库源数据.xlsx"


def _rows(sheet_name: str) -> list[list]:
    ws = load_workbook(EXCEL_PATH)[sheet_name]
    data = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row and row[0] is not None:
            data.append([str(c) if c is not None else "" for c in row])
    return data


def _kv(keys: list[str], row: list) -> dict:
    return {k: (row[i] if i < len(row) else "") for i, k in enumerate(keys)}


async def import_entries() -> None:
    """把知识库类数据写入 mg_kb_entry（幂等 upsert）。"""
    # (sheet, keys, kb_type, entry_code_prefix, content 字段)
    plans = [
        ("科室字典", ["dept_code", "dept_name", "aliases", "expertise", "sub_specialty", "related_diseases"],
         "DEPT_EXPERTISE", "DEPT", ["dept_name", "expertise", "related_diseases"]),
        ("疾病特征库", ["dept_code", "disease_name", "symptoms", "differential", "risk_factors"],
         "SYMPTOM_DISEASE", "DISEASE", ["disease_name", "symptoms", "differential"]),
        ("临床指南", ["dept_code", "title", "content", "evidence_level", "year", "source"],
         "GUIDELINE", "GUIDE", ["title", "content"]),
        ("ICD-10映射", ["disease_name", "icd10_code", "chapter", "inclusion", "exclusion"],
         "ICD-10", "ICD10", ["disease_name", "icd10_code", "inclusion"]),
        ("症状本体库", ["standard_name", "synonyms", "body_part", "duration"],
         "SYMPTOM_DISEASE", "SYMPTOM", ["standard_name", "synonyms", "body_part"]),
        ("禁忌症与用药风险", ["drug_name", "allergy_item", "severity", "suggestion", "population", "note"],
         "DRUG_SAFETY", "DRUG", ["drug_name", "allergy_item", "suggestion"]),
    ]

    total = 0
    async with AsyncSessionFactory() as db:
        for sheet, keys, kb_type, prefix, content_fields in plans:
            rows = _rows(sheet)
            for idx, row in enumerate(rows, start=1):
                d = _kv(keys, row)
                entry_code = f"{prefix}-{idx:03d}"
                if kb_type == "DEPT_EXPERTISE":
                    entry_code = f"{prefix}-{d['dept_code']}"
                elif kb_type == "ICD-10":
                    entry_code = f"{prefix}-{d['icd10_code'].replace('.', '')}"
                content = " ".join(d.get(f, "") for f in content_fields)

                existing = await db.scalar(
                    select(KbEntry).where(
                        KbEntry.tenant_id == DEFAULT_TENANT_ID, KbEntry.entry_code == entry_code
                    )
                )
                if existing is not None:
                    existing.content = content
                    existing.content_json = d
                    existing.dept_code = d.get("dept_code") or None
                else:
                    db.add(
                        KbEntry(
                            id=gen_id(),
                            tenant_id=DEFAULT_TENANT_ID,
                            kb_type=kb_type,
                            entry_code=entry_code,
                            title=d.get("title") or d.get("dept_name") or d.get("disease_name") or d.get("standard_name") or d.get("drug_name"),
                            content=content,
                            content_json=d,
                            dept_code=d.get("dept_code") or None,
                            status="1",  # 已发布
                            is_active="1",  # 参与检索
                            create_by="system",
                        )
                    )
                total += 1
        await db.commit()
    print(f"mg_kb_entry 导入 {total} 条（幂等）")


async def import_dept_vectors(embedder, store: MilvusStore) -> None:
    """科室专长向量化 → Milvus kb_dept（合并覆盖，不 drop）。

    聚焦科室用富文本覆盖同 id 的简版，其余科室简版保留（避免分诊召回退化）。
    """
    rows = _rows("科室字典")
    if not rows:
        return
    store.ensure_collection(KB_DEPT)
    store.create_index(KB_DEPT)

    texts = []
    dept_rows = []
    for row in rows:
        d = _kv(["dept_code", "dept_name", "aliases", "expertise", "sub_specialty", "related_diseases"], row)
        texts.append(f"{d['dept_name']}：{d['expertise']} {d['related_diseases']}")
        dept_rows.append(d)

    embeddings = await embedder.embed(texts)
    vec_rows = []
    for d, emb in zip(dept_rows, embeddings):
        vec_rows.append(
            {
                "id": f"dept_{d['dept_code']}",
                "dense": emb.dense,
                "sparse": emb.sparse,
                "text": f"{d['dept_name']}：{d['expertise']} {d['related_diseases']}",
                "dept_code": d["dept_code"],
                "dept_name": d["dept_name"],
                "tenant_id": DEFAULT_TENANT_ID,
            }
        )
    store.upsert(KB_DEPT, vec_rows)
    print(f"Milvus kb_dept 导入 {len(vec_rows)} 条科室专长")


async def import_doctors() -> None:
    """医生信息 → mg_user（幂等，跳过已存在账号）。"""
    rows = _rows("医生信息")
    count = 0
    async with AsyncSessionFactory() as db:
        for row in rows:
            d = _kv(["doctor_id", "name", "title", "dept_code", "dept_name"], row)
            account = d["doctor_id"]
            existing = await db.scalar(
                select(User).where(User.tenant_id == DEFAULT_TENANT_ID, User.account == account)
            )
            if existing is not None:
                continue
            from app.common.security import hash_password
            db.add(
                User(
                    id=gen_id(),
                    tenant_id=DEFAULT_TENANT_ID,
                    account=account,
                    real_name=d["name"],
                    role="DOCTOR",
                    title=d["title"],
                    dept_code=d["dept_code"],
                    credential_hash=hash_password("admin123"),
                    status="1",
                    create_by="system",
                )
            )
            count += 1
        await db.commit()
    print(f"mg_user 新增 {count} 个医生（幂等）")


def gen_rules_json() -> None:
    """规则类数据 → kb/rules.json（红旗/分诊/追问，供代码层硬编码护栏读取）。"""
    red_flags = [
        _kv(["rule_id", "symptom", "keywords", "layer", "action", "message"], row)
        for row in _rows("红旗症状库")
    ]
    for r in red_flags:
        r["keywords"] = [k for k in r["keywords"].split("|") if k]
        r["layer"] = int(r["layer"])

    triage_rules = [
        _kv(["symptom", "dept_code", "dept_name", "age_filter", "gender_filter", "priority", "note"], row)
        for row in _rows("分诊规则")
    ]
    for r in triage_rules:
        r["symptoms"] = [s for s in r.pop("symptom").split("|") if s]
        r["priority"] = int(r["priority"])

    inquiry = [
        _kv(["complaint_type", "target_slot", "question", "order"], row)
        for row in _rows("追问模板")
    ]

    out = PROJECT_ROOT / "kb" / "rules.json"
    out.write_text(
        json.dumps(
            {"red_flags": red_flags, "triage_rules": triage_rules, "inquiry_templates": inquiry},
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    print(f"规则 JSON 生成 {out}（红旗 {len(red_flags)} / 分诊 {len(triage_rules)} / 追问 {len(inquiry)}）")


async def main() -> None:
    if not EXCEL_PATH.exists():
        print(f"未找到 {EXCEL_PATH}，请先运行 gen_kb_excel.py")
        return
    await import_entries()
    await import_doctors()

    embedder = build_embedder(settings)
    store = MilvusStore(settings.milvus_uri)
    try:
        await import_dept_vectors(embedder, store)
    finally:
        await embedder.aclose()
        store.close()

    gen_rules_json()
    print("全部导入完成")


if __name__ == "__main__":
    asyncio.run(main())
