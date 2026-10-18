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
from kb_data.depts import build_departments
from kb_data.diseases import DISEASES_1
from kb_data.diseases2 import DISEASES_2
from kb_data.drugs import DRUG_SAFETY
from kb_data.drugs2 import DRUG_SAFETY_2
from kb_data.icd10 import DEPT_CHAPTER, ICD_EXACT
from kb_data.symptoms import SYMPTOMS
from kb_data.symptoms2 import SYMPTOMS_2

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


# ---- 指南推荐意见（结构化，501 条）--------------------------------------
# 把「一段话的指南片段」拆成可检索的结构：推荐意见 / 证据等级 / 推荐强度 / 适用人群 / 场景
REC_TPL = [
    ("首诊应完成基础检查（血常规、生化），必要时行影像学或内镜评估以明确诊断", "B", "强", "成人", "初诊"),
    ("确诊后需评估病情严重程度，按分层结果决定门诊治疗还是住院观察", "A", "强", "通用", "评估"),
    ("一线方案以病因治疗联合对症支持为主，4 周无效需重新评估诊断", "B", "强", "通用", "治疗"),
    ("治疗期间监测症状变化与药物不良反应，出现加重或新发症状应立即复诊", "B", "强", "通用", "随访"),
    ("合并基础疾病者应同时管理原发病，注意多药联用的相互作用", "C", "弱", "老年", "共病"),
    ("缓解期建议每 3-6 个月随访一次，评估复发风险与生活方式干预依从性", "B", "弱", "通用", "随访"),
    ("儿童患者药物剂量需按体重调整，慎用可能影响生长发育的药物", "C", "弱", "儿童", "用药"),
    ("妊娠期用药需权衡母亲获益与胎儿风险，优先选择安全性证据充分的方案", "C", "强", "孕妇", "用药"),
    ("症状持续超过 2 周或反复发作，建议转诊专科进一步检查", "B", "强", "通用", "转诊"),
    ("非药物干预（饮食、运动、作息）应作为长期管理的基础措施", "B", "弱", "通用", "管理"),
]


def gen_guideline_recs(n_per: int = 2) -> list[list]:
    """每个疾病生成 2 条结构化推荐意见。"""
    rows = []
    for i, (name, dept, *_rest) in enumerate(ALL_DISEASES):
        for j in range(n_per):
            tpl, ev, strength, pop, scene = REC_TPL[(i + j) % len(REC_TPL)]
            rows.append(
                [
                    dept,
                    name,
                    tpl,
                    ev,
                    strength,
                    pop,
                    scene,
                    f"{name}临床诊疗指南",
                    2021 + (i % 4),
                ]
            )
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
    ("急性冠脉综合征", "剧烈胸痛|压榨性胸痛|胸痛伴出汗|胸痛冒冷汗|胸痛出冷汗|胸痛伴冷汗|胸痛伴放射|心梗", "您可能有心脏急症，请立即前往急诊或拨打120"),
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
    for sym, aliases, _part, _dur in ALL_SYMPTOMS:
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
        gender = "女" if dept in ("GYN", "OB") else ""
        rows.append([syms, dept, DEPT_NAME.get(dept, dept), "", gender, 20 if dept == "EMER" else 10, f"{DEPT_NAME.get(dept, dept)}主症状"])
    # 补足到 n：症状 × 科室组合
    idx = len(rows)
    male_kw = ["男性", "射精", "包皮", "阴茎", "睾丸", "阴囊"]
    for sym, _aliases, part, _dur in ALL_SYMPTOMS:
        if idx >= n:
            break
        gender = ""
        if part == "生殖":
            # 男性生殖症状归泌尿外科；其余归妇科（性别过滤）
            if any(k in sym for k in male_kw):
                dept = "URO"
            else:
                dept, gender = "GYN", "女"
        else:
            dept = {"腹部": "DIG", "胸部": "CAR", "头部": "NEU", "泌尿": "URO",
                    "关节": "ORT", "皮肤": "DERM", "眼部": "OPH", "耳部": "ENT", "口腔": "STO",
                    "咽喉": "ENT", "鼻部": "ENT", "心理": "PSY", "下肢": "VS", "腰部": "ORT"}.get(part, "GEN")
        rows.append([sym, dept, DEPT_NAME.get(dept, dept), "", gender, 8, f"{sym}（{part}）"])
        idx += 1
    return rows[:n]


