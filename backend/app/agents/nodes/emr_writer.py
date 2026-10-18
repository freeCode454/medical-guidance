"""SOAP 病历生成节点（F36）。

把整段对话整理成符合规范的四段式预问诊病历。设计对齐《03 数据库》
mg_emr_record 表与《02 架构》§5.2.3：

- S（Subjective）主观资料：主诉、现病史、既往史、过敏史
- O（Objective）客观资料：已采集的体征信息（预问诊阶段通常为缺省/自述）
- A（Assessment）评估：鉴别方向，**仅医生端可见**，患者端剔除
- P（Plan）计划：建议就诊科室、建议补充检查，**不得含用药建议**

明确不做：不给用药建议（F36）、不伪造缺失内容（AC-F36-2）。
生成失败或部分缺失时降级为 PARTIAL，绝不编造。
"""
from __future__ import annotations

import json
import logging

from app.agents.state import TriageState
from app.common.llm_client import ModelClient
from app.ws import events

logger = logging.getLogger(__name__)

_SOAP_SCHEMA = {
    "name": "soap_emr",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "subjective": {"type": "string"},
            "objective": {"type": "string"},
            "assessment": {"type": "string"},
            "plan": {"type": "string"},
            "completeness_rate": {"type": "number"},
        },
        "required": ["subjective", "objective", "assessment", "plan", "completeness_rate"],
        "additionalProperties": False,
    },
}


def _build_prompt(state: TriageState) -> str:
    messages = state.get("messages", [])
    history = "\n".join(f"{m.get('role')}: {m.get('content')}" for m in messages)
    entities = state.get("entities", {})
    triage = state.get("triage_result", {})
    depts = triage.get("recommended_depts", [])
    dept_lines = "\n".join(
        f"- {d.get('dept_code')} {d.get('dept_name', '')}" for d in depts
    )
    return (
        "你是门诊预问诊病历撰写助手。根据对话记录和分诊结论，生成符合规范的 SOAP 四段式病历。\n\n"
        f"患者主诉：{state.get('chief_complaint', '')}\n\n"
        f"对话历史：\n{history}\n\n"
        f"已采集医学信息：{json.dumps(entities, ensure_ascii=False)}\n\n"
        f"分诊建议科室：\n{dept_lines}\n\n"
        "按要求输出四段：\n"
        "1. subjective（S 主观资料）：主诉、现病史、既往史、过敏史，仅写患者已陈述的内容\n"
        "2. objective（O 客观资料）：已采集的客观体征；预问诊阶段缺失时写「无」，不得编造\n"
        "3. assessment（A 评估）：鉴别方向，面向医生，可含疾病方向的推测，仅医生端可见\n"
        "4. plan（P 计划）：建议就诊科室、建议补充检查；【严禁】出现任何用药建议\n"
        "5. completeness_rate：字段完整率 0~1（关键字段缺失则降低）\n\n"
        "铁律：不编造患者未提及的症状、体征、病史；不输出任何用药建议。"
    )


def build_emr_writer_node(client: ModelClient):
    """构造 SOAP 病历生成节点。"""

    async def emr_writer_node(state: TriageState) -> dict:
        session_id = state.get("session_id", "")
        events.emit_node_start(
            session_id, events.NODE_EMR_GENERATE, "病历生成", "正在整理预问诊病历"
        )
        prompt = _build_prompt(state)
        try:
            reply = await client.chat(
                [{"role": "user", "content": prompt}],
                small=False,
                json_schema=_SOAP_SCHEMA,
                capability="llm_chat",
            )
            result = json.loads(reply)
        except Exception as exc:
            logger.warning("SOAP 病历生成失败: %s", exc)
            # 降级：PARTIAL，保留已采集的结构化信息，不伪造
            entities = state.get("entities", {})
            events.emit_node_complete(
                session_id, events.NODE_EMR_GENERATE, {"generate_status": "FAILED"}
            )
            return {
                "emr": {
                    "subjective": state.get("chief_complaint", ""),
                    "objective": "",
                    "assessment": "",
                    "plan": "",
                    "generate_status": "FAILED",
                    "completeness_rate": 0.0,
                    "entities": entities,
                }
            }

        # 检查 P 段是否误含用药建议（简单关键词兜底）
        plan = result.get("plan", "")
        drug_hints = ("用药", "服用", "处方", "mg", "片", "口服", "静脉", "注射")
        if any(k in plan for k in drug_hints):
            logger.warning("SOAP P 段疑似含用药建议，已剔除")
            result["plan"] = "建议就诊科室进一步评估，用药方案由接诊医生根据面诊结果制定。"

        emr = {
            "subjective": result.get("subjective", ""),
            "objective": result.get("objective", ""),
            "assessment": result.get("assessment", ""),
            "plan": result["plan"],
            "generate_status": "SUCCESS",
            "completeness_rate": result.get("completeness_rate", 1.0),
        }
        events.emit_node_complete(
            session_id,
            events.NODE_EMR_GENERATE,
            {"generate_status": "SUCCESS", "completeness_rate": emr["completeness_rate"]},
        )
        return {"emr": emr}

    return emr_writer_node
