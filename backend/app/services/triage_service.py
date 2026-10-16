"""分诊服务：候选科室召回 + 分诊结论生成。"""
from __future__ import annotations

import json
import logging

from app.common.embedder import BaseEmbedder
from app.common.llm_client import ModelClient
from app.retrieval import KB_DEPT, MilvusStore
from app.retrieval.fusion import fuse

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
) -> list[dict]:
    """主诉 → 候选科室召回（按 score 降序）。

    返回：[{"dept_code": str, "score": float}, ...]
    """
    emb = (await embedder.embed([complaint]))[0]

    dense_hits = store.dense_search(
        KB_DEPT,
        dense=emb.dense,
        filter_expr=f'tenant_id == "{tenant_id}"',
        limit=limit,
    )

    sparse_hits: list[dict] = []
    if emb.has_sparse and mode != "DENSE":
        sparse_hits = store.sparse_search(
            KB_DEPT,
            sparse=emb.sparse or {},
            filter_expr=f'tenant_id == "{tenant_id}"',
            limit=limit,
        )

    fused = fuse(dense_hits, sparse_hits, mode=mode)
    return [
        {
            "dept_code": h["dept_code"],
            "dept_name": h.get("dept_name", ""),
            "score": float(h.get("score", 0)),
        }
        for h in fused
    ]


async def generate_triage(
    client: ModelClient,
    embedder: BaseEmbedder,
    store: MilvusStore,
    *,
    complaint: str,
    tenant_id: str,
    mode: str = "DENSE",
    limit: int = 10,
) -> dict:
    """主诉 → 分诊结论（候选科室召回 + LLM 生成）。

    返回：{"route", "confidence", "recommended_depts": [{dept_code, dept_name,
    confidence, reason}]}。患者视图只含科室，不含疾病名（R01）。
    """
    depts = await recall_depts(
        embedder, store, complaint=complaint, tenant_id=tenant_id, mode=mode, limit=limit
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

