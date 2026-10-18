"""编排服务：把 LangGraph 编排图接入会话流程。

封装图的生命周期（启动 / 追问恢复）与结果落库：

- ``start``：创建会话后首次触发，跑图到 interrupt（追问）或 done（直接分诊）
- ``resume``：患者回答追问后恢复图，继续跑
- 图结果落库：分诊结论 → mg_triage_result；SOAP → mg_emr_record；
  MDT → mg_mdt_council；追问 → mg_session_message（AI 角色）；会话状态更新

多轮状态管理：checkpointer 由应用生命周期注入（PostgreSQL 为交付默认，
内存仅用于单测）；thread_id = session_id。``_pending`` 只是进程内加速提示，
真正判定是否处于挂起态以检查点快照（``interrupts`` / ``next``）为准，
因此服务重启后仍能恢复追问。
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from langgraph.types import Command
from sqlalchemy import func, select

from app.agents import build_triage_graph
from app.agents.nodes.safety import detect_emergency
from app.agents.state import TriageState
from app.common.database import AsyncSessionFactory, lock_message_sequence
from app.common.embedder import BaseEmbedder
from app.common.enums import MessageRole, MessageType, SessionStatus
from app.common.llm_client import ModelClient
from app.models import EmrRecord, MdtCouncil, Session, SessionMessage, TriageResult
from app.retrieval import MilvusStore
from app.ws import events

logger = logging.getLogger(__name__)


def _build_evidence(result: dict) -> dict:
    """把 state 里的症状摘要 / 风险标记固化为分诊依据快照。

    患者端只读这份快照（``mg_triage_result.evidence_json``），不接触仅存在于
    编排进程内存里的 state，因此进程重启后仍能还原「当时问了什么」。
    """
    entities = result.get("entities") or {}
    summary = {
        "chief_complaint": result.get("chief_complaint"),
        "duration": entities.get("duration"),
        "location": entities.get("location"),
        "nature": entities.get("nature"),
        "accompanying": entities.get("accompanying"),
        "past_history": entities.get("past_history"),
        "allergy": entities.get("allergy"),
    }
    triage = result.get("triage_result") or {}
    kg_paths: list[dict] = []
    for dept in triage.get("recommended_depts") or []:
        kg_paths.extend(dept.get("kg_paths") or [])

    return {
        "symptom_summary": {
            key: value
            for key, value in summary.items()
            if value not in (None, "", [])
        },
        "risk_flag": bool(result.get("risk_flag")),
        "risk_reason": result.get("risk_reason"),
        "kg_paths": kg_paths,
    }


class TriageOrchestrator:
    """分诊编排器：持有编译后的图，管理多轮交互与结果落库。"""

    def __init__(
        self,
        client: ModelClient,
        embedder: BaseEmbedder,
        store: MilvusStore,
        checkpointer: Any = None,
    ):
        self.graph = build_triage_graph(client, embedder, store, checkpointer)
        self._pending: set[str] = set()

    def _config(self, session_id: str) -> dict:
        return {"configurable": {"thread_id": session_id}}

    async def _has_pending(self, session_id: str) -> bool:
        """是否处于挂起态。

        以检查点快照为准（``interrupts`` 或 ``next`` 非空），而不是只看进程内集合，
        这样服务重启/多 worker 后仍能正确 resume。
        """
        if session_id in self._pending:
            return True
        try:
            snapshot = await self.graph.aget_state(self._config(session_id))
        except Exception:
            logger.warning("读取检查点失败 session=%s", session_id, exc_info=True)
            return False
        return bool(snapshot.interrupts) or bool(snapshot.next)

    # ---- 对外入口 ---------------------------------------------------------

    async def start(
        self,
        *,
        session_id: str,
        tenant_id: str,
        patient_id: str,
        chief_complaint: str,
        patient_hash: str | None = None,
        gender: str | None = None,
        age: int | None = None,
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
        if gender:
            state["gender"] = gender
        if age is not None:
            state["age"] = age
        try:
            result = await self.graph.ainvoke(state, config=self._config(session_id))
        except Exception:
            logger.exception("编排启动失败 session=%s", session_id)
            return
        await self._safe_after_run(session_id, tenant_id, patient_id, result)

    async def resume(
        self,
        *,
        session_id: str,
        tenant_id: str,
        patient_id: str,
        answer: str,
    ) -> None:
        """患者回答追问后恢复图。会话不处于挂起态则忽略。"""
        if not await self._has_pending(session_id):
            logger.info("会话 %s 不在挂起态，忽略 resume", session_id)
            return

        # 危重症规则不能只判首轮主诉：追问回答里补出「胸口疼、冒冷汗」
        # 同样必须立即转急诊（临床红线，F50）。
        if detect_emergency(answer):
            logger.warning("追问回答命中危重症红线 session=%s", session_id)
            self._pending.discard(session_id)
            events.emit_emergency(
                session_id,
                "追问回答命中危重症红线",
                "您的症状需要立即就医，请立即前往就近医院急诊科或拨打 120",
            )
            await self._safe_after_run(
                session_id,
                tenant_id,
                patient_id,
                {
                    "route": "EMERGENCY",
                    "risk_flag": True,
                    "risk_reason": "追问回答命中急危重症预警规则",
                    "chief_complaint": answer,
                },
            )
            return

        try:
            result = await self.graph.ainvoke(
                Command(resume=answer), config=self._config(session_id)
            )
        except Exception:
            logger.exception("编排恢复失败 session=%s", session_id)
            return
        await self._safe_after_run(session_id, tenant_id, patient_id, result)

    async def _safe_after_run(
        self, session_id: str, tenant_id: str, patient_id: str, result: dict
    ) -> None:
        """落库失败不能静默：记录堆栈并给患者端一个可重试的错误事件。"""
        try:
            await self._after_run(session_id, tenant_id, patient_id, result)
        except Exception:
            logger.exception("编排结果落库失败 session=%s", session_id)
            events.emit_node_error(
                session_id,
                "ORCHESTRATION",
                60000,
                "问诊结果保存失败，请稍后重试",
                degraded=False,
            )

    # ---- 图结果处理 -------------------------------------------------------

    async def _after_run(
        self, session_id: str, tenant_id: str, patient_id: str, result: dict
    ) -> None:
        if "__interrupt__" in result:
            self._pending.add(session_id)
            intr = result["__interrupt__"][0].value or {}
            question = intr.get("pending_question", "")
            asked = intr.get("asked") or []
            rounds = intr.get("inquiry_rounds", 0)
            await self._persist_question(session_id, tenant_id, question)
            # 把本轮追问的 slot 与问题立刻写入 state。
            # LangGraph resume 会重放整个节点，重放时节点从 state 读 pending_question
            # （不再重新生成），保证「用户回答」与「原问题」正确配对。
            try:
                await self.graph.aupdate_state(
                    self._config(session_id),
                    {"asked": asked, "pending_question": question},
                )
            except Exception as exc:
                logger.warning("更新追问状态失败 session=%s: %s", session_id, exc)
            # 问题推送统一收敛在这里：节点内 emit 会因 LangGraph 重放而重复，
            # 导致患者端一次收到两条 AI 消息。
            events.emit_node_complete(
                session_id,
                events.NODE_INQUIRY,
                {"sufficient": False, "content": question, "inquiry_rounds": rounds},
            )
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
            await lock_message_sequence(db, session_id)
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
        triage = result.get("triage_result") or {}
        route = result.get("route") or triage.get("route") or "MANUAL"
        risk_flag = bool(result.get("risk_flag"))
        final_status = (
            SessionStatus.EMERGENCY.value
            if route == "EMERGENCY" or risk_flag
            # 非急诊会话进入「待接管」：任何同租户医生可认领，
            # 否则 doctor_id 为空时医生端永远看不到该患者。
            else SessionStatus.PENDING_TAKEOVER.value
        )
        triage_result_id: str | None = None
        emr_record_id: str | None = None

        async with AsyncSessionFactory() as db:
            # 幂等：已有分诊结论则跳过
            existing = await db.scalar(
                select(TriageResult).where(
                    TriageResult.session_id == session_id,
                    TriageResult.tenant_id == tenant_id,
                )
            )
            if existing is None:
                tr = TriageResult(
                    tenant_id=tenant_id,
                    session_id=session_id,
                    candidates_json=triage.get("recommended_depts", []),
                    confidence=triage.get("confidence", 0.0),
                    route=route,
                    retrieval_mode=result.get("retrieval_mode") or "HYBRID",
                    evidence_json=_build_evidence(result),
                )
                db.add(tr)
                triage_result_id = tr.id

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

            # SOAP 病历（一次会话仅一份；急诊直达不生成空病历）
            emr = result.get("emr") or {}
            emr_exists = await db.scalar(
                select(EmrRecord).where(
                    EmrRecord.session_id == session_id,
                    EmrRecord.tenant_id == tenant_id,
                )
            )
            if emr_exists is None and emr:
                er = EmrRecord(
                    tenant_id=tenant_id,
                    session_id=session_id,
                    patient_id=patient_id,
                    subjective=emr.get("subjective"),
                    objective=emr.get("objective"),
                    assessment=emr.get("assessment"),
                    plan=emr.get("plan"),
                    soap_json={
                        "subjective": emr.get("subjective"),
                        "objective": emr.get("objective"),
                        "assessment": emr.get("assessment"),
                        "plan": emr.get("plan"),
                        "entities": result.get("entities") or {},
                    },
                    completeness_rate=emr.get("completeness_rate"),
                    generate_status=emr.get("generate_status", "SUCCESS"),
                )
                db.add(er)
                emr_record_id = er.id

            # 会话状态更新
            session = await db.get(Session, session_id)
            if session is not None:
                session.inquiry_rounds = result.get("inquiry_rounds", 0)
                session.risk_flag = "1" if risk_flag else "0"
                # 只推进仍处于问诊中的会话：医生已接管/已关闭的会话不能被后台覆盖
                if session.status == SessionStatus.IN_PROGRESS.value:
                    session.status = final_status
                    if final_status == SessionStatus.FINISHED.value:
                        session.finished_time = datetime.now(UTC)
                # 已有人工接管时不覆盖科室（医生可能已修正）
                if session.doctor_id is None and triage.get("recommended_depts"):
                    session.dept_code = triage["recommended_depts"][0].get("dept_code")

            await db.commit()

        logger.info(
            "编排完成 session=%s route=%s status=%s",
            session_id,
            route,
            final_status,
        )

        # 发射 task_complete 事件（对话通道）
        depts = triage.get("recommended_depts") or []
        top = depts[0] if depts else {}
        events.emit_task_complete(
            session_id,
            {
                "session_id": session_id,
                "session_status": final_status,
                "result": {
                    "route": route,
                    "dept_code": top.get("dept_code"),
                    "dept_name": top.get("dept_name"),
                    "confidence": triage.get("confidence", 0.0),
                    "inquiry_rounds": result.get("inquiry_rounds", 0),
                    "triage_result_id": triage_result_id,
                    "emr_record_id": emr_record_id,
                },
                "suggest_next": (
                    ["FETCH_TRIAGE_RESULT"]
                    if final_status == SessionStatus.EMERGENCY.value
                    else ["FETCH_TRIAGE_RESULT", "FETCH_EMR"]
                ),
            },
        )


_orchestrator: TriageOrchestrator | None = None


def get_orchestrator() -> TriageOrchestrator:
    """获取全局编排器（由 lifespan 初始化）。"""
    assert _orchestrator is not None, "编排器未初始化"
    return _orchestrator


def init_orchestrator(
    client: ModelClient,
    embedder: BaseEmbedder,
    store: MilvusStore,
    checkpointer: Any = None,
) -> TriageOrchestrator:
    """构建全局编排器。"""
    global _orchestrator
    _orchestrator = TriageOrchestrator(client, embedder, store, checkpointer)
    return _orchestrator
