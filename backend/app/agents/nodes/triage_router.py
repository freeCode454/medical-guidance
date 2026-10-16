"""分流路由节点（F33 / F41 / F56）。

候选科室召回 + 决策表路由（DIRECT / MDT / MANUAL）+ 分诊结论生成。
路由以 LLM 判断的置信度判定（检索相似度对长查询会被稀释，不宜直接作阈值）。
"""
from __future__ import annotations

import logging

from app.agents.state import TriageState
from app.common.embedder import BaseEmbedder
from app.common.llm_client import ModelClient
from app.retrieval import MilvusStore
from app.services.triage_service import generate_triage, recall_depts

logger = logging.getLogger(__name__)


def _decide_route(
    confidence: float,
    depts: list[dict],
    low_confidence_threshold: float = 0.3,
    gap_threshold: float = 0.1,
) -> str:
    """决策表路由（用 LLM 分诊置信度判定，阈值来自 mg_sys_config）。

    - 无候选科室 → MANUAL（检索无依据，必须转人工）
    - 多科室且前两位置信度差值小于阈值 → MDT（多科需会诊）
    - 有明确推荐但整体置信度极低（< 0.3）→ MANUAL（模型自身信心不足）
    - 否则 → DIRECT

    注：置信度不是硬门槛——检索召回的候选科室本身有向量依据，
    LLM 在候选内做推荐（如 0.56 明确指向消化内科）即为有效结论，
    不应因略低于 0.6 就转人工。仅当无候选或模型自身信心极低才 MANUAL。
    """
    if not depts:
        return "MANUAL"
    if len(depts) > 1:
        confs = [d.get("confidence", 0) for d in depts]
        if (confs[0] - confs[1]) < gap_threshold:
            return "MDT"
    if confidence < low_confidence_threshold:
        return "MANUAL"
    return "DIRECT"


def _build_query(state: TriageState) -> str:
    """用主诉 + 关键实体（部位、伴随症状）拼接检索查询。

    精简原则：查询过长会稀释向量相似度，只保留对分诊最关键的字段。
    """
    complaint = state.get("chief_complaint", "")
    entities = state.get("entities", {})
    parts = [complaint]
    if entities.get("location"):
        parts.append(str(entities["location"]))
    acc = entities.get("accompanying")
    if isinstance(acc, list):
        parts.extend(str(v) for v in acc)
    return " ".join(p for p in parts if p)


def build_router_node(client: ModelClient, embedder: BaseEmbedder, store: MilvusStore):
    """构造分流路由节点（绑定资源）。"""

    async def router_node(state: TriageState) -> dict:
        query = _build_query(state)
        tenant_id = state["tenant_id"]

        result = await generate_triage(
            client, embedder, store, complaint=query, tenant_id=tenant_id
        )
        # 决策表路由（以 LLM 置信度判定，覆盖 LLM 自身的 route）
        route = _decide_route(
            result.get("confidence", 0.0), result.get("recommended_depts", [])
        )
        result["route"] = route
        return {"route": route, "triage_result": result}

    return router_node
