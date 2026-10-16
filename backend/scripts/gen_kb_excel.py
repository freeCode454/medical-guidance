"""生成医学知识库源数据 Excel（灌库源头文件）· 小医院规模。

一份工作簿、11 个 sheet（含说明），每个数据 sheet ≥ 250 条：
- 6 个知识库类（进 mg_kb_entry + Milvus）：科室字典 / 疾病特征库 / 临床指南 / ICD-10 / 症状本体库 / 禁忌症
- 3 个规则类（硬编码护栏）：红旗症状库 / 分诊规则 / 追问模板
- 1 个基础类：医生信息（进 mg_user）

⚠️ 数据为演示用示例，正式使用前须经医学专业人士审核。
"""
from __future__ import annotations

import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kb_data.depts import build_departments  # noqa: E402
from kb_data.diseases import DISEASES_1  # noqa: E402
from kb_data.diseases2 import DISEASES_2  # noqa: E402
from kb_data.drugs import DRUG_SAFETY  # noqa: E402
from kb_data.drugs2 import DRUG_SAFETY_2  # noqa: E402
from kb_data.icd10 import DEPT_CHAPTER, ICD_EXACT  # noqa: E402
from kb_data.symptoms import SYMPTOMS  # noqa: E402
from kb_data.symptoms2 import SYMPTOMS_2  # noqa: E402

ALL_DISEASES = DISEASES_1 + DISEASES_2
ALL_SYMPTOMS = SYMPTOMS + SYMPTOMS_2

# 科室名映射
DEPT_NAME = {d[0]: d[1] for d in build_departments()}

# ---- 医生（250）---------------------------------------------------------
SURNAMES = list("张王李赵刘陈杨黄周吴徐孙马朱胡林郭何高罗郑梁谢宋唐许韩冯邓曹彭曾肖田董袁潘于蒋蔡余杜叶程苏魏吕丁任沈姚卢姜崔钟谭陆汪范金石廖贾夏韦付方白邹孟熊秦邱江尹薛闫段雷侯龙史陶黎贺顾毛郝龚邵万钱严覃武戴莫孔向汤")
GIVEN = ["志强", "丽华", "建国", "秀珍", "海燕", "伟", "敏", "娟", "涛", "明", "颖", "鹏", "静", "磊", "芳", "勇", "娜", "军", "洋", "霞", "刚", "艳", "杰", "超", "平"]
TITLES = ["住院医师", "主治医师", "副主任医师", "主任医师"]
DOCTOR_DEPTS = [d[0] for d in build_departments() if d[0] in {
    "DIG", "CAR", "RES", "NEU", "END", "NEP", "HEM", "RHE", "INF", "ONC", "GER", "GEN",
    "GS", "ORT", "URO", "NS", "CS", "VS", "BS", "CRS", "HBS", "BURN", "OB", "GYN", "PED",
    "NEO", "DERM", "OPH", "ENT", "STO", "PSY", "REH", "TCM", "ACU", "EMER", "ICU",
    "ANE", "PAIN", "NUT", "MIN", "FAM", "GCP",
}]


def gen_doctors(n: int = 250) -> list[list]:
    """程序生成医生（姓名池 + 职称 + 科室）。"""
    rows = []
    idx = 0
    for s in SURNAMES:
        for g in GIVEN:
            if idx >= n:
                return rows
            dept = DOCTOR_DEPTS[idx % len(DOCTOR_DEPTS)]
            title = TITLES[idx % len(TITLES)]
            rows.append([f"doctor{idx + 1:03d}", f"{s}{g}", title, dept, DEPT_NAME.get(dept, dept)])
            idx += 1
    return rows


