"""规则引擎：加载 kb/rules.json，提供分诊规则命中/红旗判断/追问模板。

规则来源于「医学知识库源数据 Excel」的规则类 sheet（结构化可解析），
在向量召回之外提供确定性信号，弥补纯语义召回对「年龄/科室层级/症状主次」的盲区。
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger("mg.rules")

_RULES_PATH = Path(__file__).resolve().parents[3] / "kb" / "rules.json"


@lru_cache(maxsize=1)
def _load_rules() -> dict[str, Any]:
    if not _RULES_PATH.exists():
        logger.warning("规则文件不存在：%s", _RULES_PATH)
        return {"red_flags": [], "triage_rules": [], "inquiry_templates": []}
    try:
        data = json.loads(_RULES_PATH.read_text(encoding="utf-8"))
        logger.info(
            "规则加载完成：红旗 %d / 分诊 %d / 追问 %d",
            len(data.get("red_flags", [])),
            len(data.get("triage_rules", [])),
            len(data.get("inquiry_templates", [])),
        )
        return data
    except Exception as exc:  # 规则文件损坏不应阻断服务
        logger.error("规则文件解析失败：%s", exc)
        return {"red_flags": [], "triage_rules": [], "inquiry_templates": []}


def reload_rules() -> None:
    _load_rules.cache_clear()


@lru_cache(maxsize=1)
def _synonym_index() -> dict[str, str]:
    """同义词 → 标准名（反向索引，长词优先替换）。"""
    syn = _load_rules().get("symptom_synonyms", {})
    idx: dict[str, str] = {}
    for std, words in syn.items():
        for w in words or []:
            if w and w != std:
                idx[w] = std
    return idx


def normalize_complaint(text: str) -> str:
    """把口语同义词归一化为标准症状名（如「肚子疼」→「腹痛」，「拉肚子」→「腹泻」）。

    规则表用的是标准症状名，患者说的是口语，必须先归一化才能命中。
    按同义词长度降序替换，避免短词误伤长词。
    """
    idx = _synonym_index()
    for word in sorted(idx, key=len, reverse=True):
        if word in text:
            text = text.replace(word, idx[word])
    return text


def match_dept_bonus(
    complaint: str,
    *,
    gender: str | None = None,
    age: int | None = None,
) -> dict[str, float]:
    """分诊规则命中 → {dept_code: 命中得分}。

    每个命中的症状给基础分，乘以规则优先级权重（priority/10）。
    性别/年龄过滤：规则限定人群与本次患者不符时跳过。
    """
    rules = _load_rules().get("triage_rules", [])
    text = normalize_complaint(complaint)
    bonus: dict[str, float] = {}
    for rule in rules:
        dept = rule.get("dept_code")
        if not dept:
            continue
        # 性别过滤（规则限定「女」时，男性患者跳过）
        gf = (rule.get("gender_filter") or "").strip()
        if gf and gender and gf != gender:
            continue
        # 年龄过滤
        af = (rule.get("age_filter") or "").strip()
        if af == "child" and age is not None and age >= 18:
            continue
        if af == "elderly" and age is not None and age < 65:
            continue
        symptoms = rule.get("symptoms") or []
        hits = [s for s in symptoms if s and s in text]
        if not hits:
            continue
        priority = float(rule.get("priority") or 8)
        # 命中症状数 × 优先级权重；最多计 3 个命中，避免长主诉过度加权
        score = min(len(hits), 3) * (priority / 10.0)
        if score > bonus.get(dept, 0):
            bonus[dept] = score
    return bonus


def match_red_flags(text: str) -> list[dict[str, Any]]:
    """红旗症状命中（关键词匹配，先做同义词归一化）。返回命中的规则列表。"""
    flags = _load_rules().get("red_flags", [])
    text = normalize_complaint(text)
    hit = []
    for f in flags:
        keywords = f.get("keywords") or []
        if any(k and k in text for k in keywords):
            hit.append(f)
    return hit


def inquiry_templates(complaint_type: str) -> list[dict[str, Any]]:
    """取某主诉类型下的追问模板（按 order 排序）。"""
    items = [
        t for t in _load_rules().get("inquiry_templates", [])
        if t.get("complaint_type") == complaint_type
    ]
    return sorted(items, key=lambda x: int(x.get("order") or 99))


def infer_complaint_type(complaint: str) -> str | None:
    """从主诉文本推断追问模板的主诉类型（先归一化，最长匹配）。"""
    text = normalize_complaint(complaint)
    types = {t.get("complaint_type") for t in _load_rules().get("inquiry_templates", [])}
    matched = [t for t in types if t and t in text]
    return max(matched, key=len) if matched else None
