"""知识图谱服务：症状 → 疾病 → 科室的多跳推理与路径解释。

图谱数据由 scripts/build_kg.py 从知识库源数据构建（节点统一带 :Mg 标签，
与同一 Neo4j 实例里的其他图谱隔离）。

对外能力：
- infer_depts(complaint)：主诉 → 候选科室 + 推理路径（供分诊与医生端展示）
- explain(complaint, dept_code)：某科室的推理链（为什么推荐这个科室）
"""
from __future__ import annotations

import logging

from neo4j import GraphDatabase

from app.config import settings
from app.services import rules_engine

logger = logging.getLogger(__name__)

# 本项目图谱节点统一标签（build_kg.py 写入时打的）
_MG = ":Mg"


class KnowledgeGraph:
    def __init__(self, uri: str | None = None, user: str | None = None, password: str | None = None):
        self._uri = uri or getattr(settings, "neo4j_uri", "") or "bolt://127.0.0.1:7687"
        self._user = user or getattr(settings, "neo4j_user", "") or "neo4j"
        self._pwd = password or getattr(settings, "neo4j_password", "") or "12345678"
        self._driver = GraphDatabase.driver(self._uri, auth=(self._user, self._pwd))

    def close(self) -> None:
        self._driver.close()

    def available(self) -> bool:
        try:
            with self._driver.session(database="neo4j") as s:
                s.run("RETURN 1").consume()
            return True
        except Exception as exc:
            logger.warning("Neo4j 不可用：%s", exc)
            return False

    # ---------------- 症状匹配 ----------------

    def _all_symptom_names(self) -> list[str]:
        with self._driver.session(database="neo4j") as s:
            return [r["name"] for r in s.run(f"MATCH (n:Symptom{_MG}) RETURN n.name AS name")]

    def match_symptoms(self, text: str) -> list[str]:
        """从主诉中匹配图谱里的症状（标准名 + 同义词，先做同义词归一化）。"""
        norm = rules_engine.normalize_complaint(text)
        names = self._all_symptom_names()
        hit = {n for n in names if n and n in norm}
        # 长词优先（「下腹痛」优先于「腹痛」），最多取 10 个
        return sorted(hit, key=len, reverse=True)[:10]

    # ---------------- 多跳推理 ----------------

    def infer_depts(self, complaint: str, limit: int = 5) -> list[dict]:
        """主诉 → 候选科室（症状→疾病→科室 两跳），带推理路径。

        返回：[{dept_code, dept_name, disease_hits, score, paths: ["腹痛→胃炎→消化内科", ...]}]
        """
        symptoms = self.match_symptoms(complaint)
        if not symptoms:
            return []
        cql = """
        MATCH (s:Symptom:Mg)-[:INDICATES]->(d:Disease:Mg)-[:BELONGS_TO]->(dept:Department:Mg)
        WHERE s.name IN $symptoms
        RETURN dept.code AS dept_code, dept.name AS dept_name,
               count(DISTINCT d) AS disease_hits,
               collect(DISTINCT s.name + '→' + d.name + '→' + dept.name)[..3] AS paths
        ORDER BY disease_hits DESC
        LIMIT $limit
        """
        with self._driver.session(database="neo4j") as s:
            rows = s.run(cql, symptoms=symptoms, limit=limit).data()

        max_hits = max((r["disease_hits"] for r in rows), default=1) or 1
        for r in rows:
            r["score"] = round(r["disease_hits"] / max_hits, 4)
            r["symptom_hits"] = len(symptoms)
        return rows

    def explain(self, complaint: str, dept_code: str) -> list[str]:
        """为什么推荐该科室：从命中的症状出发，列出到该科室的推理路径。"""
        symptoms = self.match_symptoms(complaint)
        if not symptoms:
            return []
        cql = """
        MATCH (s:Symptom:Mg)-[:INDICATES]->(d:Disease:Mg)-[:BELONGS_TO]->(dept:Department:Mg {code: $dept})
        WHERE s.name IN $symptoms
        RETURN DISTINCT s.name + '→' + d.name + '→' + dept.name AS path
        LIMIT 8
        """
        with self._driver.session(database="neo4j") as s:
            return [r["path"] for r in s.run(cql, symptoms=symptoms, dept=dept_code).data()]

    def stats(self) -> dict:
        with self._driver.session(database="neo4j") as s:
            nodes = s.run(f"MATCH (n{_MG}) RETURN labels(n) AS labels, count(*) AS c").data()
            rels = s.run(
                f"MATCH (:{_MG[1:]} )-[r]->() RETURN type(r) AS type, count(*) AS c"
            ).data()
        return {"nodes": nodes, "rels": rels}


_kg: KnowledgeGraph | None = None


def get_kg() -> KnowledgeGraph:
    """进程内单例。"""
    global _kg
    if _kg is None:
        _kg = KnowledgeGraph()
    return _kg