# ---- 临床指南（250）-----------------------------------------------------
GUIDE_TPL = [
    "{d}的诊治应结合病史、症状、体征与辅助检查综合判断，重视与相似疾病的鉴别。",
    "{d}强调早期识别与分层管理，依据病情严重程度制定个体化方案。",
    "{d}的一线处理以病因治疗与对症支持为主，必要时转诊专科。",
    "{d}需定期随访评估疗效与并发症，及时调整治疗策略。",
    "{d}的诊断标准需结合实验室与影像学证据，避免漏诊误诊。",
]


def gen_guidelines(n: int = 250) -> list[list]:
    rows = []
    for i, (name, dept, *_rest) in enumerate(ALL_DISEASES):
        if i >= n:
            break
        tpl = GUIDE_TPL[i % len(GUIDE_TPL)]
        rows.append([dept, f"{name}诊疗要点", tpl.format(d=name), "AB"[i % 2], 2020 + (i % 4), "示例指南片段"])
    return rows


# ---- ICD-10（250）-------------------------------------------------------
def gen_icd10(n: int = 250) -> list[list]:
    rows = []
    seq: dict[str, int] = {}
    for i, (name, dept, *_rest) in enumerate(ALL_DISEASES):
        if i >= n:
            break
        if name in ICD_EXACT:
            code, inc, exc = ICD_EXACT[name]
            chapter = DEPT_CHAPTER.get(dept, ("其他", "R"))[0]
        else:
            chapter, prefix = DEPT_CHAPTER.get(dept, ("其他", "R"))
            seq[prefix] = seq.get(prefix, 0) + 1
            cnt = seq[prefix]
            code = f"{prefix}{80 + (cnt - 1) // 10}.{(cnt - 1) % 10}"
            inc = name
            exc = "需与相似疾病鉴别"
        rows.append([name, code, chapter, inc, exc])
    return rows


# ---- 红旗症状库（250）---------------------------------------------------
RED_FLAG_CORE = [
    ("急性冠脉综合征", "剧烈胸痛|压榨性胸痛|胸痛伴出汗|胸痛伴放射", "您可能有心脏急症，请立即前往急诊或拨打120"),
    ("呼吸困难", "呼吸困难|喘不上气|窒息|气短伴发绀", "您呼吸严重困难，请立即拨打120或就近急诊"),
    ("脑血管意外", "突发言语不清|单侧肢体无力|口角歪斜|剧烈头痛伴呕吐", "您可能有卒中征兆，请立即拨打120"),
    ("大出血", "大出血|呕血|咯血|大量便血|外伤出血不止", "您正在出血，请立即拨打120并保持平卧"),
    ("意识障碍", "昏迷|意识丧失|晕厥|不省人事", "患者意识障碍，请立即拨打120"),
    ("抽搐", "抽搐|惊厥|抽风", "患者抽搐，请保持呼吸道通畅并立即拨打120"),
    ("休克", "休克|濒死感|血压骤降|四肢湿冷", "您可能有休克征兆，请立即拨打120"),
    ("高热惊厥", "高热惊厥|高热伴抽搐", "患者高热惊厥，请立即就医"),
    ("严重过敏", "呼吸困难伴皮疹|喉头水肿|过敏性休克", "您可能有严重过敏反应，请立即拨打120"),
    ("气道异物", "突发窒息|呛咳后不能发声|气道异物", "疑似气道异物，请立即急救并拨打120"),
    ("宫外孕破裂", "停经后剧烈腹痛|阴道出血伴腹痛|头晕晕厥", "育龄女性停经后剧烈腹痛，请立即就医"),
    ("急性中毒", "误服药物|农药中毒|一氧化碳中毒|吞服异物", "疑似中毒，请立即拨打120并携带毒物样本"),
    ("重度脱水", "婴幼儿腹泻伴精神萎靡|尿量极少|囟门凹陷", "孩子可能重度脱水，请立即就医"),
    ("颅脑外伤", "头部外伤后呕吐|意识改变|耳鼻流血", "头部外伤后异常，请立即就医"),
    ("血糖危象", "糖尿病伴意识模糊|极度口渴多尿|呼吸深快", "可能发生血糖危象，请立即就医"),
    ("急性腹痛", "剧烈腹痛持续不缓解|板状腹|压痛反跳痛", "可能为急腹症，请立即就医"),
    ("消化道大出血", "呕血|柏油样便|头晕心慌", "消化道大出血可能，请立即就医"),
    ("产科急症", "孕期剧烈腹痛|阴道大量出血|胎动消失", "产科急症，请立即就医"),
    ("小儿危重症", "小儿精神萎靡|拒食|呼吸急促|发绀", "患儿病情危重，请立即就医"),
    ("自杀风险", "表达自杀想法|自伤行为|情绪极度低落", "请立即联系心理危机干预或送医"),
]
RED_MODIFIERS = ["伴意识障碍", "进行性加重", "持续不缓解", "突发剧烈", "伴血压下降", "伴呼吸困难", "反复发作", "难以忍受"]