# ---- 追问模板（250）-----------------------------------------------------
# 按主诉定制追问维度（不同主诉问的东西不一样）
INQUIRY_MAP = {
    "腹痛": [("location", "疼痛具体在哪个部位（上腹/下腹/左右侧）？"), ("duration", "疼了多久了？是持续还是阵发？"), ("nature", "疼痛是什么样的（绞痛/胀痛/隐痛/烧灼痛）？"), ("accompanying", "有没有腹泻、恶心、呕吐、发热？"), ("severity", "疼痛程度如何（轻/中/重）？")],
    "腹泻": [("duration", "腹泻多久了？"), ("frequency", "一天腹泻几次？大便是什么样子？"), ("accompanying", "有没有腹痛、发热、呕吐、脱水？"), ("trigger", "有没有吃不干净的东西？"), ("severity", "有没有精神差、尿少？")],
    "恶心": [("duration", "恶心多久了？"), ("trigger", "和进食有关吗？"), ("accompanying", "有没有呕吐、腹痛、头痛？"), ("severity", "是否影响进食？"), ("history", "以前有没有类似情况？")],
    "呕吐": [("duration", "呕吐多久了？"), ("frequency", "吐了几次？吐的是什么？"), ("trigger", "进食后还是空腹？"), ("accompanying", "有没有腹痛、发热、头痛？"), ("severity", "有没有脱水表现？")],
    "胸痛": [("nature", "胸痛是什么样的（压榨/针刺/烧灼）？"), ("radiation", "有没有放射到左臂、下颌或后背？"), ("trigger", "什么情况下加重（活动/劳累/深呼吸）？"), ("accompanying", "有没有出汗、气短、恶心？"), ("duration", "每次持续多久？")],
    "胸闷": [("trigger", "胸闷什么情况下出现（活动/休息/夜间）？"), ("duration", "每次持续多久？能否自行缓解？"), ("accompanying", "有没有胸痛、气短、心悸？"), ("radiation", "有没有放射感？"), ("history", "有没有心脏病史？")],
    "心悸": [("trigger", "心慌什么情况下出现？"), ("duration", "每次持续多久？"), ("nature", "是心跳快、乱还是重？"), ("accompanying", "有没有胸痛、气短、头晕、多汗？"), ("history", "有没有甲亢或心脏病史？")],
    "咳嗽": [("duration", "咳嗽多久了？"), ("sputum", "有没有痰？痰是什么颜色？"), ("fever", "有没有发热？体温多少？"), ("trigger", "夜间或活动后加重吗？"), ("accompanying", "有没有气短、胸痛？")],
    "咳痰": [("color", "痰是什么颜色（白/黄/绿/带血）？"), ("amount", "痰量多不多？"), ("duration", "咳痰多久了？"), ("fever", "有没有发热？"), ("accompanying", "有没有气短、胸痛？")],
    "发热": [("duration", "发热多久了？"), ("degree", "最高体温多少？"), ("pattern", "是持续还是忽高忽低？"), ("accompanying", "有没有咳嗽、咽痛、腹泻、皮疹？"), ("history", "有没有接触发热病人或旅行史？")],
    "头痛": [("location", "头痛在哪个部位（太阳穴/后脑勺/全头）？"), ("nature", "是胀痛、跳痛还是刺痛？"), ("accompanying", "有没有恶心、呕吐、畏光、发热？"), ("trigger", "什么情况下加重？"), ("severity", "疼痛程度如何？")],
    "头晕": [("nature", "是旋转感（天旋地转）还是头重脚轻？"), ("duration", "持续多久？是阵发还是持续？"), ("trigger", "体位变化时加重吗？"), ("accompanying", "有没有恶心、耳鸣、肢体无力？"), ("history", "有没有高血压、颈椎病？")],
    "眩晕": [("duration", "眩晕持续多久？"), ("trigger", "头位变动时诱发吗？"), ("accompanying", "有没有耳鸣、听力下降、恶心？"), ("nature", "是天旋地转还是摇晃感？"), ("history", "以前有没有类似发作？")],
    "肢体无力": [("onset", "无力是突然发生还是慢慢出现的？"), ("location", "是单侧还是双侧？具体哪边？"), ("accompanying", "有没有言语不清、口角歪斜？"), ("progression", "是加重还是好转？"), ("history", "有没有高血压、糖尿病？")],
    "麻木": [("location", "麻木在哪个部位？"), ("nature", "是持续还是阵发？"), ("accompanying", "有没有无力、疼痛？"), ("trigger", "什么姿势下出现？"), ("history", "有没有糖尿病、颈椎病？")],
    "尿频": [("duration", "尿频多久了？"), ("frequency", "一天几次？夜尿几次？"), ("accompanying", "有没有尿痛、血尿、发热？"), ("trigger", "和饮水、情绪有关吗？"), ("history", "有没有前列腺或妇科病史？")],
    "尿急": [("duration", "尿急多久了？"), ("accompanying", "有没有尿痛、尿频、血尿？"), ("trigger", "憋不住时有没有漏尿？"), ("severity", "是否影响生活？"), ("history", "有没有尿路感染史？")],
    "尿痛": [("duration", "尿痛多久了？"), ("nature", "是排尿开始痛还是全程痛？"), ("accompanying", "有没有尿频、尿急、血尿、发热？"), ("trigger", "和性生活有关吗？"), ("history", "有没有尿路感染史？")],
    "血尿": [("nature", "是肉眼可见还是镜下血尿？"), ("duration", "出现多久了？"), ("accompanying", "有没有腰痛、尿痛、发热？"), ("trigger", "和运动、月经有关吗？"), ("history", "有没有结石、肿瘤病史？")],
    "腰痛": [("location", "腰痛在哪个部位？"), ("nature", "是酸痛、绞痛还是刺痛？"), ("trigger", "什么姿势或动作加重？"), ("accompanying", "有没有下肢放射痛、麻木？"), ("history", "有没有外伤或久坐？")],
    "关节痛": [("location", "哪个关节痛？单侧还是双侧？"), ("nature", "是肿痛、刺痛还是酸痛？"), ("duration", "痛了多久？晨僵吗？"), ("trigger", "活动后加重还是缓解？"), ("accompanying", "有没有红肿、发热？")],
    "皮疹": [("location", "皮疹在哪些部位？"), ("nature", "是什么样（红斑/丘疹/水疱/风团）？"), ("duration", "出现多久了？"), ("trigger", "有没有接触过敏原、用药、进食特殊食物？"), ("accompanying", "有没有瘙痒、发热？")],
    "瘙痒": [("location", "哪里痒？范围多大？"), ("duration", "痒了多久？"), ("nature", "是阵发还是持续？夜间加重吗？"), ("trigger", "什么情况下加重？"), ("accompanying", "有没有皮疹、干燥？")],
    "咽痛": [("duration", "咽痛多久了？"), ("severity", "吞咽时疼吗？影响进食吗？"), ("accompanying", "有没有发热、咳嗽、扁桃体肿大？"), ("trigger", "有没有受凉或用嗓过度？"), ("history", "以前有没有反复咽痛？")],
    "鼻塞": [("duration", "鼻塞多久了？"), ("nature", "是单侧还是双侧？持续还是阵发？"), ("accompanying", "有没有流涕、喷嚏、鼻痒？"), ("trigger", "季节性或接触过敏原时加重吗？"), ("history", "有没有鼻炎史？")],
    "耳鸣": [("nature", "耳鸣是什么样的声音？"), ("duration", "持续多久了？"), ("location", "单侧还是双侧？"), ("accompanying", "有没有听力下降、眩晕？"), ("history", "有没有噪声暴露或耳部疾病？")],
    "眼红": [("duration", "眼红多久了？"), ("accompanying", "有没有眼痛、眼痒、分泌物？"), ("location", "单眼还是双眼？"), ("trigger", "有没有接触刺激物或揉眼？"), ("history", "有没有过敏或戴隐形眼镜？")],
    "视力下降": [("onset", "视力下降是突然还是逐渐？"), ("location", "单眼还是双眼？"), ("accompanying", "有没有眼痛、视野缺损、黑影？"), ("trigger", "和用眼、外伤有关吗？"), ("history", "有没有糖尿病、高血压？")],
    "失眠": [("nature", "是入睡困难、易醒还是早醒？"), ("duration", "失眠多久了？"), ("trigger", "有没有精神压力或作息变化？"), ("accompanying", "有没有焦虑、情绪低落？"), ("history", "有没有用药或咖啡因摄入？")],
    "焦虑": [("duration", "焦虑多久了？"), ("trigger", "什么情况下加重？"), ("accompanying", "有没有心慌、多汗、坐立不安？"), ("severity", "是否影响工作生活？"), ("history", "有没有类似发作或家族史？")],
    "乏力": [("duration", "乏力多久了？"), ("trigger", "休息后能缓解吗？"), ("accompanying", "有没有消瘦、发热、纳差？"), ("severity", "是否影响日常活动？"), ("history", "有没有慢性病或用药？")],
    "消瘦": [("duration", "体重下降多久了？"), ("amount", "下降了多少斤？"), ("accompanying", "有没有食欲亢进、多饮多尿、腹泻？"), ("trigger", "有没有刻意节食或运动？"), ("history", "有没有糖尿病、甲亢、肿瘤史？")],
    "水肿": [("location", "水肿在哪个部位？"), ("duration", "水肿多久了？"), ("nature", "是凹陷性还是非凹陷性？"), ("accompanying", "有没有气短、尿少、泡沫尿？"), ("history", "有没有心肝肾疾病？")],
    "便血": [("nature", "血是鲜红还是暗红？附在大便表面还是混在里？"), ("duration", "便血多久了？"), ("amount", "量大不大？"), ("accompanying", "有没有腹痛、排便习惯改变？"), ("history", "有没有痔疮或肠病家族史？")],
    "便秘": [("duration", "便秘多久了？"), ("frequency", "几天一次？"), ("nature", "大便干硬吗？排便费力吗？"), ("accompanying", "有没有腹胀、腹痛、便血？"), ("history", "有没有用药或饮水少？")],
    "腹胀": [("duration", "腹胀多久了？"), ("trigger", "和进食有关吗？"), ("accompanying", "有没有腹痛、排气减少、呕吐？"), ("nature", "是持续还是阵发？"), ("history", "有没有胃肠疾病？")],
    "气短": [("trigger", "气短什么情况下出现（活动/休息/夜间）？"), ("severity", "能走多远或上几层楼？"), ("accompanying", "有没有咳嗽、胸痛、心悸？"), ("duration", "多久了？"), ("history", "有没有心肺疾病？")],
    "背痛": [("location", "背痛在哪个部位？"), ("nature", "是酸痛、刺痛还是放射痛？"), ("trigger", "什么姿势加重？"), ("accompanying", "有没有下肢麻木、无力？"), ("history", "有没有外伤或久坐？")],
    "颈痛": [("duration", "颈痛多久了？"), ("nature", "是酸痛、僵硬还是放射痛？"), ("trigger", "转头或低头时加重吗？"), ("accompanying", "有没有上肢麻木、头晕？"), ("history", "有没有久坐或外伤？")],
    "牙痛": [("location", "哪颗牙痛？上牙还是下牙？"), ("nature", "是持续痛、冷热痛还是咬合痛？"), ("duration", "痛了多久？夜间加重吗？"), ("trigger", "冷热刺激时痛吗？"), ("history", "有没有龋齿或牙周病？")],
    "耳痛": [("location", "哪只耳朵痛？"), ("duration", "痛了多久？"), ("accompanying", "有没有听力下降、耳鸣、流脓？"), ("trigger", "有没有感冒、游泳进水？"), ("history", "有没有中耳炎史？")],
    "月经不调": [("pattern", "周期怎么乱（提前/推迟/不规律）？"), ("duration", "持续多久了？"), ("amount", "经量多还是少？"), ("accompanying", "有没有痛经、白带异常？"), ("history", "有没有精神压力或体重变化？")],
    "白带异常": [("nature", "白带是什么颜色、气味、性状？"), ("duration", "出现多久了？"), ("accompanying", "有没有外阴瘙痒、灼痛？"), ("trigger", "和月经周期有关吗？"), ("history", "有没有阴道炎史？")],
    "停经": [("duration", "停经多久了？"), ("possibility", "有没有性生活？可能怀孕吗？"), ("accompanying", "有没有恶心、乳房胀痛？"), ("history", "以前月经规律吗？"), ("trigger", "有没有精神压力或体重骤变？")],
    "皮肤瘙痒": [("location", "哪里痒？范围多大？"), ("duration", "痒了多久？"), ("trigger", "什么情况下加重？"), ("accompanying", "有没有皮疹、干燥、黄疸？"), ("history", "有没有过敏或肝胆疾病？")],
    "脱发": [("pattern", "是斑片状还是整体稀疏？"), ("duration", "脱发多久了？"), ("amount", "每天掉多少？"), ("accompanying", "有没有头皮痒、红斑？"), ("history", "有没有精神压力、用药、家族史？")],
    "口干": [("duration", "口干多久了？"), ("trigger", "喝水能缓解吗？"), ("accompanying", "有没有眼干、多饮多尿？"), ("severity", "是否影响进食吞咽？"), ("history", "有没有糖尿病或干燥综合征？")],
    "多饮": [("duration", "多饮多久了？"), ("amount", "每天喝多少水？"), ("accompanying", "有没有多尿、消瘦、乏力？"), ("trigger", "和天气、运动有关吗？"), ("history", "有没有糖尿病史？")],
    "多尿": [("frequency", "一天尿几次？夜尿几次？"), ("duration", "多尿多久了？"), ("amount", "尿量多吗？"), ("accompanying", "有没有多饮、消瘦、乏力？"), ("history", "有没有糖尿病或尿崩症？")],
    "体重下降": [("amount", "下降了多少？"), ("duration", "多久内下降的？"), ("accompanying", "有没有食欲亢进、多饮多尿、腹泻？"), ("trigger", "有没有刻意节食？"), ("history", "有没有糖尿病、甲亢、肿瘤史？")],
}


def gen_inquiry(n: int = 250) -> list[list]:
    """主诉 × 定制追问维度（每个主诉 5 个维度）。"""
    rows = []
    order = 1
    for complaint, dims in INQUIRY_MAP.items():
        for slot, q in dims:
            rows.append([complaint, slot, q, order])
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
        "疾病特征库": (ALL_DISEASES, ["疾病名称", "科室编码", "症状", "鉴别诊断要点", "高危因素"]),
        "临床指南": (gen_guidelines(), ["科室编码", "标题", "文本片段", "证据等级", "年份", "来源"]),
        "指南推荐意见": (
            gen_guideline_recs(),
            ["科室编码", "疾病名称", "推荐意见", "证据等级", "推荐强度", "适用人群", "场景", "指南来源", "年份"],
        ),
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
