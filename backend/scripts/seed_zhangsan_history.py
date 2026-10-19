"""为演示患者 zhangsan 生成 3 年门诊历史（一次性种子脚本）。

只写数据：患者画像、历史会话/消息、分诊记录、SOAP 病历、病历文书、就诊预约、EMR_READ 授权。
不修改任何业务代码。
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.common.database import AsyncSessionFactory
from app.models import (
    Appointment,
    EmrDocument,
    EmrRecord,
    Patient,
    PatientConsent,
    Session,
    SessionMessage,
    TriageResult,
)

SH = ZoneInfo("Asia/Shanghai")
TENANT = "00000000000000000000000000000001"
PATIENT_ACCOUNT = "zhangsan"

VISITS = [
    {
        "session_no": "HIS-ZS-20230512",
        "date": datetime(2023, 5, 12, 9, 0, tzinfo=SH),
        "dept": "RES",
        "doctor": "cc73751d3dbf4558bd8bfb454b42025e",
        "complaint": "发热、咳嗽3天",
        "soap": {
            "subjective": (
                "主诉：发热、咳嗽3天。现病史：3天前受凉后出现发热，体温最高38.5℃，"
                "伴咽痛、乏力、少量白痰，无呼吸困难、胸痛。既往史：既往体健。"
                "过敏史：否认药物过敏。"
            ),
            "objective": "体温38.2℃，咽部充血，双肺呼吸音清，未闻及干湿性啰音。",
            "assessment": "急性上呼吸道感染（病毒性可能大）。",
            "plan": "建议呼吸内科就诊；休息、多饮水，必要时对症处理；持续高热或呼吸困难及时复诊。",
            "entities": {
                "duration": "3天",
                "location": "咽部",
                "nature": "发热、咳嗽",
                "accompanying": ["咽痛", "乏力"],
                "past_history": [],
                "allergy": [],
            },
        },
        "icd10": ["J06.9"],
        "answer": "没有呼吸困难，体温最高38.5℃",
        "question": "有没有呼吸困难或胸痛？",
        "doc_title": "呼吸内科门诊病历",
        "doc_type": "OUTPATIENT",
        "doc_content": (
            "主诉：发热、咳嗽3天。现病史：受凉后发热，最高38.5℃，伴咽痛、乏力、少量白痰。"
            "查体：体温38.2℃，咽充血，双肺呼吸音清。诊断：急性上呼吸道感染。"
            "处理：休息、多饮水，必要时对症处理，持续高热或呼吸困难复诊。"
        ),
        "section_json": {
            "主诉": "发热、咳嗽3天",
            "查体": "体温38.2℃，咽充血，双肺呼吸音清",
            "诊断": "急性上呼吸道感染",
            "处理": "休息、补液，必要时对症处理",
        },
    },
    {
        "session_no": "HIS-ZS-20231103",
        "date": datetime(2023, 11, 3, 14, 30, tzinfo=SH),
        "dept": "DIG",
        "doctor": "42b442394c404d2f99187731f6a75694",
        "complaint": "腹痛、腹泻1天",
        "soap": {
            "subjective": (
                "主诉：腹痛、腹泻1天。现病史：昨日进食外卖后出现脐周阵发性腹痛，"
                "腹泻4次，为稀水样便，无发热、无血便、无呕吐。既往史：既往体健。"
                "过敏史：否认药物过敏。"
            ),
            "objective": "腹软，脐周轻压痛，无反跳痛，肠鸣音活跃。",
            "assessment": "急性胃肠炎（感染性可能大）。",
            "plan": "建议消化内科就诊；清淡饮食、补液；出现血便、持续呕吐或高热及时急诊。",
            "entities": {
                "duration": "1天",
                "location": "脐周",
                "nature": "阵发性腹痛",
                "accompanying": ["腹泻", "稀水样便"],
                "past_history": [],
                "allergy": [],
            },
        },
        "icd10": ["K52.9"],
        "answer": "没有发热，也没有血便",
        "question": "有没有发热、呕吐或血便？",
        "doc_title": "消化内科门诊病历",
        "doc_type": "OUTPATIENT",
        "doc_content": (
            "主诉：腹痛、腹泻1天。现病史：不洁饮食后脐周阵发性腹痛，腹泻4次，稀水样便，"
            "无发热、血便、呕吐。查体：腹软，脐周轻压痛，无反跳痛。诊断：急性胃肠炎。"
            "处理：清淡饮食、补液，出现血便/持续呕吐/高热及时急诊。"
        ),
        "section_json": {
            "主诉": "腹痛、腹泻1天",
            "查体": "腹软，脐周轻压痛，无反跳痛",
            "诊断": "急性胃肠炎",
            "处理": "清淡饮食、补液，警惕脱水",
        },
    },
    {
        "session_no": "HIS-ZS-20240318",
        "date": datetime(2024, 3, 18, 10, 0, tzinfo=SH),
        "dept": "ORT",
        "doctor": "7cafb99ab4534425ab54c952aa7ed74a",
        "complaint": "右踝扭伤2天",
        "soap": {
            "subjective": (
                "主诉：右踝扭伤2天。现病史：跑步时扭伤右踝，局部肿胀、疼痛，行走受限，"
                "无畸形、无麻木。既往史：既往体健。过敏史：否认药物过敏。"
            ),
            "objective": "右踝外侧肿胀、压痛，活动受限，末梢血运及感觉正常。",
            "assessment": "右踝关节扭伤，需排除韧带损伤或骨折。",
            "plan": "建议骨科就诊；制动、冰敷、抬高患肢，必要时行踝关节影像学检查。",
            "entities": {
                "duration": "2天",
                "location": "右踝外侧",
                "nature": "扭伤后肿痛",
                "accompanying": ["肿胀", "活动受限"],
                "past_history": [],
                "allergy": [],
            },
        },
        "icd10": ["S93.4"],
        "answer": "没有畸形，也没有麻木",
        "question": "局部有没有明显畸形或麻木？",
        "doc_title": "骨科门诊病历",
        "doc_type": "OUTPATIENT",
        "doc_content": (
            "主诉：右踝扭伤2天。现病史：跑步扭伤右踝，局部肿胀疼痛、行走受限，无畸形麻木。"
            "查体：右踝外侧肿胀压痛，活动受限，末梢血运感觉正常。诊断：右踝关节扭伤。"
            "处理：制动、冰敷、抬高患肢，必要时影像学检查。"
        ),
        "section_json": {
            "主诉": "右踝扭伤2天",
            "查体": "右踝外侧肿胀压痛，活动受限",
            "诊断": "右踝关节扭伤",
            "处理": "制动、冰敷、抬高患肢",
        },
    },
    {
        "session_no": "HIS-ZS-20240907",
        "date": datetime(2024, 9, 7, 16, 0, tzinfo=SH),
        "dept": "DERM",
        "doctor": "4f1b7709ab154cbca98c382793dfe3b4",
        "complaint": "全身皮疹1天",
        "soap": {
            "subjective": (
                "主诉：全身皮疹1天。现病史：因咽痛自行服用青霉素后出现躯干、四肢红色皮疹，"
                "伴瘙痒，无呼吸困难、无喉头紧缩感。既往史：过敏性鼻炎。"
                "过敏史：青霉素过敏（本次皮疹考虑相关）。"
            ),
            "objective": "躯干及四肢散在红色斑丘疹，压之褪色，未见水疱、剥脱，呼吸平稳。",
            "assessment": "药物性皮炎（青霉素相关）可能性大。",
            "plan": "立即停用可疑药物，皮肤科就诊；如出现呼吸困难、喉头水肿或皮疹迅速加重，立即急诊。",
            "entities": {
                "duration": "1天",
                "location": "躯干、四肢",
                "nature": "红色斑丘疹、瘙痒",
                "accompanying": ["瘙痒"],
                "past_history": ["过敏性鼻炎"],
                "allergy": ["青霉素"],
            },
        },
        "icd10": ["L27.0"],
        "answer": "没有呼吸困难，也没有喉咙发紧",
        "question": "有没有呼吸困难或喉头紧缩感？",
        "doc_title": "皮肤科门诊病历",
        "doc_type": "OUTPATIENT",
        "doc_content": (
            "主诉：全身皮疹1天。现病史：服用青霉素后躯干四肢出现红色皮疹，伴瘙痒，"
            "无呼吸困难、喉头紧缩感。既往史：过敏性鼻炎。过敏史：青霉素。"
            "查体：躯干四肢散在红色斑丘疹，压之褪色，呼吸平稳。"
            "诊断：药物性皮炎（青霉素相关）。处理：停用可疑药物，皮肤科随诊，警惕喉头水肿。"
        ),
        "section_json": {
            "主诉": "全身皮疹1天",
            "过敏史": "青霉素过敏",
            "诊断": "药物性皮炎（青霉素相关）",
            "处理": "停用可疑药物，警惕呼吸困难",
        },
    },
    {
        "session_no": "HIS-ZS-20250214",
        "date": datetime(2025, 2, 14, 9, 30, tzinfo=SH),
        "dept": "RES",
        "doctor": "cc73751d3dbf4558bd8bfb454b42025e",
        "complaint": "咳嗽2周",
        "soap": {
            "subjective": (
                "主诉：咳嗽2周。现病史：2周前感冒后咳嗽，晨起及夜间明显，少量白痰，"
                "无发热、无咯血、无呼吸困难。既往史：过敏性鼻炎；青霉素过敏。"
                "过敏史：青霉素。"
            ),
            "objective": "咽部轻充血，双肺呼吸音粗，未闻及明显干湿性啰音。",
            "assessment": "急性支气管炎。",
            "plan": "建议呼吸内科就诊；必要时胸片检查，避免烟雾刺激，持续咳嗽或咯血复诊。",
            "entities": {
                "duration": "2周",
                "location": "咽部、支气管",
                "nature": "咳嗽、少量白痰",
                "accompanying": ["晨起咳嗽", "夜间咳嗽"],
                "past_history": ["过敏性鼻炎"],
                "allergy": ["青霉素"],
            },
        },
        "icd10": ["J20.9"],
        "answer": "没有发热，也没有咯血",
        "question": "有没有发热、咯血或呼吸困难？",
        "doc_title": "呼吸内科门诊病历",
        "doc_type": "OUTPATIENT",
        "doc_content": (
            "主诉：咳嗽2周。现病史：感冒后咳嗽，晨起及夜间明显，少量白痰，无发热、咯血、"
            "呼吸困难。既往史：过敏性鼻炎；青霉素过敏。查体：咽轻充血，双肺呼吸音粗。"
            "诊断：急性支气管炎。处理：避免烟雾刺激，必要时胸片，持续咳嗽或咯血复诊。"
        ),
        "section_json": {
            "主诉": "咳嗽2周",
            "查体": "双肺呼吸音粗",
            "诊断": "急性支气管炎",
            "处理": "避免烟雾刺激，必要时胸片",
        },
    },
    {
        "session_no": "HIS-ZS-20250822",
        "date": datetime(2025, 8, 22, 10, 30, tzinfo=SH),
        "dept": "DIG",
        "doctor": "42b442394c404d2f99187731f6a75694",
        "complaint": "上腹隐痛1月",
        "soap": {
            "subjective": (
                "主诉：上腹隐痛1月，加重3天。现病史：餐后上腹隐痛，伴反酸、嗳气，"
                "无黑便、无呕血、无体重明显下降。既往史：过敏性鼻炎；青霉素过敏。"
                "过敏史：青霉素。"
            ),
            "objective": "上腹轻压痛，无反跳痛，肝脾未触及。",
            "assessment": "慢性胃炎，需胃镜进一步评估。",
            "plan": "建议消化内科就诊，完善胃镜检查；规律饮食，避免辛辣刺激，出现黑便/呕血急诊。",
            "entities": {
                "duration": "1月",
                "location": "上腹",
                "nature": "隐痛、反酸",
                "accompanying": ["嗳气", "餐后加重"],
                "past_history": ["过敏性鼻炎"],
                "allergy": ["青霉素"],
            },
        },
        "icd10": ["K29.7"],
        "answer": "没有黑便，也没有呕血",
        "question": "有没有黑便、呕血或体重明显下降？",
        "doc_title": "胃镜检查报告",
        "doc_type": "OUTPATIENT",
        "doc_content": (
            "检查：胃镜示胃窦黏膜轻度充血水肿，未见溃疡及占位；幽门螺杆菌检测阴性。"
            "诊断：慢性非萎缩性胃炎。建议：规律饮食，避免辛辣刺激，消化内科随诊。"
        ),
        "section_json": {
            "检查": "胃窦黏膜轻度充血水肿，HP阴性",
            "诊断": "慢性非萎缩性胃炎",
            "建议": "规律饮食，消化内科随诊",
        },
    },
    {
        "session_no": "HIS-ZS-20260109",
        "date": datetime(2026, 1, 9, 15, 0, tzinfo=SH),
        "dept": "ENT",
        "doctor": "43fc3397729643cf8d7eb874719d1692",
        "complaint": "鼻塞、打喷嚏1周",
        "soap": {
            "subjective": (
                "主诉：鼻塞、打喷嚏1周。现病史：接触冷空气后鼻痒、连续打喷嚏、清水样涕，"
                "无发热、无脓涕、无面部胀痛。既往史：过敏性鼻炎；慢性胃炎；青霉素过敏。"
                "过敏史：青霉素；可疑尘螨/花粉过敏。"
            ),
            "objective": "鼻黏膜苍白水肿，双下鼻甲肿大，咽部无充血。",
            "assessment": "过敏性鼻炎（间歇性）。",
            "plan": "建议耳鼻喉科就诊；避免过敏原、生理盐水鼻冲洗，症状加重或伴哮喘样症状复诊。",
            "entities": {
                "duration": "1周",
                "location": "鼻腔",
                "nature": "鼻痒、打喷嚏、清水样涕",
                "accompanying": ["鼻塞"],
                "past_history": ["过敏性鼻炎", "慢性胃炎"],
                "allergy": ["青霉素"],
            },
        },
        "icd10": ["J30.4"],
        "answer": "没有发热，也没有脓涕",
        "question": "有没有发热、脓涕或面部胀痛？",
        "doc_title": "耳鼻喉科门诊病历",
        "doc_type": "OUTPATIENT",
        "doc_content": (
            "主诉：鼻塞、打喷嚏1周。现病史：接触冷空气后鼻痒、连续打喷嚏、清水样涕，"
            "无发热、脓涕、面部胀痛。既往史：过敏性鼻炎、慢性胃炎；青霉素过敏。"
            "查体：鼻黏膜苍白水肿，双下鼻甲肿大。诊断：过敏性鼻炎。"
            "处理：避免过敏原，生理盐水鼻冲洗，耳鼻喉科随诊。"
        ),
        "section_json": {
            "主诉": "鼻塞、打喷嚏1周",
            "查体": "鼻黏膜苍白水肿，双下鼻甲肿大",
            "诊断": "过敏性鼻炎",
            "处理": "避免过敏原，鼻冲洗",
        },
    },
    {
        "session_no": "HIS-ZS-20260615",
        "date": datetime(2026, 6, 15, 8, 30, tzinfo=SH),
        "dept": "RES",
        "doctor": "cc73751d3dbf4558bd8bfb454b42025e",
        "complaint": "咽痛、发热2天",
        "soap": {
            "subjective": (
                "主诉：咽痛、发热2天。现病史：2天前出现咽痛，体温最高38.0℃，伴乏力，"
                "无咳嗽、无呼吸困难。既往史：过敏性鼻炎；慢性胃炎；青霉素过敏。"
                "过敏史：青霉素。"
            ),
            "objective": "体温38.0℃，咽部充血，双侧扁桃体I度肿大，双肺呼吸音清。",
            "assessment": "急性上呼吸道感染（咽扁桃体炎可能）。",
            "plan": "建议呼吸内科/全科就诊；休息、多饮水，持续高热、吞咽困难或呼吸困难复诊。",
            "entities": {
                "duration": "2天",
                "location": "咽部",
                "nature": "咽痛、发热",
                "accompanying": ["乏力"],
                "past_history": ["过敏性鼻炎", "慢性胃炎"],
                "allergy": ["青霉素"],
            },
        },
        "icd10": ["J06.9"],
        "answer": "没有咳嗽，也没有呼吸困难",
        "question": "有没有咳嗽或呼吸困难？",
        "doc_title": "呼吸内科门诊病历",
        "doc_type": "OUTPATIENT",
        "doc_content": (
            "主诉：咽痛、发热2天。现病史：咽痛，最高38.0℃，伴乏力，无咳嗽、呼吸困难。"
            "既往史：过敏性鼻炎、慢性胃炎；青霉素过敏。查体：咽充血，扁桃体I度肿大，"
            "双肺呼吸音清。诊断：急性上呼吸道感染。处理：休息、补液，持续高热或吞咽困难复诊。"
        ),
        "section_json": {
            "主诉": "咽痛、发热2天",
            "查体": "咽充血，扁桃体I度肿大",
            "诊断": "急性上呼吸道感染",
            "处理": "休息、补液，持续高热复诊",
        },
    },
]

DEPT_NAMES = {
    "RES": "呼吸内科",
    "DIG": "消化内科",
    "ORT": "骨科",
    "DERM": "皮肤科",
    "ENT": "耳鼻喉科",
}


async def main() -> None:
    async with AsyncSessionFactory() as db:
        patient = await db.scalar(
            select(Patient).where(
                Patient.tenant_id == TENANT, Patient.account == PATIENT_ACCOUNT
            )
        )
        if patient is None:
            raise RuntimeError("zhangsan 患者不存在，请先注册")
        existing = await db.scalar(
            select(Session).where(
                Session.tenant_id == TENANT,
                Session.patient_id == patient.id,
                Session.session_no.like("HIS-ZS-%"),
            )
        )
        if existing is not None:
            print("zhangsan 的历史数据已存在，跳过")
            return

        # 患者画像：23 岁男性，院内患者编号，3 年前建档
        patient.age = 23
        patient.gender = "1"
        patient.patient_no = "P20230001"
        patient.create_time = datetime(2023, 4, 1, 8, 0, tzinfo=SH)
        patient.remark = "演示患者：院内 3 年就诊史（2023-2026）"

        for index, visit in enumerate(VISITS):
            visit_time = visit["date"]
            session = Session(
                tenant_id=TENANT,
                session_no=visit["session_no"],
                patient_id=patient.id,
                doctor_id=visit["doctor"],
                dept_code=visit["dept"],
                chief_complaint=visit["complaint"],
                status="FINISHED",
                risk_flag="0",
                inquiry_rounds=2,
                sufficiency_score=0.9,
                started_time=visit_time,
                finished_time=visit_time + timedelta(minutes=20),
                expire_time=visit_time + timedelta(days=1),
                create_time=visit_time,
            )
            db.add(session)
            await db.flush()

            db.add_all(
                [
                    SessionMessage(
                        tenant_id=TENANT,
                        session_id=session.id,
                        seq_no=1,
                        role="PATIENT",
                        content=visit["complaint"],
                        msg_type="TEXT",
                        send_time=visit_time,
                        create_time=visit_time,
                    ),
                    SessionMessage(
                        tenant_id=TENANT,
                        session_id=session.id,
                        seq_no=2,
                        role="AI",
                        content=visit["question"],
                        msg_type="TEXT",
                        send_time=visit_time + timedelta(minutes=2),
                        create_time=visit_time + timedelta(minutes=2),
                    ),
                    SessionMessage(
                        tenant_id=TENANT,
                        session_id=session.id,
                        seq_no=3,
                        role="PATIENT",
                        content=visit["answer"],
                        msg_type="TEXT",
                        send_time=visit_time + timedelta(minutes=4),
                        create_time=visit_time + timedelta(minutes=4),
                    ),
                ]
            )

            dept_name = DEPT_NAMES[visit["dept"]]
            db.add(
                TriageResult(
                    tenant_id=TENANT,
                    session_id=session.id,
                    candidates_json=[
                        {
                            "dept_code": visit["dept"],
                            "dept_name": dept_name,
                            "confidence": 0.92,
                            "is_primary": True,
                        }
                    ],
                    confidence=0.92,
                    route="DIRECT",
                    retrieval_mode="HYBRID",
                    evidence_json={
                        "symptom_summary": {
                            "chief_complaint": visit["complaint"],
                            **visit["soap"]["entities"],
                        },
                        "risk_flag": False,
                        "history_used": False,
                    },
                    doctor_confirmed="1",
                    confirmed_time=visit_time + timedelta(minutes=20),
                    create_time=visit_time + timedelta(minutes=20),
                )
            )

            soap = visit["soap"]
            db.add(
                EmrRecord(
                    tenant_id=TENANT,
                    session_id=session.id,
                    patient_id=patient.id,
                    subjective=soap["subjective"],
                    objective=soap["objective"],
                    assessment=soap["assessment"],
                    plan=soap["plan"],
                    soap_json={
                        "subjective": soap["subjective"],
                        "objective": soap["objective"],
                        "assessment": soap["assessment"],
                        "plan": soap["plan"],
                        "entities": soap["entities"],
                    },
                    schema_version="1.0",
                    completeness_rate=0.9,
                    generate_status="SUCCESS",
                    create_time=visit_time + timedelta(minutes=30),
                )
            )

            db.add(
                EmrDocument(
                    tenant_id=TENANT,
                    patient_id=patient.id,
                    doc_type=visit["doc_type"],
                    doc_title=visit["doc_title"],
                    dept_code=visit["dept"],
                    record_time=visit_time,
                    doc_content=visit["doc_content"],
                    section_json=visit["section_json"],
                    icd10_codes=visit["icd10"],
                    source_system="HIS_SEED",
                    doc_no=f"ZS-{visit['session_no']}",
                    create_time=visit_time + timedelta(minutes=30),
                )
            )

            db.add(
                Appointment(
                    tenant_id=TENANT,
                    appointment_no=f"ZS{visit_time:%Y%m%d}{index + 1:02d}",
                    session_id=session.id,
                    patient_id=patient.id,
                    dept_code=visit["dept"],
                    doctor_id=visit["doctor"],
                    schedule_date=visit_time.date(),
                    time_slot=f"{visit_time:%H:%M}-{visit_time + timedelta(minutes=30):%H:%M}",
                    slot_id=f"seed:{visit['doctor']}:{visit_time:%Y%m%d}:{visit_time:%H%M}",
                    status="COMPLETED",
                    create_time=visit_time,
                )
            )

        # 患者已授权当前问诊读取既往病历
        db.add(
            PatientConsent(
                tenant_id=TENANT,
                patient_id=patient.id,
                session_id=None,
                consent_scope="EMR_READ",
                consent_time=datetime.now(UTC),
                expire_time=datetime.now(UTC) + timedelta(days=365),
                consent_channel="H5",
                create_time=datetime.now(UTC),
            )
        )
        await db.commit()
        print(f"已生成 zhangsan 3 年历史：{len(VISITS)} 次就诊、{len(VISITS)} 份 SOAP、{len(VISITS)} 份文书")


if __name__ == "__main__":
    asyncio.run(main())
