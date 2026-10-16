"""编排服务：把 LangGraph 编排图接入会话流程。

封装图的生命周期（启动 / 追问恢复）与结果落库：

- ``start``：创建会话后首次触发，跑图到 interrupt（追问）或 done（直接分诊）
- ``resume``：患者回答追问后恢复图，继续跑
- 图结果落库：分诊结论 → mg_triage_result；SOAP → mg_emr_record；
  MDT → mg_mdt_council；追问 → mg_session_message（AI 角色）；会话状态更新

多轮状态管理：checkpointer 用 InMemorySaver（thread_id = session_id），
``_pending`` 集合记录处于 interrupt 挂起的会话，用于区分 start / resume。
两者生命周期一致（都在进程内存），服务重启后需重新发起会话——开发期可接受，
交付期切换 PostgresSaver 后由检查点状态替代。
"""
from __future__ import annotations

import logging

from langgraph.types import Command
from sqlalchemy import func, select

from app.agents import build_triage_graph
from app.agents.state import TriageState
from app.common.database import AsyncSessionFactory
from app.common.embedder import BaseEmbedder
from app.common.enums import MessageRole, MessageType, SessionStatus
from app.common.llm_client import ModelClient
from app.models import EmrRecord, MdtCouncil, Session, SessionMessage, TriageResult
from app.retrieval import MilvusStore

logger = logging.getLogger(__name__)


