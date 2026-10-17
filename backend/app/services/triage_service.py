"""分诊服务：候选科室召回 + 分诊结论生成。"""
from __future__ import annotations

import json
import logging

from app.common.embedder import BaseEmbedder
from app.common.llm_client import ModelClient
from app.retrieval import KB_DEPT, MilvusStore
from app.retrieval.fusion import fuse
from app.services import rules_engine

logger = logging.getLogger(__name__)

# 分诊结论的结构化输出约束（OpenAI json_schema 格式）
_TRIAGE_SCHEMA = {
    "name": "triage",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "route": {"type": "string", "enum": ["DIRECT", "MDT", "MANUAL", "EMERGENCY"]},
            "confidence": {"type": "number"},
            "recommended_depts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "dept_code": {"type": "string"},
                        "dept_name": {"type": "string"},
                        "confidence": {"type": "number"},
                        "reason": {"type": "string"},
                    },
                    "required": ["dept_code", "dept_name", "confidence", "reason"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["route", "confidence", "recommended_depts"],
        "additionalProperties": False,
    },
}


def _build_triage_prompt(complaint: str, depts: list[dict]) -> str:
    dept_lines = "\n".join(
        f"- {d['dept_code']} {d.get('dept_name', '')}（相关度 {d['score']:.2f}）"
        for d in depts
    )
    return (
        "你是医院智能导诊分诊助手。根据患者主诉和候选科室，给出分诊建议。\n\n"
        f"患者主诉：{complaint}\n\n"
        f"候选科室（按检索相关度排序）：\n{dept_lines}\n\n"
        "请判断：\n"
        "1. route：DIRECT（单一科室明确）/ MDT（多科需会诊）/ MANUAL（信息不足转人工）\n"
        "2. recommended_depts：推荐科室，dept_code 与 dept_name 必须严格取自上述候选列表，不得编造\n"
        "3. confidence：整体置信度 0~1\n\n"
        "要求：只输出科室，不得出现任何疾病名称。"
    )


async def recall_depts(
    embedder: BaseEmbedder,
    store: MilvusStore,
    *,
    complaint: str,
    tenant_id: str,
    mode: str = "HYBRID",
    limit: int = 10,
    client: ModelClient | None = None,
    gender: str | None = None,
    age: int | None = None,
) -> list[dict]:
    """主诉 → 候选科室。

    链路：向量召回（稠密+稀疏+RRF）→ rerank 精排 → 分诊规则加权。
    rerank 或规则缺失时自动降级，不阻断主链路。
    返回：[{"dept_code", "dept_name", "score"}, ...]，按最终分降序。
    """
    emb = (await embedder.embed([complaint]))[0]
    recall_k = max(limit * 2, 20)  # 先多召回，再精排收窄

    dense_hits = store.dense_search(
        KB_DEPT,
        dense=emb.dense,
        filter_expr=f'tenant_id == "{tenant_id}"',
        limit=recall_k,
    )

    sparse_hits: list[dict] = []
    if emb.has_sparse and mode != "DENSE":
        sparse_hits = store.sparse_search(
            KB_DEPT,
            sparse=emb.sparse or {},
            filter_expr=f'tenant_id == "{tenant_id}"',
            limit=recall_k,
        )

    fused = fuse(dense_hits, sparse_hits, mode=mode)

    candidates = [
        {
            "dept_code": h["dept_code"],
            "dept_name": h.get("dept_name", ""),
            "text": h.get("text", "") or h.get("dept_name", ""),
            "vec": float(h.get("score", 0)),
        }
        for h in fused
    ]

    # 人群硬过滤：男性患者直接剔除妇科/产科。
    # 规则加权（0.15）压不过向量+精排的分差，必须在候选层剔除，避免「男患者被推荐妇科」。
    if gender == "男":
        exclude = {"GYN", "OB"}
        candidates = [c for c in candidates if c["dept_code"] not in exclude]

    # 分诊规则命中（确定性信号）：年龄/性别不符的规则会被过滤掉
    bonus = rules_engine.match_dept_bonus(complaint, gender=gender, age=age)

    # rerank 精排
    rerank_scores: dict[str, float] = {}
    if client is not None and candidates:
        try:
            docs = [c["text"] for c in candidates]
            ranked = await client.rerank(complaint, docs, top_n=len(docs))
            for idx, score in ranked:
                if 0 <= idx < len(candidates):
                    rerank_scores[candidates[idx]["dept_code"]] = float(score)
        except Exception as exc:  # 精排失败降级，不影响可用性
            logger.warning("rerank 失败，降级为向量+规则：%s", exc)

    # 各分量归一化到 0~1
    max_vec = max((c["vec"] for c in candidates), default=0) or 1.0
    max_rr = max(rerank_scores.values(), default=0) or 1.0
    max_rule = max(bonus.values(), default=0) or 1.0

    for c in candidates:
        vec_n = c["vec"] / max_vec
        rr_n = rerank_scores.get(c["dept_code"], 0) / max_rr if rerank_scores else 0.0
        rule_n = bonus.get(c["dept_code"], 0) / max_rule
        # 权重：精排为主，向量次之，规则作确定性补充
        c["final"] = 0.55 * rr_n + 0.30 * vec_n + 0.15 * rule_n

    candidates.sort(key=lambda x: x["final"], reverse=True)
    result = [
        {
            "dept_code": c["dept_code"],
            "dept_name": c["dept_name"],
            "score": round(c["final"], 4),
        }
        for c in candidates[:limit]
    ]

    # 图谱推理路径：作为可解释证据附加（不参与排序，避免影响已验证的排序质量）
    try:
        from app.services.kg_service import get_kg

        kg = get_kg()
        kg_map = {r["dept_code"]: r for r in kg.infer_depts(complaint, limit=20)}
        for r in result:
            hit = kg_map.get(r["dept_code"])
            if hit:
                r["kg_paths"] = hit["paths"]
                r["kg_disease_hits"] = hit["disease_hits"]
    except Exception as exc:  # 图谱不可用不影响分诊
        logger.debug("图谱证据跳过：%s", exc)

    return result


