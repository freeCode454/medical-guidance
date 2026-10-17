"""澄清追问节点（F34 / F41）。

一轮 LLM 调用完成：提取医学信息 + 判断充分度 + 生成追问。
信息不充分时调用 ``interrupt`` 挂起图，返回追问给患者；患者回答后经
``Command(resume=answer)`` 恢复，回答追加进对话记录，图循环回本节点重新判定。

追问轮次上限从状态 inquiry_rounds 判断，超过上限强制视为充分（避免无限追问）。
"""
from __future__ import annotations

import json
import logging

from langgraph.types import interrupt

from app.agents.state import TriageState
from app.common.llm_client import ModelClient
from app.services import rules_engine
from app.ws import events

logger = logging.getLogger(__name__)

# 追问轮次上限（与 mg_sys_config 的 inquiry.max_rounds 默认一致）
MAX_ROUNDS = 8

_SCHEMA = {
    "name": "inquiry",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "sufficient": {"type": "boolean"},
            "collected": {
                "type": "object",
                "properties": {
                    "duration": {"type": ["string", "null"]},
                    "location": {"type": ["string", "null"]},
                    "nature": {"type": ["string", "null"]},
                    "accompanying": {"type": "array", "items": {"type": "string"}},
                    "past_history": {"type": "array", "items": {"type": "string"}},
                    "allergy": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["duration", "location", "nature", "accompanying", "past_history", "allergy"],
                "additionalProperties": False,
            },
            "missing": {"type": "array", "items": {"type": "string"}},
            "question": {"type": "string"},
        },
        "required": ["sufficient", "collected", "missing", "question"],
        "additionalProperties": False,
    },
}


def _build_prompt(state: TriageState) -> str:
    messages = state.get("messages", [])
    history = "\n".join(f"{m.get('role')}: {m.get('content')}" for m in messages)
    entities = state.get("entities", {})
    asked = "、".join(state.get("asked", [])) or "无"
    return (
        "你是医疗预问诊信息采集助手。判断已有信息是否足够用于分诊，避免不必要的追问。\n\n"
        f"患者主诉：{state.get('chief_complaint', '')}\n\n"
        f"对话历史：\n{history}\n\n"
        f"已采集信息：{json.dumps(entities, ensure_ascii=False)}\n"
        f"已问过：{asked}\n\n"
        "已采集判定标准（关键）：主诉或对话里【已经提到】的信息就算已采集，"
        "不要因为「不够具体」而重复追问。例如：\n"
        "- 提到「三天了」= 时长已采集\n"
        "- 提到「肚脐周围」= 部位已采集\n"
        "- 提到「绞痛」「一阵一阵」= 性质已采集\n"
        "- 提到「拉肚子」= 伴随症状已采集\n\n"
        "充分度门槛：只要具备「主诉 + 时长 + 部位」，就判定 sufficient=true。\n"
        "仅当完全缺失时长或部位时才追问，且一轮只问 1 个最关键的缺失项。\n"
        "collected 字段填入从对话中提取到的信息（未提到为 null 或空数组）。"
    )


