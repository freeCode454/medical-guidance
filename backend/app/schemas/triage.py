"""分诊结果相关 schema：对应 04 文档 12.3 节。

关键约束（R01 / R02）：
    - 患者视图的响应中不得出现任何疾病名称（仅科室）
    - 鉴别诊断候选与判断依据仅医生端可见，不在本 schema 中出现
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.common.enums import TriageRoute


class RecommendedDept(BaseModel):
    """建议科室。"""

    dept_code: str = Field(description="科室编码")
    dept_name: str = Field(description="科室名称")
    confidence: float = Field(ge=0, le=1, description="置信度")
    is_primary: bool = Field(description="是否为首要推荐科室")


class SymptomSummary(BaseModel):
    """已收集的症状摘要，字段随采集情况可能为 null。"""

    chief_complaint: str | None = Field(default=None, description="主诉")
    duration: str | None = Field(default=None, description="发病时长")
    location: str | None = Field(default=None, description="部位")
    nature: str | None = Field(default=None, description="性质")
    accompanying: list[str] | None = Field(default=None, description="伴随症状")
    past_history: list[str] | None = Field(default=None, description="既往史")
    allergy: list[str] | None = Field(default=None, description="过敏史")


class EmergencyGuidance(BaseModel):
    """危重症引导信息（F11），仅 route=EMERGENCY 时非空。"""

    triggered: bool = Field(description="是否已触发急诊通道")
    reason: str = Field(description="触发原因描述，不得出现疾病名称")
    advice: str = Field(description="就医引导文案")
    emergency_phone: str = Field(default="120", description="急救电话")
    recommended_dept: str = Field(description="建议直接前往的科室")


class TriageResultResponse(BaseModel):
    """分诊结果响应（患者视图）。"""

    triage_result_id: str = Field(description="分诊结论标识")
    route: TriageRoute = Field(description="路由去向")
    confidence: float = Field(ge=0, le=1, description="整体置信度")
    recommended_depts: list[RecommendedDept] = Field(default_factory=list, description="建议科室列表")
    symptom_summary: SymptomSummary = Field(description="症状摘要")
    inquiry_rounds: int = Field(description="已追问轮次")
    emergency_guidance: EmergencyGuidance | None = Field(
        default=None, description="危重症引导信息，仅 route=EMERGENCY 时非空"
    )
    disclaimer: str = Field(description="免责声明文本，客户端须完整展示")
    generated_time: datetime = Field(description="结论生成时间")