async def generate_triage(
    client: ModelClient,
    embedder: BaseEmbedder,
    store: MilvusStore,
    *,
    complaint: str,
    tenant_id: str,
    mode: str = "HYBRID",
    limit: int = 10,
    gender: str | None = None,
    age: int | None = None,
) -> dict:
    """主诉 → 分诊结论（候选科室召回 + rerank + 规则加权 + LLM 生成）。

    返回：{"route", "confidence", "recommended_depts": [{dept_code, dept_name,
    confidence, reason}]}。患者视图只含科室，不含疾病名（R01）。
    """
    depts = await recall_depts(
        embedder,
        store,
        complaint=complaint,
        tenant_id=tenant_id,
        mode=mode,
        limit=limit,
        client=client,
        gender=gender,
        age=age,
    )
    dept_map = {d["dept_code"]: d.get("dept_name", "") for d in depts}

    prompt = _build_triage_prompt(complaint, depts)
    reply = await client.chat(
        [{"role": "user", "content": prompt}],
        small=False,
        json_schema=_TRIAGE_SCHEMA,
        capability="llm_chat",
    )
    try:
        result = json.loads(reply)
    except json.JSONDecodeError:
        # LLM 返回非 JSON 时降级：转人工，避免把脏数据写进结论
        return {
            "route": "MANUAL",
            "confidence": 0.0,
            "recommended_depts": [],
        }

    # 兜底校验：dept_code 必须来自检索召回，防止 LLM 幻觉编造科室
    top = depts[0] if depts else {"dept_code": "", "dept_name": ""}
    for rec in result.get("recommended_depts", []):
        if rec.get("dept_code") not in dept_map:
            rec["dept_code"] = top["dept_code"]
            rec["dept_name"] = dept_map.get(top["dept_code"], top.get("dept_name", ""))
        # 附加图谱推理路径（供医生端展示「为什么推荐这个科室」）
        for d in depts:
            if d["dept_code"] == rec.get("dept_code") and d.get("kg_paths"):
                rec["kg_paths"] = d["kg_paths"]
                rec["kg_disease_hits"] = d.get("kg_disease_hits", 0)
                break
    return result


async def run_triage_and_persist(
    session_id: str,
    tenant_id: str,
    complaint: str,
    client: ModelClient,
    store: MilvusStore,
) -> None:
    """后台执行分诊并写 mg_triage_result（幂等：已有结论则跳过）。

    由 send_message 接口以 BackgroundTasks 触发，响应立即返回，
    分诊在后台完成，符合「AI 回复异步」的语义（04 文档 12.2.4）。
    """
    from sqlalchemy import select

    from app.common.database import AsyncSessionFactory
    from app.models import TriageResult

    # 幂等：已有结论则跳过（同一会话只生成一次）
    async with AsyncSessionFactory() as db:
        existing = await db.scalar(
            select(TriageResult).where(TriageResult.session_id == session_id)
        )
    if existing is not None:
        return

    try:
        result = await generate_triage(
            client, client.embedder, store, complaint=complaint, tenant_id=tenant_id
        )
    except Exception as exc:  # LLM/网络异常不阻断会话，留待重试
        logger.error("分诊失败 session=%s: %s", session_id, exc)
        return

    async with AsyncSessionFactory() as db:
        db.add(
            TriageResult(
                tenant_id=tenant_id,
                session_id=session_id,
                candidates_json=result["recommended_depts"],
                confidence=result["confidence"],
                route=result["route"],
                retrieval_mode="DENSE",
            )
        )
        await db.commit()
    logger.info("分诊完成 session=%s route=%s", session_id, result["route"])

