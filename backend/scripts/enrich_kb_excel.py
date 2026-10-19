"""知识库 Excel 清洗与丰富流水线。

只做「结构化、去重、交叉索引」，不新增任何诊疗结论：
- 清洗全部 sheet 的空白与多值分隔符；
- 生成疾病知识卡、症状别名索引、科室导诊卡；
- 生成知识条目清单（供 import_kb 直接入库）；
- 生成数据质量报告，记录重复/冲突/缺失，不静默改医学内容。

用法（backend 目录）：
    python scripts/enrich_kb_excel.py
"""
from __future__ import annotations

import json
import re
import shutil
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
SRC = PROJECT_ROOT / "kb" / "医学知识库源数据.xlsx"
ARCHIVE_DIR = PROJECT_ROOT / "kb" / "archive"

_HEADER_FILL = PatternFill("solid", fgColor="17504E")
_HEADER_FONT = Font(color="FFFFFF", bold=True)


def clean(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    # 全角空格、连续空白归一
    text = re.sub(r"\s+", " ", text)
    return text


def multi(value: Any) -> list[str]:
    """按 | 拆分多值字段，去空、去重并保持原顺序。"""
    out: list[str] = []
    for part in clean(value).split("|"):
        item = part.strip()
        if item and item not in out:
            out.append(item)
    return out


def multi_text(value: Any) -> str:
    return "|".join(multi(value))


def load_sheet(wb, name: str) -> tuple[list[str], list[dict[str, str]]]:
    ws = wb[name]
    raw = list(ws.iter_rows(values_only=True))
    header = [clean(c) for c in raw[0]]
    rows: list[dict[str, str]] = []
    for row in raw[1:]:
        if not any(clean(c) for c in row):
            continue
        rows.append({header[i]: clean(row[i]) if i < len(row) else "" for i in range(len(header))})
    return header, rows


def write_sheet(wb, name: str, header: list[str], rows: list[list[Any]]) -> None:
    if name in wb.sheetnames:
        del wb[name]
    ws = wb.create_sheet(name)
    ws.append(header)
    for cell in ws[1]:
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.alignment = Alignment(vertical="center")
    for row in rows:
        ws.append(row)
    ws.freeze_panes = "A2"
    for idx, title in enumerate(header, start=1):
        width = max(12, min(48, max(len(str(title)) * 2, *(len(str(r[idx - 1])) for r in rows[:200] if idx - 1 < len(r)))) if rows else 16)
        ws.column_dimensions[get_column_letter(idx)].width = width


def normalize_sheet(ws) -> None:
    for row in ws.iter_rows():
        for cell in row:
            if isinstance(cell.value, str):
                value = clean(cell.value)
                if "|" in value:
                    value = multi_text(value)
                cell.value = value


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"未找到源工作簿：{SRC}")
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    backup = ARCHIVE_DIR / f"医学知识库源数据_原始_{datetime.now(UTC):%Y%m%d_%H%M%S}.xlsx"
    shutil.copy2(SRC, backup)

    wb = load_workbook(SRC)
    # 1) 全 sheet 清洗
    for ws in wb.worksheets:
        if ws.title != "说明":
            normalize_sheet(ws)

    sheet_names = [ws.title for ws in wb.worksheets]
    _, depts = load_sheet(wb, "科室字典")
    _, diseases = load_sheet(wb, "疾病特征库")
    _, guidelines = load_sheet(wb, "临床指南")
    _, recs = load_sheet(wb, "指南推荐意见")
    _, icds = load_sheet(wb, "ICD-10映射")
    _, symptoms = load_sheet(wb, "症状本体库")
    _, drugs = load_sheet(wb, "禁忌症与用药风险")
    _, red_flags = load_sheet(wb, "红旗症状库")
    _, triage_rules = load_sheet(wb, "分诊规则")
    _, inquiry = load_sheet(wb, "追问模板")

    dept_by_code = {d["科室编码"]: d for d in depts}
    icd_by_disease: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in icds:
        icd_by_disease[row["疾病名称"]].append(row)
    recs_by_disease: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in recs:
        recs_by_disease[row["疾病名称"]].append(row)
    guidelines_by_dept: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in guidelines:
        guidelines_by_dept[row["科室编码"]].append(row)
    diseases_by_dept: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in diseases:
        diseases_by_dept[row["科室编码"]].append(row)

    # 2) 疾病知识卡：同名疾病跨科室聚合
    disease_names = sorted({d["疾病名称"] for d in diseases})
    cards: list[list[Any]] = []
    for name in disease_names:
        variants = [d for d in diseases if d["疾病名称"] == name]
        dept_codes = sorted({d["科室编码"] for d in variants})
        dept_names = [dept_by_code.get(c, {}).get("科室名称", c) for c in dept_codes]
        symptom_set = []
        differential = []
        risks = []
        for v in variants:
            for item in multi(v.get("症状", "")):
                if item not in symptom_set:
                    symptom_set.append(item)
            for item in multi(v.get("鉴别诊断要点", "")):
                if item not in differential:
                    differential.append(item)
            for item in multi(v.get("高危因素", "")):
                if item not in risks:
                    risks.append(item)
        icd_rows = icd_by_disease.get(name, [])
        icd_codes = []
        chapters = []
        for r in icd_rows:
            if r["ICD-10编码"] not in icd_codes:
                icd_codes.append(r["ICD-10编码"])
            if r["章节"] not in chapters:
                chapters.append(r["章节"])
        rec_rows = recs_by_disease.get(name, [])
        red_rows = [r for r in red_flags if name in r["症状"] or any(k in name for k in multi(r["关键词"]))]
        cards.append(
            [
                name,
                "|".join(dept_codes),
                "|".join(dept_names),
                "|".join(symptom_set),
                "|".join(differential),
                "|".join(risks),
                "|".join(icd_codes),
                "|".join(chapters),
                len(rec_rows),
                "；".join(r["推荐意见"] for r in rec_rows[:3]),
                "|".join(r["提示文案"] for r in red_rows[:2]),
                "|".join([name, *symptom_set, *differential[:3], *dept_names]),
                "疾病特征库 + ICD-10映射 + 指南推荐意见（派生）",
            ]
        )
    write_sheet(
        wb,
        "疾病知识卡",
        ["疾病名称", "科室编码", "科室名称", "症状", "鉴别诊断", "高危因素", "ICD编码", "ICD章节", "指南推荐数", "指南推荐摘要", "红旗提示", "关键词", "数据来源"],
        cards,
    )

    # 3) 症状别名索引
    aliases: list[list[Any]] = []
    for row in symptoms:
        aliases.append([row["标准症状名"], row["标准症状名"], row["身体部位"], row["持续时间"], "标准名"])
        for alias in multi(row["同义词"]):
            aliases.append([row["标准症状名"], alias, row["身体部位"], row["持续时间"], "同义词"])
    write_sheet(wb, "症状别名索引", ["标准症状名", "别名", "身体部位", "持续时间", "类型"], aliases)

    # 4) 科室导诊卡
    dept_cards: list[list[Any]] = []
    for dept in depts:
        code = dept["科室编码"]
        disease_list = [d["疾病名称"] for d in diseases_by_dept.get(code, [])]
        symptom_list: list[str] = []
        for d in diseases_by_dept.get(code, []):
            for s in multi(d.get("症状", "")):
                if s not in symptom_list:
                    symptom_list.append(s)
        dept_cards.append(
            [
                code,
                dept["科室名称"],
                dept["别名"],
                dept["专长"],
                dept["亚专科"],
                "|".join(disease_list),
                "|".join(symptom_list),
                len(guidelines_by_dept.get(code, [])),
                len(disease_list),
                "科室字典 + 疾病特征库 + 临床指南（派生）",
            ]
        )
    write_sheet(
        wb,
        "科室导诊卡",
        ["科室编码", "科室名称", "别名", "专长", "亚专科", "疾病列表", "症状列表", "指南数", "疾病数", "数据来源"],
        dept_cards,
    )

    # 5) 知识条目清单：直接供 import_kb 使用
    catalog: list[list[Any]] = []
    for row in depts:
        code = row["科室编码"]
        content = f"{row['科室名称']}（{row['别名']}）：{row['专长']}；亚专科：{row['亚专科']}；相关疾病：{row['对应疾病']}"
        catalog.append([
            f"DEPT-{code}", "DEPT_EXPERTISE", "kb_dept", row["科室名称"], content, code,
            "", "", "", "科室字典",
            json.dumps({"aliases": multi(row["别名"]), "sub_specialty": multi(row["亚专科"]), "related_diseases": multi(row["对应疾病"])}, ensure_ascii=False),
        ])
    for idx, row in enumerate(diseases, start=1):
        dept_code = row["科室编码"]
        icd_codes = [r["ICD-10编码"] for r in icd_by_disease.get(row["疾病名称"], [])]
        content = f"{row['疾病名称']}：症状 {row['症状']}；鉴别 {row['鉴别诊断要点']}；高危因素 {row['高危因素']}"
        catalog.append([
            f"DISEASE-{dept_code}-{idx:03d}", "SYMPTOM_DISEASE", "kb_symptom", row["疾病名称"], content, dept_code,
            "|".join(icd_codes), "", "", "疾病特征库",
            json.dumps({"symptoms": multi(row["症状"]), "differential": multi(row["鉴别诊断要点"]), "risk_factors": multi(row["高危因素"])}, ensure_ascii=False),
        ])
    for idx, row in enumerate(guidelines, start=1):
        content = f"{row['标题']}：{row['文本片段']}"
        catalog.append([
            f"GUIDE-{idx:03d}", "GUIDELINE", "kb_guideline", row["标题"], content, row["科室编码"],
            "", "", "", row["来源"],
            json.dumps({"evidence_level": row["证据等级"], "year": row["年份"], "source": row["来源"]}, ensure_ascii=False),
        ])
    for idx, row in enumerate(recs, start=1):
        content = f"{row['疾病名称']}：{row['推荐意见']}（适用人群：{row['适用人群']}；场景：{row['场景']}；强度：{row['推荐强度']}）"
        icd_codes = [r["ICD-10编码"] for r in icd_by_disease.get(row["疾病名称"], [])]
        catalog.append([
            f"GUIDEREC-{idx:03d}", "GUIDELINE_REC", "kb_guideline", f"{row['疾病名称']}·推荐", content, row["科室编码"],
            "|".join(icd_codes), "", "", row["指南来源"],
            json.dumps({"disease_name": row["疾病名称"], "evidence_level": row["证据等级"], "recommendation_strength": row["推荐强度"], "population": row["适用人群"], "scene": row["场景"], "guideline_source": row["指南来源"], "year": row["年份"]}, ensure_ascii=False),
        ])
    for idx, row in enumerate(icds, start=1):
        content = f"{row['疾病名称']}（{row['ICD-10编码']}）：章节 {row['章节']}；包含 {row['包含']}；排除 {row['排除']}"
        catalog.append([
            f"ICD10-{idx:03d}", "ICD-10", "kb_icd10", row["疾病名称"], content, "",
            row["ICD-10编码"], "", "", "ICD-10映射",
            json.dumps({"chapter": row["章节"], "inclusion": row["包含"], "exclusion": row["排除"]}, ensure_ascii=False),
        ])
    for idx, row in enumerate(symptoms, start=1):
        content = f"{row['标准症状名']}（{row['同义词']}）：部位 {row['身体部位']}；持续时间 {row['持续时间']}"
        catalog.append([
            f"SYMPTOM-{idx:03d}", "SYMPTOM_DISEASE", "kb_symptom", row["标准症状名"], content, "",
            "", "", "", "症状本体库",
            json.dumps({"synonyms": multi(row["同义词"]), "body_part": row["身体部位"], "duration": row["持续时间"]}, ensure_ascii=False),
        ])
    for idx, row in enumerate(drugs, start=1):
        content = f"{row['药物']} / {row['过敏/禁忌项']}：严重度 {row['严重度']}；建议 {row['建议']}；适用人群 {row['适用人群']}；备注 {row['备注']}"
        catalog.append([
            f"DRUG-{idx:03d}", "DRUG_SAFETY", "kb_drug", f"{row['药物']}·{row['过敏/禁忌项']}", content, "",
            "", "", "", "禁忌症与用药风险",
            json.dumps({"drug_name": row["药物"], "allergy_item": row["过敏/禁忌项"], "severity": row["严重度"], "suggestion": row["建议"], "population": row["适用人群"], "note": row["备注"]}, ensure_ascii=False),
        ])
    write_sheet(
        wb,
        "知识条目清单",
        ["entry_code", "kb_type", "vector_collection", "title", "content", "dept_code", "icd10_codes", "age_group", "gender", "source", "content_json"],
        catalog,
    )

    # 6) 数据质量报告
    disease_counts = Counter(d["疾病名称"] for d in diseases)
    icd_counts = Counter(r["疾病名称"] for r in icds)
    guide_counts = Counter(r["标题"] for r in guidelines)
    chapter_conflicts = []
    for name, rows in icd_by_disease.items():
        chapters = {r["章节"] for r in rows}
        if len(chapters) > 1:
            chapter_conflicts.append(f"{name}: {' / '.join(sorted(chapters))}")
    quality = [
        ["sheet 数", len(sheet_names)],
        ["科室数", len(depts)],
        ["一级科室数", sum(1 for d in depts if "-" not in d["科室编码"])],
        ["疾病条目数", len(diseases)],
        ["疾病唯一名称数", len(disease_counts)],
        ["跨科室重复疾病数", sum(1 for v in disease_counts.values() if v > 1)],
        ["ICD 条目数", len(icds)],
        ["ICD 重复疾病名数", sum(1 for v in icd_counts.values() if v > 1)],
        ["指南条目数", len(guidelines)],
        ["指南重复标题数", sum(1 for v in guide_counts.values() if v > 1)],
        ["指南推荐条目数", len(recs)],
        ["症状条目数", len(symptoms)],
        ["用药风险条目数", len(drugs)],
        ["红旗规则数", len(red_flags)],
        ["分诊规则数", len(triage_rules)],
        ["追问模板数", len(inquiry)],
        ["知识条目清单总数", len(catalog)],
        ["ICD 章节冲突数", len(chapter_conflicts)],
        ["ICD 章节冲突示例", "；".join(chapter_conflicts[:3])],
        ["说明", "重复疾病多为跨科室视角；清洗只做空白/多值归一，不修改医学结论"],
        ["生成时间", datetime.now(UTC).isoformat()],
    ]
    write_sheet(wb, "数据质量报告", ["指标", "值"], quality)

    wb.save(SRC)
    print(f"原始备份：{backup}")
    print(f"已写入：{SRC}")
    print(f"知识条目清单：{len(catalog)} 条；疾病知识卡：{len(cards)}；症状别名：{len(aliases)}；科室导诊卡：{len(dept_cards)}")
    print(f"ICD 章节冲突：{len(chapter_conflicts)}（保留在数据质量报告，未静默改写）")


if __name__ == "__main__":
    main()