def build_inquiry_node(client: ModelClient):
    """构造澄清追问节点（绑定 client）。"""

    async def inquiry_node(state: TriageState) -> dict:
        session_id = state.get("session_id", "")
        events.emit_node_start(
            session_id, events.NODE_INQUIRY, "信息采集与追问", "正在评估信息是否充分"
        )
        # 轮次上限：超过则强制充分，不再追问
        if state.get("inquiry_rounds", 0) >= MAX_ROUNDS:
            events.emit_node_complete(
                session_id, events.NODE_INQUIRY, {"sufficient": True, "round_limit": True}
            )
            return {"sufficient": True}

        prompt = _build_prompt(state)
        reply = await client.chat(
            [{"role": "user", "content": prompt}],
            small=True,
            json_schema=_SCHEMA,
            capability="llm_chat",
        )
        try:
            result = json.loads(reply)
        except json.JSONDecodeError:
            logger.warning("澄清追问解析失败，视为信息充分")
            events.emit_node_complete(
                session_id, events.NODE_INQUIRY, {"sufficient": True, "degraded": True}
            )
            return {"sufficient": True}

        collected = result.get("collected") or {}
        entities: dict = dict(state.get("entities", {}))
        for key, value in collected.items():
            if value not in (None, [], ""):
                entities[key] = value

        round_now = state.get("inquiry_rounds", 0) + 1

        if result.get("sufficient"):
            events.emit_node_complete(
                session_id, events.NODE_INQUIRY, {"sufficient": True, "inquiry_rounds": round_now}
            )
            return {"sufficient": True, "entities": entities, "inquiry_rounds": round_now}

        # 不充分：先推送本轮追问，再挂起图等待患者回答
        missing = result.get("missing", [])
        question = result.get("question", "")

        # 结构化追问模板优先：按主诉类型取模板，顺序固定（部位→时长→性质→程度→诱因→伴随…），
        # 已问过的 slot 跳过；模板未命中（主诉类型未知）时才用 LLM 生成的追问。
        complaint_type = rules_engine.infer_complaint_type(state.get("chief_complaint", ""))
        logger.debug(
            "inquiry 模板匹配 chief_complaint=%r type=%r asked=%r",
            state.get("chief_complaint"),
            complaint_type,
            state.get("asked"),
        )
        template_exhausted = False
        if complaint_type:
            asked_slots = set(state.get("asked", []))
            # 从对话历史反查已问过的问题原文：
            # asked 状态依赖 interrupt 之后的 return，LangGraph 重放节点时可能拿不到，
            # 而 messages 是累积的，用它兜底最可靠。
            asked_questions = {
                m.get("content", "")
                for m in state.get("messages", [])
                if m.get("role") in ("assistant", "AI")
            }
            templates = rules_engine.inquiry_templates(complaint_type)
            for tpl in templates:
                slot = tpl.get("target_slot")
                q = tpl.get("question") or ""
                # 双重判断：slot 没问过，且问题原文也没出现过
                if slot and slot not in asked_slots and q not in asked_questions:
                    question = q or question
                    missing = [slot]
                    logger.info("模板选中追问 slot=%s session=%s", slot, session_id)
                    break
            else:
                # 该主诉的追问维度已全部问过，判定充分。
                # 否则会回落到 LLM 自由生成问题，而 LLM 看不到已问过什么，容易原地打转。
                template_exhausted = bool(templates)

        if template_exhausted:
            logger.info("追问维度已用尽，判定充分 session=%s type=%s", session_id, complaint_type)
            events.emit_node_complete(
                session_id,
                events.NODE_INQUIRY,
                {"sufficient": True, "reason": "template_exhausted", "inquiry_rounds": round_now},
            )
            return {"sufficient": True, "entities": entities, "inquiry_rounds": round_now}

        # 双保险：LLM 生成的问题若与历史 AI 追问重复，同样判定充分
        asked_before = {
            m.get("content", "")
            for m in state.get("messages", [])
            if m.get("role") in ("assistant", "AI")
        }
        if question and question in asked_before:
            logger.info("追问重复，判定充分 session=%s question=%r", session_id, question)
            events.emit_node_complete(
                session_id,
                events.NODE_INQUIRY,
                {"sufficient": True, "reason": "duplicate_question", "inquiry_rounds": round_now},
            )
            return {"sufficient": True, "entities": entities, "inquiry_rounds": round_now}

        events.emit_node_complete(
            session_id,
            events.NODE_INQUIRY,
            {"sufficient": False, "content": question, "asked": missing, "inquiry_rounds": round_now},
        )
        answer = interrupt({"pending_question": question, "asked": missing})
        # 患者回答后恢复：追问 + 回答都追加进对话，图循环回本节点
        return {
            "messages": [
                {"role": "assistant", "content": question},
                {"role": "patient", "content": answer},
            ],
            "asked": missing,
            "entities": entities,
            "inquiry_rounds": round_now,
            "sufficient": False,
        }

    return inquiry_node
