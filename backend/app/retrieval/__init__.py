"""检索能力层（F56）：向量库集合定义、客户端、结果融合。"""
from app.retrieval.collections import (
    ALL_COLLECTIONS,
    KB_DEPT,
    KB_SYMPTOM,
    TRIAGE_COLLECTIONS,
    VectorCollection,
    get_collection,
)
from app.retrieval.vector_store import MilvusStore

__all__ = [
    "ALL_COLLECTIONS",
    "KB_DEPT",
    "KB_SYMPTOM",
    "TRIAGE_COLLECTIONS",
    "MilvusStore",
    "VectorCollection",
    "get_collection",
]