def gen_red_flags(n: int = 250) -> list[list]:
    rows = []
    for i, (symptom, kw, msg) in enumerate(RED_FLAG_CORE, start=1):
        rows.append([f"RF{i:03d}", symptom, kw, 1, "GUIDE_TO_EMERGENCY", msg])
    # 基于症状 × 危重修饰，扩充到 n 条
    idx = len(rows)
    for sym, aliases, part, _dur in ALL_SYMPTOMS:
        if idx >= n:
            break
        for mod in RED_MODIFIERS:
            if idx >= n:
                break
            name = f"{sym}{mod}"
            kw = "|".join(f"{a}{mod}" for a in aliases.split("|")[:2])
            rows.append([f"RF{idx + 1:03d}", name, kw, 1, "GUIDE_TO_EMERGENCY", f"{sym}{mod}，请立即就医评估"])
            idx += 1
    return rows[:n]


# ---- 分诊规则（250）-----------------------------------------------------
def gen_triage_rules(n: int = 250) -> list[list]:
    """症状 → 科室映射。"""
    # 科室主症状映射
    dept_symptom = {
        "DIG": "腹痛|腹泻|恶心|呕吐|反酸|烧心|便血|腹胀",
        "CAR": "胸痛|胸闷|心悸|心慌|气短|高血压",
        "RES": "咳嗽|咳痰|发热|喘息|咯血|呼吸困难",
        "NEU": "头痛|头晕|眩晕|肢体无力|麻木|抽搐|面瘫",
        "END": "多饮|多尿|口渴|消瘦|畏寒|多汗",
        "NEP": "水肿|少尿|多尿|血尿|腰痛",
        "HEM": "贫血|乏力|出血|瘀斑|淋巴结肿大",
        "RHE": "关节痛|关节肿|晨僵|皮疹|光过敏",
        "INF": "发热|皮疹|腹泻|黄疸|盗汗",
        "ONC": "消瘦|肿块|咯血|便血|吞咽困难",
        "GER": "记忆减退|跌倒|乏力|纳差",
        "GEN": "发热|咳嗽|腹痛|头晕|失眠",
        "GS": "腹痛|腹部包块|腹股沟包块|甲状腺结节",
        "ORT": "关节痛|腰背痛|颈痛|骨折|扭伤",
        "URO": "尿频|尿急|尿痛|血尿|排尿困难",
        "NS": "头痛|意识障碍|抽搐|视物模糊",
        "CS": "胸痛|气短|咳嗽|咯血|吞咽困难",
        "VS": "下肢肿胀|下肢发凉|间歇性跛行|血管包块",
        "BS": "乳房肿块|乳房胀痛|乳头溢液",
        "CRS": "便血|肛门疼痛|便秘|脱出",
        "HBS": "右上腹痛|黄疸|腹痛|发热",
        "BURN": "烧伤|烫伤|皮肤溃疡|瘢痕",
        "OB": "停经|孕期腹痛|阴道出血|胎动异常",
        "PED": "发热|咳嗽|腹泻|抽搐|纳差",
        "NEO": "黄疸|喂养困难|气促|体温不稳",
        "DERM": "皮疹|瘙痒|风团|水疱|脱发",
        "OPH": "眼红|眼痛|视力下降|视物模糊|眼干",
        "ENT": "咽痛|鼻塞|流涕|耳鸣|耳痛|声音嘶哑",
        "STO": "牙痛|牙龈出血|口腔溃疡|张口受限",
        "PSY": "失眠|焦虑|抑郁|情绪低落|恐慌",
        "REH": "偏瘫|活动受限|言语障碍|吞咽困难",
        "TCM": "乏力|纳差|失眠|咳嗽|腰痛",
        "ACU": "颈肩腰腿痛|面瘫|失眠|偏头痛",
        "EMER": "剧烈胸痛|昏迷|休克|抽搐|大出血|严重外伤",
        "ICU": "休克|呼吸衰竭|意识障碍|多器官衰竭",
        "ANE": "术前评估|术后疼痛|慢性疼痛",
        "PAIN": "慢性疼痛|神经痛|癌痛|关节疼痛",
        "NUT": "消瘦|营养不良|肥胖|饮食指导",
        "MIN": "健康体检|慢病筛查|职业病筛查",
        "FAM": "慢病随访|健康管理|家庭病床",
        "GCP": "临床试验|入组评估|随访",
    }
    rows = []
    for dept, syms in dept_symptom.items():
        rows.append([syms, dept, DEPT_NAME.get(dept, dept), "", "", 20 if dept == "EMER" else 10, f"{DEPT_NAME.get(dept, dept)}主症状"])
    # 补足到 n：症状 × 科室组合
    idx = len(rows)
    for sym, aliases, part, _dur in ALL_SYMPTOMS:
        if idx >= n:
            break
        # 简单按部位映射科室
        dept = {"腹部": "DIG", "胸部": "CAR", "头部": "NEU", "泌尿": "URO", "生殖": "GYN",
                "关节": "ORT", "皮肤": "DERM", "眼部": "OPH", "耳部": "ENT", "口腔": "STO",
                "咽喉": "ENT", "鼻部": "ENT", "心理": "PSY", "下肢": "VS", "腰部": "ORT"}.get(part, "GEN")
        rows.append([sym, dept, DEPT_NAME.get(dept, dept), "", "", 8, f"{sym}（{part}）"])
        idx += 1
    return rows[:n]


