"""分诊编排图：危重症拦截 → 澄清追问 ⇄ 路由 → 分诊结论。

图结构（对齐《02 架构》§5.2.2）：
    START → safety（危重症拦截）
         → [命中] → END（急诊，中断）
         → [未命中] → inquiry（信息充分度判定）
                    → [不充分] → interrupt 追问 → 患者回答 → 回到 inquiry
                    → [充分] → router（候选科室 + 结论）→ END

检查点用 InMemorySaver（开发期），thread_id 用 mg_session.id，后续可切 PostgresSaver。
"""
from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from app.agents.nodes.inquiry import build_inquiry_node
from app.agents.nodes.safety import safety_node
from app.agents.nodes.triage_router import build_router_node
from app.agents.state import TriageState
from app.common.embedder import BaseEmbedder
from app.common.llm_client import ModelClient
from app.retrieval import MilvusStore


def build_triage_graph(
    client: ModelClient, embedder: BaseEmbedder, store: MilvusStore
):
    """构建并编译分诊编排图。"""
    g = StateGraph(TriageState)

    g.add_node("safety", safety_node)
    g.add_node("inquiry", build_inquiry_node(client))
    g.add_node("router", build_router_node(client, embedder, store))

    g.add_edge(START, "safety")

    # 危重症命中 → 直接结束（急诊引导由 service 层处理）
    g.add_conditional_edges(
        "safety",
        lambda s: "emergency" if s.get("risk_flag") else "inquiry",
        {"emergency": END, "inquiry": "inquiry"},
    )

    # 信息不充分 → 循环回 inquiry；充分 → 路由
    g.add_conditional_edges(
        "inquiry",
        lambda s: "router" if s.get("sufficient") else "inquiry",
        {"router": "router", "inquiry": "inquiry"},
    )

    g.add_edge("router", END)

    return g.compile(checkpointer=InMemorySaver())