class TriageOrchestrator:
    """分诊编排器：持有编译后的图，管理多轮交互与结果落库。"""

    def __init__(self, client: ModelClient, embedder: BaseEmbedder, store: MilvusStore):
        self.graph = build_triage_graph(client, embedder, store)
        self._pending: set[str] = set()

    def _config(self, session_id: str) -> dict:
        return {"configurable": {"thread_id": session_id}}

    # ---- 对外入口 ---------------------------------------------------------

    async def start(
        self,
        *,
        session_id: str,
        tenant_id: str,
        patient_id: str,
        chief_complaint: str,
        patient_hash: str | None = None,
    ) -> None:
        """创建会话后首次触发：跑图到 interrupt（追问）或 done。

        幂等：若该会话已有编排状态（复用已有会话场景），跳过 start。
        """
        snapshot = await self.graph.aget_state(self._config(session_id))
        if snapshot.values:
            logger.info("会话 %s 已有编排状态，跳过 start", session_id)
            return
        state: TriageState = {
            "session_id": session_id,
            "tenant_id": tenant_id,
            "patient_hash": patient_hash,
            "chief_complaint": chief_complaint,
            "messages": [{"role": "patient", "content": chief_complaint}],
        }
        try:
            result = await self.graph.ainvoke(state, config=self._config(session_id))
        except Exception as exc:
            logger.error("编排启动失败 session=%s: %s", session_id, exc)
            return
        await self._after_run(session_id, tenant_id, patient_id, result)

    async def resume(
        self,
        *,
        session_id: str,
        tenant_id: str,
        patient_id: str,
        answer: str,
    ) -> None:
        """患者回答追问后恢复图。会话不在挂起态则忽略。"""
        if session_id not in self._pending:
            logger.info("会话 %s 不在挂起态，忽略 resume", session_id)
            return
        try:
            result = await self.graph.ainvoke(
                Command(resume=answer), config=self._config(session_id)
            )
        except Exception as exc:
            logger.error("编排恢复失败 session=%s: %s", session_id, exc)
            return
        await self._after_run(session_id, tenant_id, patient_id, result)

    # ---- 图结果处理 -------------------------------------------------------

    async def _after_run(
        self, session_id: str, tenant_id: str, patient_id: str, result: dict
    ) -> None:
        if "__interrupt__" in result:
            self._pending.add(session_id)
            question = result["__interrupt__"][0].value.get("pending_question", "")
            await self._persist_question(session_id, tenant_id, question)
        else:
            self._pending.discard(session_id)
            await self._persist_result(session_id, tenant_id, patient_id, result)

    async def _persist_question(
        self, session_id: str, tenant_id: str, question: str
    ) -> None:
        """把追问落为 AI 消息。"""
        if not question:
            return
        async with AsyncSessionFactory() as db:
            current_max = await db.scalar(
                select(func.max(SessionMessage.seq_no)).where(
                    SessionMessage.session_id == session_id,
                    SessionMessage.tenant_id == tenant_id,
                )
            )
            db.add(
                SessionMessage(
                    tenant_id=tenant_id,
                    session_id=session_id,
                    seq_no=(current_max or 0) + 1,
                    role=MessageRole.AI.value,
                    content=question,
                    msg_type=MessageType.TEXT.value,
                )
            )
            await db.commit()

    async def _persist_result(
        self, session_id: str, tenant_id: str, patient_id: str, result: dict
    ) -> None:
        """图完成后落库：分诊结论 + SOAP 病历 + MDT 会诊 + 会话状态。"""
        async with AsyncSessionFactory() as db:
            # 幂等：已有分诊结论则跳过
            existing = await db.scalar(
                select(TriageResult).where(TriageResult.session_id == session_id)
            )
            if existing is None:
                triage = result.get("triage_result") or {}
                db.add(
                    TriageResult(
                        tenant_id=tenant_id,
                        session_id=session_id,
                        candidates_json=triage.get("recommended_depts", []),
                        confidence=triage.get("confidence", 0.0),
                        route=result.get("route", triage.get("route", "MANUAL")),
                        retrieval_mode="DENSE",
                    )
                )

                # MDT 会诊记录（若触发）
                mdt = triage.get("mdt")
                if mdt and mdt.get("opinions"):
                    candidate_codes = [
                        o.get("dept_code", "") for o in mdt["opinions"]
                    ]
                    db.add(
                        MdtCouncil(
                            tenant_id=tenant_id,
                            session_id=session_id,
                            trigger_reason="候选科室置信度差值低于阈值",
                            candidate_depts=candidate_codes,
                            opinions_json=mdt["opinions"],
                            consensus_dept=mdt.get("consensus_dept"),
                            consensus_confidence=mdt.get("consensus_confidence"),
                            divergence_flag=(
                                "1" if mdt.get("divergence_flag") else "0"
                            ),
                            divergence_json=mdt.get("divergence"),
                            missing_count=mdt.get("missing_count", 0),
                        )
                    )

            # SOAP 病历（一次会话仅一份）
            emr_exists = await db.scalar(
                select(EmrRecord).where(EmrRecord.session_id == session_id)
            )
            if emr_exists is None:
                emr = result.get("emr") or {}
                db.add(
                    EmrRecord(
                        tenant_id=tenant_id,
                        session_id=session_id,
                        patient_id=patient_id,
                        subjective=emr.get("subjective"),
                        objective=emr.get("objective"),
                        assessment=emr.get("assessment"),
                        plan=emr.get("plan"),
                        completeness_rate=emr.get("completeness_rate"),
                        generate_status=emr.get("generate_status", "SUCCESS"),
                    )
                )

            # 会话状态更新
            session = await db.get(Session, session_id)
            if session is not None:
                route = result.get("route")
                if route == "EMERGENCY" or result.get("risk_flag"):
                    session.status = SessionStatus.EMERGENCY.value
                else:
                    session.status = SessionStatus.FINISHED.value
                session.inquiry_rounds = result.get("inquiry_rounds", 0)
                session.risk_flag = "1" if result.get("risk_flag") else "0"
                triage = result.get("triage_result") or {}
                if triage.get("recommended_depts"):
                    session.dept_code = triage["recommended_depts"][0].get("dept_code")

            await db.commit()
        logger.info("编排完成 session=%s route=%s", session_id, result.get("route"))


_orchestrator: TriageOrchestrator | None = None


def get_orchestrator() -> TriageOrchestrator:
    """获取全局编排器（由 lifespan 初始化）。"""
    assert _orchestrator is not None, "编排器未初始化"
    return _orchestrator


def init_orchestrator(client: ModelClient, embedder: BaseEmbedder, store: MilvusStore) -> TriageOrchestrator:
    """构建全局编排器。"""
    global _orchestrator
    _orchestrator = TriageOrchestrator(client, embedder, store)
    return _orchestrator