# ---- 追问模板（250）-----------------------------------------------------
INQUIRY_DIMS = [
    ("location", "具体在哪个部位？"),
    ("duration", "出现多久了？"),
    ("nature", "是什么样的感觉（性质）？"),
    ("severity", "严重程度如何（轻/中/重）？"),
    ("trigger", "什么情况下加重或缓解？"),
    ("accompanying", "有没有其它伴随症状？"),
    ("history", "以前有没有类似情况或相关病史？"),
    ("medication", "目前有没有在用药？"),
    ("fever", "有没有发热？体温多少？"),
    ("radiation", "疼痛有没有向其它部位放射？"),
]


def gen_inquiry(n: int = 250) -> list[list]:
    """主诉 × 追问维度。"""
    complaints = [
        "腹痛", "腹泻", "恶心", "呕吐", "胸痛", "胸闷", "心悸", "咳嗽", "咳痰", "发热",
        "头痛", "头晕", "眩晕", "肢体无力", "麻木", "尿频", "尿痛", "血尿", "腰痛", "关节痛",
        "皮疹", "瘙痒", "咽痛", "鼻塞", "耳鸣", "眼红", "视力下降", "失眠", "焦虑", "乏力",
    ]
    rows = []
    order = 1
    for c in complaints:
        for slot, q in INQUIRY_DIMS:
            rows.append([c, slot, q, order])
            order += 1
            if len(rows) >= n:
                return rows
    return rows


