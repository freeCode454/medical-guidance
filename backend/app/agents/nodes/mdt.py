"""MDT 多学科会诊节点（F35）。

三节点协同（fan-out → 专科角色 → fan-in 汇总）：

1. ``mdt_fanout``：根据候选科室，用 ``Send`` API 并行唤起多个专科角色
2. ``mdt_specialist``：单个专科角色独立判断（倾向 / 依据 / 建议科室 / 置信度）
3. ``mdt_aggregate``：汇总各专科意见，投票得出共识科室，分歧点显式保留

设计要点（对齐《02 架构》§6.4 与《03 数据库》mg_mdt_council）：

- 并行度：Send 同时发起，总耗时取决于最慢角色（AC-F35-1）
- 分歧必须显式输出，不得在汇总时抹平（AC-F35-2）
- 个别角色失败时以其余角色汇总，缺失数量显式记录（AC-F35-3）
- 专科意见含医学判断依据，**仅医生端可见**，不向患者端输出疾病名称（R01）
"""
from __future__ import annotations

import json
import logging
from collections import Counter

from langgraph.types import Send

from app.agents.state import TriageState
from app.common.llm_client import ModelClient

logger = logging.getLogger(__name__)

# 专科角色判断的结构化输出约束
_SPECIALIST_SCHEMA = {
    "name": "mdt_specialist",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "leaning": {"type": "string", "enum": ["SUPPORT", "AGAINST"]},
            "rationale": {"type": "string"},
            "suggested_dept": {"type": "string"},
            "confidence": {"type": "number"},
        },
        "required": ["leaning", "rationale", "suggested_dept", "confidence"],
        "additionalProperties": False,
    },
}


def _build_specialist_prompt(state: TriageState) -> str:
    messages = state.get("messages", [])
    history = "\n".join(f"{m.get('role')}: {m.get('content')}" for m in messages)
    entities = state.get("entities", {})
    dept_name = state.get("specialist_dept_name", "") or state.get("specialist_dept", "")
    # 会诊参与科室清单（供专科角色约束建议范围）
    depts = [d for d in state.get("triage_result", {}).get("recommended_depts", [])]
    dept_lines = "\n".join(
        f"- {d.get('dept_code')} {d.get('dept_name', '')}" for d in depts
    )
    return (
        f"你是{dept_name}的专科医生，正在参加一次多学科会诊（MDT）。\n\n"
        f"患者主诉：{state.get('chief_complaint', '')}\n\n"
        f"对话历史：\n{history}\n\n"
        f"已采集信息：{json.dumps(entities, ensure_ascii=False)}\n\n"
        f"会诊参与科室：\n{dept_lines}\n\n"
        f"请从{dept_name}的专业角度独立判断这位患者是否属于你的专科范畴：\n"
        "1. leaning：SUPPORT（支持收入本科）/ AGAINST（不建议本科）\n"
        "2. rationale：判断依据（医学理由，仅医生端可见，不得含糊）\n"
        "3. suggested_dept：你建议的就诊科室编码，必须取自上述会诊参与科室列表，不得编造\n"
        "4. confidence：置信度 0~1\n\n"
        "要求：不得输出具体疾病诊断名称。"
    )


def build_mdt_fanout_node():
    """构造 MDT 分发节点：按候选科室并行唤起专科角色。"""

    def mdt_fanout(state: TriageState) -> list[Send]:
        triage = state.get("triage_result", {})
        depts = triage.get("recommended_depts", [])
        if not depts:
            # 无候选科室：直接跳过会诊（走汇总，产生空结果）
            return []
        sends = [
            Send(
                "mdt_specialist",
                {
                    "specialist_dept": d.get("dept_code", ""),
                    "specialist_dept_name": d.get("dept_name", ""),
                },
            )
            for d in depts
        ]
        logger.info("MDT 分发 %d 个专科角色：%s", len(sends), [d.get("dept_code") for d in depts])
        return sends

    return mdt_fanout


