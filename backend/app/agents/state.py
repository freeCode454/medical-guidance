"""编排层共享状态（核心契约）。

各图节点通过本状态通信，不得绕过。归并方式（对齐《02 架构》§5.2.1）：
- 追加（operator.add）：对话记录
- 合并（自定义 reducer）：医学实体、信息槽位、已问项
- 覆盖（默认）：串行决策点（充分度、路由、风险等级等）

⚠️ MDT 并行会诊时，多个专科角色同时写状态，追加/合并保证不互相覆盖。
"""
from __future__ import annotations

import operator
from typing import Annotated, TypedDict


def _merge_dict(left: dict, right: dict) -> dict:
    """合并字典：右侧覆盖同键（用于医学实体、信息槽位的增量更新）。"""
    merged = dict(left or {})
    merged.update(right or {})
    return merged


def _merge_list(left: list, right: list) -> list:
    """合并列表并去重（用于已问项）。"""
    seen = set(left or [])
    out = list(left or [])
    for item in right or []:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


class TriageState(TypedDict, total=False):
    # ---- 服务端注入（覆盖） ----
    session_id: str
    tenant_id: str
    patient_hash: str | None
    gender: str  # 男 / 女（供分诊规则人群过滤）
    age: int  # 年龄（供儿童/老年科室过滤）

    # ---- 对话（追加） ----
    chief_complaint: str
    messages: Annotated[list[dict], operator.add]

    # ---- 医学信息（合并） ----
    entities: Annotated[dict, _merge_dict]  # duration/location/nature/accompanying/past_history/allergy

    # ---- 澄清追问（合并） ----
    asked: Annotated[list, _merge_list]  # 已问过的信息项
    # 当前挂起的问题：_after_run 在 interrupt 时写入。LangGraph resume 会重放
    # 整个节点，重放时从这里读问题（而不是重新生成），保证与 resume 值配对。
    pending_question: str
    inquiry_rounds: int

    # ---- 决策点（覆盖） ----
    sufficient: bool  # 信息是否充分
    route: str  # DIRECT / MDT / MANUAL / EMERGENCY
    risk_flag: bool  # 是否命中危重症红线
    candidate_depts: list[dict]  # 候选科室召回结果
    triage_result: dict  # 分诊结论

    # ---- MDT 会诊（fan-out / fan-in） ----
    specialist_dept: str  # 当前专科角色科室编码（Send 分支覆盖）
    specialist_dept_name: str  # 当前专科角色科室名称
    mdt_opinions: Annotated[list[dict], operator.add]  # 各专科意见（并行追加）
    mdt_result: dict  # 会诊汇总结果（共识 + 分歧）

    # ---- 输出（覆盖） ----
    emr: dict  # SOAP 病历