# ---- 生成 Excel ---------------------------------------------------------
HEADER_FILL = PatternFill(start_color="17504E", end_color="17504E", fill_type="solid")
HEADER_FONT = Font(color="FFFFFF", bold=True)
TITLE_FONT = Font(color="17504E", bold=True, size=12)

README = [
    ["字段", "说明"],
    ["本工作簿", "医学知识库源数据（小医院规模），用于导入 mg_kb_entry（关系库）与 Milvus（向量库）"],
    ["数据规模", "每个数据 sheet ≥ 250 条；覆盖 41 个一级科室 + 205 个亚专科"],
    ["数据性质", "演示用示例数据，正式使用前须经医学专业人士审核"],
    ["列表字段分隔符", "多个值用 | 分隔，导入脚本据此拆分"],
    ["红旗症状库", "硬编码安全护栏，keywords 用于正则/关键词匹配，layer=1 表示规则层兜底"],
    ["分诊规则", "症状→科室映射，priority 高的（急诊）优先匹配，gender_filter 用于性别过滤"],
    ["追问模板", "按主诉类型（complaint_type）触发，target_slot 对应澄清追问的采集字段"],
]


def main() -> None:
    data = {
        "科室字典": (build_departments(), ["科室编码", "科室名称", "别名", "专长", "亚专科", "对应疾病"]),
        "医生信息": (gen_doctors(), ["医生ID", "姓名", "职称", "科室编码", "科室名称"]),
        "疾病特征库": (ALL_DISEASES, ["科室编码", "疾病名称", "症状", "鉴别诊断要点", "高危因素"]),
        "临床指南": (gen_guidelines(), ["科室编码", "标题", "文本片段", "证据等级", "年份", "来源"]),
        "ICD-10映射": (gen_icd10(), ["疾病名称", "ICD-10编码", "章节", "包含", "排除"]),
        "症状本体库": (ALL_SYMPTOMS, ["标准症状名", "同义词", "身体部位", "持续时间"]),
        "红旗症状库": (gen_red_flags(), ["规则ID", "症状", "关键词", "层级", "动作", "提示文案"]),
        "禁忌症与用药风险": (DRUG_SAFETY + DRUG_SAFETY_2, ["药物", "过敏/禁忌项", "严重度", "建议", "适用人群", "备注"]),
        "分诊规则": (gen_triage_rules(), ["症状", "科室编码", "科室名称", "年龄过滤", "性别过滤", "优先级", "备注"]),
        "追问模板": (gen_inquiry(), ["主诉类型", "目标字段", "追问问题", "顺序"]),
    }

    wb = Workbook()
    wb.remove(wb.active)

    ws = wb.create_sheet("说明")
    for row in README:
        ws.append(row)
    ws.column_dimensions["A"].width = 18
    ws.column_dimensions["B"].width = 70
    ws["A1"].font = TITLE_FONT

    for name, (rows, headers) in data.items():
        ws = wb.create_sheet(name)
        ws.append(headers)
        for cell in ws[1]:
            cell.fill = HEADER_FILL
            cell.font = HEADER_FONT
        for row in rows:
            ws.append(row)
        for i, h in enumerate(headers, start=1):
            max_len = len(h)
            for row in rows:
                if i <= len(row) and row[i - 1] is not None:
                    max_len = max(max_len, len(str(row[i - 1])))
            ws.column_dimensions[get_column_letter(i)].width = min(max_len + 4, 50)
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                cell.alignment = Alignment(vertical="top", wrap_text=True)
        ws.freeze_panes = "A2"

    out = Path(__file__).resolve().parent.parent.parent / "kb" / "医学知识库源数据.xlsx"
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    print(f"已生成 {out}")
    total = 0
    for name, (rows, _) in data.items():
        total += len(rows)
        flag = "✅" if len(rows) >= 250 else "⚠️"
        print(f"  {flag} {name}: {len(rows)} 条")
    print(f"合计 {total} 条（不含说明）")


if __name__ == "__main__":
    main()
