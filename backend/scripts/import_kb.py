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
from app.models import Dept, KbEntry, User, gen_id  # noqa: E402
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
    """从「知识条目清单」全量导入 mg_kb_entry。

    清单由 scripts/enrich_kb_excel.py 生成，已把科室、疾病、指南、推荐、ICD、
    症状、用药风险统一成可入库的条目，并带上 content_json / icd10 / source。
    """
    catalog = _rows("知识条目清单")
    if not catalog:
        raise SystemExit(
            "知识条目清单为空：请先运行 python scripts/enrich_kb_excel.py"
        )

    keys = [
        "entry_code", "kb_type", "vector_collection", "title", "content",
        "dept_code", "icd10_codes", "age_group", "gender", "source", "content_json",
    ]
    prefixes = ("DEPT", "DISEASE", "GUIDE", "GUIDEREC", "ICD10", "SYMPTOM", "DRUG")

    total = 0
    async with AsyncSessionFactory() as db:
        old = (
            await db.scalars(
                select(KbEntry).where(KbEntry.tenant_id == DEFAULT_TENANT_ID)
            )
        ).all()
        removed = 0
        for entry in old:
            code = entry.entry_code or ""
            if any(code.startswith(prefix + "-") for prefix in prefixes):
                await db.delete(entry)
                removed += 1
        if removed:
            await db.flush()
            print(f"清理旧条目 {removed} 条")

        for row in catalog:
            data = _kv(keys, row)
            entry_code = data["entry_code"]
            icd_codes = [c for c in data["icd10_codes"].split("|") if c]
            try:
                content_json = json.loads(data["content_json"]) if data["content_json"] else {}
            except json.JSONDecodeError:
                content_json = {}
            title = data["title"] or data["entry_code"]
            entry = await db.scalar(
                select(KbEntry).where(
                    KbEntry.tenant_id == DEFAULT_TENANT_ID,
                    KbEntry.entry_code == entry_code,
                )
            )
            if entry is not None:
                entry.kb_type = data["kb_type"]
                entry.title = title
                entry.content = data["content"]
                entry.content_json = content_json
                entry.dept_code = data["dept_code"] or None
                entry.icd10_codes = icd_codes or None
                entry.age_group = data["age_group"] or "all"
                entry.gender = data["gender"] or "0"
                entry.source = data["source"] or None
                entry.entry_version = "v2"
                entry.status = "1"
                entry.is_active = "1"
            else:
                db.add(
                    KbEntry(
                        id=gen_id(),
                        tenant_id=DEFAULT_TENANT_ID,
                        kb_type=data["kb_type"],
                        entry_code=entry_code,
                        title=title,
                        content=data["content"],
                        content_json=content_json,
                        dept_code=data["dept_code"] or None,
                        icd10_codes=icd_codes or None,
                        age_group=data["age_group"] or "all",
                        gender=data["gender"] or "0",
                        source=data["source"] or None,
                        entry_version="v2",
                        status="1",
                        is_active="1",
                        create_by="system",
                    )
                )
            total += 1
        await db.commit()
    print(f"mg_kb_entry 导入 {total} 条（来自知识条目清单）")


async def import_dept_vectors(embedder, store: MilvusStore) -> None:
    """科室专长向量化 → Milvus kb_dept。

    只导入**一级科室**（dept_code 不含连字符）——分诊推荐应到一级科室，
    亚专科是院内细分，不参与候选科室召回，避免把患者分到亚专科。
    合并覆盖：同 id upsert，不清空其他科室。
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
        if "-" in d["dept_code"]:  # 跳过亚专科
            continue
        texts.append(f"{d['dept_name']}：{d['expertise']} {d['related_diseases']}")
        dept_rows.append(d)

    embeddings = await embedder.embed(texts)
    vec_rows = []
    for d, emb in zip(dept_rows, embeddings, strict=False):
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


async def import_departments() -> None:
    """科室字典 → mg_dept（幂等：按 dept_code upsert）。"""
    rows = _rows("科室字典")
    added = 0
    async with AsyncSessionFactory() as db:
        for idx, row in enumerate(rows, start=1):
            d = _kv(["dept_code", "dept_name", "aliases", "expertise", "sub_specialty", "related_diseases"], row)
            existing = await db.scalar(
                select(Dept).where(Dept.tenant_id == DEFAULT_TENANT_ID, Dept.dept_code == d["dept_code"])
            )
            if existing is not None:
                existing.dept_name = d["dept_name"]
                existing.sub_specialty = [s for s in d["sub_specialty"].split("|") if s] or None
                existing.common_complaints = [s for s in d["related_diseases"].split("|") if s] or None
            else:
                db.add(
                    Dept(
                        id=gen_id(),
                        tenant_id=DEFAULT_TENANT_ID,
                        dept_code=d["dept_code"],
                        dept_name=d["dept_name"],
                        sub_specialty=[s for s in d["sub_specialty"].split("|") if s] or None,
                        common_complaints=[s for s in d["related_diseases"].split("|") if s] or None,
                        sort_no=idx,
                        status="1",
                        create_by="system",
                    )
                )
                added += 1
        await db.commit()
    print(f"mg_dept 新增 {added} 个科室（幂等）")


async def import_doctors() -> None:
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
    # 症状同义词映射：标准名 → [同义词]，供规则匹配时把口语词归一化
    synonyms = {}
    for row in _rows("症状本体库"):
        d = _kv(["standard_name", "synonyms", "body_part", "duration"], row)
        if d["standard_name"]:
            synonyms[d["standard_name"]] = [s for s in d["synonyms"].split("|") if s]

    out.write_text(
        json.dumps(
            {
                "red_flags": red_flags,
                "triage_rules": triage_rules,
                "inquiry_templates": inquiry,
                "symptom_synonyms": synonyms,
            },
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    print(f"规则 JSON 生成 {out}（红旗 {len(red_flags)} / 分诊 {len(triage_rules)} / 追问 {len(inquiry)} / 同义词 {len(synonyms)}）")


async def main() -> None:
    if not EXCEL_PATH.exists():
        print(f"未找到 {EXCEL_PATH}，请先运行 gen_kb_excel.py")
        return
    await import_entries()
    await import_departments()
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
