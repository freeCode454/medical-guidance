"""危重症三层识别节点（F50）。

第一层：确定性规则匹配（关键词），不依赖任何外部服务——
模型服务全挂时依然生效。命中即中断问诊，路由置 EMERGENCY。

三层递进（当前实现第一层，二三层留待接入小模型/大模型判定）：
1. 规则层：关键词命中（本节）
2. 小模型层：意图识别模型二次确认
3. 大模型层：完整语义判定
"""
from __future__ import annotations

import re

from app.agents.state import TriageState
from app.ws import events

# 急诊红线关键词（保守：宁可误拦不可漏拦）
_EMERGENCY_PATTERNS = [
    r"剧烈胸痛", r"压榨性胸痛", r"胸痛伴(有)?出汗", r"胸痛伴(有)?放射",
    r"呼吸困难", r"喘不上气", r"窒息",
    r"昏迷", r"意识丧失", r"晕厥", r"抽搐",
    r"大出血", r"呕血", r"咯血", r"大量便血",
    r"心梗", r"心搏骤停", r"休克", r"濒死感",
    r"高热惊厥", r"剧烈头痛伴(有)?呕吐",
]

_compiled = [re.compile(p) for p in _EMERGENCY_PATTERNS]


def detect_emergency(text: str) -> bool:
    """规则层判定：文本是否命中危重症红线。"""
    if not text:
        return False
    return any(p.search(text) for p in _compiled)


def safety_node(state: TriageState) -> dict:
    """危重症拦截节点。命中则置 EMERGENCY 并中断。"""
    session_id = state.get("session_id", "")
    events.emit_node_start(
        session_id, events.NODE_SAFETY, "危重症识别", "正在评估症状紧急程度"
    )

    text = state.get("chief_complaint", "")
    hit = detect_emergency(text)
    if hit:
        events.emit_emergency(
            session_id,
            "胸痛/呼吸困难/昏迷/大出血等危重症红线关键词",
            "您的症状需要立即就医，请立即前往就近医院急诊科",
        )
        events.emit_node_complete(
            session_id, events.NODE_SAFETY, {"matched": True}
        )
        return {"risk_flag": True, "route": "EMERGENCY"}

    events.emit_node_complete(session_id, events.NODE_SAFETY, {"matched": False})
    return {"risk_flag": False}
