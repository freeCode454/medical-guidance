"""向量库集合结构定义。

与《02 架构》§7.3 一致：七类集合，稠密向量度量余弦相似度，稀疏向量度量内积（IP）。
稀疏向量由向量化模型（BGE-M3）在应用层产出，**不**使用向量库内置 BM25 函数
（ADR-004：两路向量同源，融合打分口径一致）。

分区键：除「编码对照」外全部按机构（tenant_id）分区，实现物理隔离与检索加速。
"""
from __future__ import annotations

from dataclasses import dataclass

DIM = 1024  # BGE-M3 稠密向量维度


@dataclass(frozen=True)
class VectorCollection:
    """一个向量集合的结构定义。"""

    name: str
    has_sparse: bool = True  # 是否带稀疏向量
    # 标量字段：(字段名, 类型字符串)，类型见 MilvusStore._SCALAR_TYPES
    scalar_fields: tuple[tuple[str, str], ...] = ()
    partition_key: str | None = "tenant_id"  # None 表示不分区
    description: str = ""


# --- 七类集合 ----------------------------------------------------------

KB_DEPT = VectorCollection(
    name="kb_dept",
    has_sparse=True,
    scalar_fields=(
        ("text", "varchar4096"),
        ("dept_code", "varchar32"),
        ("dept_name", "varchar64"),
        ("tenant_id", "varchar32"),
    ),
    partition_key="tenant_id",
    description="科室专长：科室匹配（F56）",
)

KB_SYMPTOM = VectorCollection(
    name="kb_symptom",
    has_sparse=True,
    scalar_fields=(
        ("text", "varchar4096"),
        ("dept_code", "varchar32"),
        ("icd10_code", "varchar16"),
        ("age_group", "varchar16"),
        ("gender", "varchar1"),
        ("tenant_id", "varchar32"),
    ),
    partition_key="tenant_id",
    description="症状疾病：症状 → 疾病候选（F56）",
)

KB_GUIDELINE = VectorCollection(
    name="kb_guideline",
    has_sparse=True,
    scalar_fields=(
        ("text", "varchar4096"),
        ("icd10_code", "varchar16"),
        ("evidence_level", "varchar16"),
        ("pub_year", "varchar8"),
        ("tenant_id", "varchar32"),
    ),
    partition_key="tenant_id",
    description="诊疗指南：条文溯源与依据（F56）",
)

KB_ICD10 = VectorCollection(
    name="kb_icd10",
    has_sparse=False,
    scalar_fields=(("text", "varchar4096"), ("chapter", "varchar16"), ("alias", "varchar64")),
    partition_key=None,  # 编码是行业标准，全局共享，不归属机构
    description="编码对照：ICD-10 编码对齐（F56）",
)

KB_DRUG = VectorCollection(
    name="kb_drug",
    has_sparse=False,
    scalar_fields=(
        ("text", "varchar4096"),
        ("drug_name", "varchar64"),
        ("taboo_type", "varchar16"),
        ("tenant_id", "varchar32"),
    ),
    partition_key="tenant_id",
    description="用药禁忌：禁忌校验（F47）",
)

KB_CASE = VectorCollection(
    name="kb_case",
    has_sparse=False,
    scalar_fields=(
        ("text", "varchar4096"),
        ("dept_code", "varchar32"),
        ("diagnosis", "varchar64"),
        ("tenant_id", "varchar32"),
    ),
    partition_key="tenant_id",
    description="脱敏病例：检索增强（F56）",
)

KB_EMR = VectorCollection(
    name="kb_emr",
    has_sparse=True,
    scalar_fields=(
        ("text", "varchar4096"),
        ("patient_hash", "varchar64"),
        ("doc_type", "varchar32"),
        ("record_time", "varchar32"),
        ("tenant_id", "varchar32"),
    ),
    partition_key="tenant_id",
    description="病历文书：既往史召回（F56）",
)


ALL_COLLECTIONS: tuple[VectorCollection, ...] = (
    KB_DEPT,
    KB_SYMPTOM,
    KB_GUIDELINE,
    KB_ICD10,
    KB_DRUG,
    KB_CASE,
    KB_EMR,
)

# 分诊主链路核心集合（检索候选科室用）
TRIAGE_COLLECTIONS: tuple[VectorCollection, ...] = (KB_DEPT, KB_SYMPTOM)


def get_collection(name: str) -> VectorCollection:
    """按名取集合定义。"""
    for c in ALL_COLLECTIONS:
        if c.name == name:
            return c
    raise KeyError(f"未知向量集合：{name}")
