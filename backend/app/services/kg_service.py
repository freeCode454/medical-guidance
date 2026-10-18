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
        MATCH (s:Symptom:Mg)-[ind:INDICATES]->(d:Disease:Mg)-[:BELONGS_TO]->(dept:Department:Mg)
        WHERE s.name IN $symptoms
        RETURN dept.code AS dept_code, dept.name AS dept_name,
               max(coalesce(ind.weight, 0.6)) AS max_weight,
               count(DISTINCT d) AS disease_hits,
               collect(DISTINCT s.name + '→' + d.name + '→' + dept.name)[..3] AS paths
        ORDER BY max_weight DESC, disease_hits DESC
        LIMIT $limit
        """
        with self._driver.session(database="neo4j") as s:
            rows = s.run(cql, symptoms=symptoms, limit=limit).data()

        # 打分：以科室内的最高关系权重为主（体现「核心症状 vs 伴随症状」），
        # 多疾病命中给小幅加成，再归一化到 0~1。
        for r in rows:
            r["score"] = round(r["max_weight"] * (1 + 0.1 * (r["disease_hits"] - 1)), 4)
            r["symptom_hits"] = len(symptoms)
        top = max((r["score"] for r in rows), default=0) or 1
        for r in rows:
            r["score"] = round(r["score"] / top, 4)
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
        """图谱规模：各类节点数 + 各类关系数。"""
        with self._driver.session(database="neo4j") as s:
            nodes = s.run(
                "MATCH (n:Mg) RETURN labels(n)[0] AS label, count(*) AS count ORDER BY count DESC"
            ).data()
            rels = s.run(
                "MATCH (:Mg)-[r]->(:Mg) RETURN type(r) AS type, count(*) AS count ORDER BY count DESC"
            ).data()
        return {"nodes": nodes, "relationships": rels}

    def symptom_names(self, limit: int = 1000) -> list[str]:
        """标准症状名（排除同义词节点，供前端下拉/提示）。"""
        with self._driver.session(database="neo4j") as s:
            rows = s.run(
                "MATCH (n:Symptom:Mg) WHERE NOT (n)-[:SYNONYM_OF]->() "
                "RETURN n.name AS name ORDER BY name LIMIT $limit",
                limit=limit,
            ).data()
        return [r["name"] for r in rows]

    def network(self, symptom: str, limit: int = 30) -> dict:
        """症状 → 疾病 → 科室 的子图（nodes + edges），供前端可视化。"""
        cql = """
        MATCH (s:Symptom:Mg {name: $symptom})-[:INDICATES]->(d:Disease:Mg)-[:BELONGS_TO]->(dept:Department:Mg)
        RETURN s.name AS symptom, d.name AS disease,
               dept.code AS dept_code, dept.name AS dept_name
        LIMIT $limit
        """
        with self._driver.session(database="neo4j") as s:
            rows = s.run(cql, symptom=symptom, limit=limit).data()

        nodes: dict[str, dict] = {}
        edges: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for r in rows:
            sid = f"symptom::{r['symptom']}"
            did = f"disease::{r['disease']}"
            deid = f"dept::{r['dept_code']}"
            nodes[sid] = {"id": sid, "name": r["symptom"], "category": 0}
            nodes[did] = {"id": did, "name": r["disease"], "category": 1}
            nodes[deid] = {"id": deid, "name": r["dept_name"], "category": 2}
            for src, dst, label in ((sid, did, "提示"), (did, deid, "归属")):
                key = (src, dst)
                if key not in seen:
                    seen.add(key)
                    edges.append({"source": src, "target": dst, "label": label})
        return {
            "symptom": symptom,
            "nodes": list(nodes.values()),
            "edges": edges,
            "paths": len(rows),
        }


_kg: KnowledgeGraph | None = None


def get_kg() -> KnowledgeGraph:
    """进程内单例。"""
    global _kg
    if _kg is None:
        _kg = KnowledgeGraph()
    return _kg