def build_mdt_specialist_node(client: ModelClient):
    """构造单专科角色节点（并行执行，独立判断）。"""

    async def mdt_specialist(state: TriageState) -> dict:
        dept_code = state.get("specialist_dept", "")
        dept_name = state.get("specialist_dept_name", "")
        prompt = _build_specialist_prompt(state)
        try:
            reply = await client.chat(
                [{"role": "user", "content": prompt}],
                small=False,
                json_schema=_SPECIALIST_SCHEMA,
                capability="llm_chat",
            )
            result = json.loads(reply)
        except Exception as exc:  # 个别角色失败：记录缺失，不阻断整体（AC-F35-3）
            logger.warning("MDT 专科角色 %s 判断失败: %s", dept_code, exc)
            return {"mdt_opinions": [{"dept_code": dept_code, "error": str(exc)[:120]}]}

        opinion = {
            "dept_code": dept_code,
            "dept_name": dept_name,
            "leaning": result.get("leaning"),
            "rationale": result.get("rationale", ""),
            "suggested_dept": result.get("suggested_dept", ""),
            "confidence": result.get("confidence", 0.0),
        }
        return {"mdt_opinions": [opinion]}

    return mdt_specialist


def _aggregate(opinions: list[dict]) -> dict:
    """汇总各专科意见（纯代码投票，不额外调 LLM，结果可复现）。

    返回：{"consensus_dept", "consensus_confidence", "divergence_flag",
           "divergence_json", "missing_count", "opinions"}
    """
    valid = [o for o in opinions if "error" not in o]
    missing = len(opinions) - len(valid)

    if not valid:
        return {
            "consensus_dept": None,
            "consensus_confidence": 0.0,
            "divergence_flag": False,
            "divergence_json": None,
            "missing_count": missing,
            "opinions": opinions,
        }

    # 投票：按建议科室计票
    votes: Counter = Counter(o.get("suggested_dept", "") for o in valid)
    top_dept, top_count = votes.most_common(1)[0]

    # 综合置信度 = 得票最多科室的平均置信度
    confs = [o.get("confidence", 0.0) for o in valid if o.get("suggested_dept") == top_dept]
    consensus_confidence = sum(confs) / len(confs) if confs else 0.0

    # 分歧判定：各专科建议科室不一致（有人建议了非共识科室）。
    # leaning=AGAINST 但建议科室一致不算分歧——例如「心内科医生不建议心内、建议消化内科」
    # 与其他角色最终一致。立场信息保留在 opinions 里供医生参考。
    suggested = [o.get("suggested_dept", "") for o in valid]
    divergence = len(set(suggested)) > 1

    divergence_json = None
    if divergence:
        # 少数派（建议非共识科室的角色）作为分歧点显式保留
        minority = [
            {
                "dept_code": o.get("dept_code"),
                "dept_name": o.get("dept_name", ""),
                "suggested_dept": o.get("suggested_dept"),
                "rationale": o.get("rationale"),
            }
            for o in valid
            if o.get("suggested_dept") != top_dept
        ]
        divergence_json = {
            "vote_distribution": dict(votes),
            "minority_opinions": minority,
        }

    return {
        "consensus_dept": top_dept,
        "consensus_confidence": round(consensus_confidence, 4),
        "divergence_flag": divergence,
        "divergence_json": divergence_json,
        "missing_count": missing,
        "opinions": opinions,
    }


def build_mdt_aggregate_node():
    """构造 MDT 汇总节点（fan-in）：投票共识 + 分歧保留 + 更新分诊结论。"""

    async def mdt_aggregate(state: TriageState) -> dict:
        opinions = state.get("mdt_opinions", [])
        result = _aggregate(opinions)

        # 更新分诊结论：共识科室提到首位；分歧信息写入医生端视图
        triage = dict(state.get("triage_result", {}))
        consensus_dept = result["consensus_dept"]
        depts = triage.get("recommended_depts", [])
        if consensus_dept and depts:
            ordered = sorted(
                depts, key=lambda d: 0 if d.get("dept_code") == consensus_dept else 1
            )
            triage["recommended_depts"] = ordered
            # 标记会诊结论（医生端可见分歧区块）
            triage["mdt"] = {
                "consensus_dept": consensus_dept,
                "consensus_confidence": result["consensus_confidence"],
                "divergence_flag": result["divergence_flag"],
                "divergence": result["divergence_json"],
                "missing_count": result["missing_count"],
                "opinions": result["opinions"],
            }
            # 若存在分歧，route 保持 MDT 让医生关注；无分歧则收敛为 DIRECT
            if not result["divergence_flag"]:
                triage["route"] = "DIRECT"

        return {
            "mdt_result": result,
            "triage_result": triage,
            "route": triage.get("route", state.get("route")),
        }

    return mdt_aggregate
