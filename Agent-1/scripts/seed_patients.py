"""
种子数据脚本 —— 填充 5 位患者及完整的病历、就诊记录。

覆盖 PRD 测试场景：
  - 患者事实查询（主档、过敏史、家族史、紧急联系人）
  - 病历/就诊调阅（慢病、术后、儿科、跨科室）
  - 过敏安全机制（青霉素/磺胺/头孢过敏）
  - 连续记忆聊天（不同病情复杂度）

用法：
  python scripts/seed_patients.py
"""

import os
import sys

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.models.patient import Patient
from app.models.medical_record import MedicalRecord
from app.models.visit_record import VisitRecord


# ============================================================================
# 患者数据
# ============================================================================

PATIENTS = [
    {
        # ── 张三：高血压慢病管理，心内科老病号 ──
        "hospital_id": "hospital-a",
        "patient_code": "P0001",
        "full_name": "陈建国",
        "gender": "male",
        "birth_date": "1968-05-10",
        "phone": "13800010001",
        "address": "上海市浦东新区张江镇碧波路888弄12号301室",
        "emergency_contact_name": "陈梅（配偶）",
        "emergency_contact_phone": "13800010002",
        "blood_type": "A",
        "allergy_history": "青霉素过敏（皮疹）；头孢类慎用（既往轻度皮疹）",
        "family_history": "父亲：高血压、冠心病，68岁心梗去世；母亲：高血压，健在",
        "notes": "偏好简短沟通；每次就诊需提醒服药依从性；职业：退休教师",
    },
    {
        # ── 李四：2型糖尿病长期随访，内分泌科 ──
        "hospital_id": "hospital-a",
        "patient_code": "P0002",
        "full_name": "林美娟",
        "gender": "female",
        "birth_date": "1975-08-22",
        "phone": "13900020001",
        "address": "上海市徐汇区漕河泾开发区田林路200号502室",
        "emergency_contact_name": "林志强（儿子）",
        "emergency_contact_phone": "13900020002",
        "blood_type": "O",
        "allergy_history": "无已知药物过敏",
        "family_history": "母亲：2型糖尿病、高血压；父亲：体健；有糖尿病家族聚集倾向",
        "notes": "对用药调整较焦虑，需要耐心解释；职业：公司财务",
    },
    {
        # ── 王五：膝关节炎术后康复，骨科 ──
        "hospital_id": "hospital-a",
        "patient_code": "P0003",
        "full_name": "张国栋",
        "gender": "male",
        "birth_date": "1955-03-15",
        "phone": "13700030001",
        "address": "北京市朝阳区望京街道花家地北里5号楼3单元102",
        "emergency_contact_name": "张芳（女儿）",
        "emergency_contact_phone": "13700030002",
        "blood_type": "B",
        "allergy_history": "磺胺类药物过敏（全身皮疹+发热）；酒精过敏（面部潮红）",
        "family_history": "父亲：骨关节炎、高血压；母亲：体健",
        "notes": "需要轮椅辅助；术后康复训练配合度一般，需要多鼓励；职业：退休工人",
    },
    {
        # ── 赵六：小儿发热/上呼吸道感染，儿科 ──
        "hospital_id": "hospital-a",
        "patient_code": "P0004",
        "full_name": "吴小雅",
        "gender": "female",
        "birth_date": "2019-11-28",
        "phone": "13600040001",
        "address": "上海市闵行区莘庄镇莘建路100号601室",
        "emergency_contact_name": "吴建国（父亲）",
        "emergency_contact_phone": "13600040002",
        "blood_type": "AB",
        "allergy_history": "头孢类抗生素过敏（既往注射头孢曲松后出现荨麻疹）",
        "family_history": "父亲：过敏性鼻炎；母亲：体健；无明确遗传病史",
        "notes": "家长焦虑程度较高，就诊时需额外安抚；需注意用药剂量按体重计算",
    },
    {
        # ── 孙七：多科室跨院区就诊，心内科+消化科 ──
        "hospital_id": "hospital-b",
        "patient_code": "P1001",
        "full_name": "郑文婷",
        "gender": "female",
        "birth_date": "1982-07-03",
        "phone": "13500050001",
        "address": "上海市静安区南京西路1266号恒隆广场附近",
        "emergency_contact_name": "郑磊（哥哥）",
        "emergency_contact_phone": "13500050002",
        "blood_type": "A",
        "allergy_history": "阿司匹林过敏（诱发哮喘）；花粉过敏（季节性）",
        "family_history": "父亲：高血压、胃溃疡；母亲：甲状腺功能减退",
        "notes": "工作繁忙，偏好线上问诊；跨院区就诊（hospital-a心内科，hospital-b消化科）；职业：金融分析师",
    },
]


# ============================================================================
# 病历数据 —— 每位患者 2-3 条，字段齐全
# ============================================================================

MEDICAL_RECORDS = {
    "P0001": [
        {
            "record_date": "2025-12-01",
            "record_type": "outpatient",
            "title": "高血压复诊",
            "department": "心内科",
            "doctor_name": "王志强",
            "chief_complaint": "晨起头晕两周，伴轻微心悸",
            "present_illness": "患者高血压病史10年，长期口服缬沙坦80mg qd。近两周晨起血压偏高（150-160/90-95mmHg），伴头晕、心悸，无胸闷胸痛，无呼吸困难。自行加量至160mg后症状未缓解。",
            "diagnosis": "原发性高血压 2级（高危）；药物控制欠佳",
            "treatment_plan": "1. 缬沙坦调整为160mg qd；2. 加用氨氯地平5mg qd联合降压；3. 低盐低脂饮食，每日限盐<5g；4. 家庭自测血压并记录；5. 两周后复诊评估",
            "medications": "缬沙坦 160mg qd；氨氯地平 5mg qd",
            "notes": "患者近期因家庭琐事情绪波动，可能影响血压控制。嘱保持情绪稳定。",
        },
        {
            "record_date": "2025-09-15",
            "record_type": "outpatient",
            "title": "高血压常规复诊",
            "department": "心内科",
            "doctor_name": "王志强",
            "chief_complaint": "无明显不适，常规取药复查",
            "present_illness": "患者长期规律服药，家庭自测血压稳定在130-140/80-85mmHg。无头晕、胸闷等不适。",
            "diagnosis": "原发性高血压 2级，药物控制可",
            "treatment_plan": "继续缬沙坦80mg qd；低盐饮食；三个月后复诊",
            "medications": "缬沙坦 80mg qd",
            "notes": "血压控制良好，患者依从性好。",
        },
        {
            "record_date": "2024-06-01",
            "record_type": "report",
            "title": "年度体检报告解读",
            "department": "体检中心",
            "doctor_name": "陈建华",
            "chief_complaint": "体检发现血脂偏高，咨询处理方案",
            "present_illness": "年度体检示：总胆固醇6.2mmol/L，LDL-C 3.8mmol/L，HDL-C 1.0mmol/L。心电图：窦性心律，无明显ST-T改变。",
            "diagnosis": "混合型高脂血症",
            "treatment_plan": "1. 阿托伐他汀20mg qn起始；2. 严格低脂饮食，增加膳食纤维；3. 适度有氧运动每周≥150分钟；4. 6周后复查血脂+肝功能",
            "medications": "阿托伐他汀 20mg qn",
            "notes": "需注意他汀类药物的肝功能监测。患者青霉素过敏，避免含青霉素类药物。",
        },
    ],
    "P0002": [
        {
            "record_date": "2025-11-20",
            "record_type": "outpatient",
            "title": "糖尿病复诊 — 血糖波动",
            "department": "内分泌科",
            "doctor_name": "李美玲",
            "chief_complaint": "近一月空腹血糖偏高（7.5-8.5mmol/L），餐后2h血糖11-13mmol/L",
            "present_illness": "2型糖尿病病史8年，口服二甲双胍500mg bid+格列美脲2mg qd。近一月饮食控制欠佳（年底聚餐增多），运动量减少。空腹血糖升至7.5-8.5mmol/L，HbA1c 7.8%。体重增加2kg。",
            "diagnosis": "2型糖尿病，血糖控制不良",
            "treatment_plan": "1. 二甲双胍调整为1000mg bid；2. 格列美脲继续2mg qd；3. 严格糖尿病饮食，每日总热量控制在1600kcal；4. 每周≥5天快走30分钟；5. 每日自测空腹+睡前血糖并记录；6. 转诊营养科",
            "medications": "二甲双胍 1000mg bid；格列美脲 2mg qd",
            "notes": "患者对药物调整存在焦虑，已详细解释调整原因和注意事项。建议3周后复诊。",
        },
        {
            "record_date": "2025-06-10",
            "record_type": "outpatient",
            "title": "糖尿病常规复诊",
            "department": "内分泌科",
            "doctor_name": "李美玲",
            "chief_complaint": "常规取药，无特殊不适",
            "present_illness": "血糖控制可，空腹6.0-6.8mmol/L，餐后2h 8-9mmol/L。无低血糖发作。",
            "diagnosis": "2型糖尿病，药物控制可",
            "treatment_plan": "继续当前方案；每三个月复查HbA1c；每年眼底+足部检查",
            "medications": "二甲双胍 500mg bid；格列美脲 2mg qd",
            "notes": "患者依从性好。提醒注意足部护理。",
        },
        {
            "record_date": "2024-03-05",
            "record_type": "report",
            "title": "糖尿病并发症筛查",
            "department": "内分泌科",
            "doctor_name": "赵博",
            "chief_complaint": "年度并发症筛查",
            "present_illness": "眼底检查：轻度非增殖性糖尿病视网膜病变（双眼）。尿微量白蛋白：32mg/g Cr（轻度升高）。神经传导速度：下肢轻度感觉神经传导减慢。",
            "diagnosis": "糖尿病早期微血管并发症（视网膜病变I期，早期肾病）",
            "treatment_plan": "1. 严格控制血糖（空腹<6.5mmol/L，餐后2h<8mmol/L）；2. 加用厄贝沙坦75mg qd保护肾功能；3. 每半年眼科复查；4. 低蛋白饮食（每日0.8g/kg）",
            "medications": "二甲双胍 500mg bid；格列美脲 2mg qd；厄贝沙坦 75mg qd",
            "notes": "患者对并发症感到担忧，已详细沟通：早期干预可延缓进展。",
        },
    ],
    "P0003": [
        {
            "record_date": "2025-10-05",
            "record_type": "inpatient",
            "title": "左膝关节置换术后住院记录",
            "department": "骨科",
            "doctor_name": "张建国",
            "chief_complaint": "左膝全膝关节置换术后第1天",
            "present_illness": "患者因左膝重度骨关节炎（Kellgren-Lawrence IV级），于2025-10-04在腰麻下行左膝全膝关节置换术（TKA）。手术顺利，术中出血约200ml。术后安返病房。",
            "diagnosis": "左膝重度骨关节炎，全膝关节置换术后",
            "treatment_plan": "1. 术后24-48h预防性抗生素（头孢呋辛，已确认无头孢过敏）；2. 低分子肝素预防DVT；3. 术后第1天开始CPM机被动活动+踝泵训练；4. 术后第2天尝试下床站立；5. 疼痛管理：塞来昔布200mg bid + 按需曲马多",
            "medications": "头孢呋辛 1.5g iv q12h（预防感染）；低分子肝素 4000IU ih qd；塞来昔布 200mg bid；曲马多 50mg prn",
            "notes": "⚠ 磺胺类药物过敏，避免使用磺胺类及含磺胺结构药物。术后康复团队已介入。",
        },
        {
            "record_date": "2025-10-18",
            "record_type": "outpatient",
            "title": "膝关节置换术后拆线复查",
            "department": "骨科",
            "doctor_name": "张建国",
            "chief_complaint": "术后两周，伤口愈合良好，轻度肿胀",
            "present_illness": "术后两周，伤口愈合良好，无红肿渗液。左膝关节活动度：屈曲0-85°，伸直0°。VAS疼痛评分2-3分（静息）/4-5分（活动时）。可拄双拐行走。",
            "diagnosis": "左膝TKA术后恢复期（二期愈合良好）",
            "treatment_plan": "1. 拆线；2. 继续康复训练，目标术后6周屈曲≥110°；3. 逐渐减少拐杖依赖；4. 一月后复诊拍X光片",
            "medications": "塞来昔布 200mg bid prn（疼痛时服用）",
            "notes": "患者康复配合度较术后第一周有明显改善。鼓励继续坚持康复训练。",
        },
    ],
    "P0004": [
        {
            "record_date": "2025-12-05",
            "record_type": "emergency",
            "title": "急诊 — 高热惊厥",
            "department": "儿科",
            "doctor_name": "刘丽华",
            "chief_complaint": "发热39.5°C持续6小时，伴一次全身抽搐约1分钟",
            "present_illness": "患儿6岁，近2天有轻微流涕、咳嗽。今日晨起突发高热，测体温39.5°C。约上午10时出现一次全身抽搐，持续约1分钟后自行缓解，意识恢复。抽搐时口吐白沫、双目上翻。既往无惊厥史。",
            "diagnosis": "急性上呼吸道感染；热性惊厥（单纯型）；高热",
            "treatment_plan": "1. 物理降温+布洛芬混悬液退热（按体重计算：20mg/kg）；2. 补液：口服补液盐；3. 密切观察，若再次惊厥或持续>5分钟需紧急处理；4. 收入院观察24小时",
            "medications": "布洛芬混悬液 100mg/5ml，每次6ml prn（q6h，体温>38.5°C时使用）",
            "notes": "⚠ 头孢类抗生素过敏，避免使用。家长极度焦虑，已详细解释热性惊厥通常预后良好。",
        },
        {
            "record_date": "2025-12-08",
            "record_type": "outpatient",
            "title": "热性惊厥后复诊",
            "department": "儿科",
            "doctor_name": "刘丽华",
            "chief_complaint": "体温已降至正常，仍有轻咳",
            "present_illness": "住院观察3天，体温逐步下降至正常范围（36.5-37.2°C），未再发生惊厥。仍有轻度干咳，精神食欲恢复。",
            "diagnosis": "上呼吸道感染恢复期；热性惊厥（已缓解）",
            "treatment_plan": "1. 继续观察体温，若再次发热需及时退热；2. 小儿止咳糖浆对症处理；3. 若再次发生惊厥，需行脑电图检查；4. 一周后复诊",
            "medications": "小儿止咳糖浆 5ml tid；布洛芬备用（仅发热时使用）",
            "notes": "家长情绪趋于稳定。建议家中常备退热药和体温计。热性惊厥通常为良性过程，但需警惕复发。",
        },
    ],
    "P1001": [
        {
            "record_date": "2025-11-10",
            "record_type": "outpatient",
            "title": "心悸待查",
            "department": "心内科",
            "doctor_name": "王志强",
            "chief_complaint": "近一月反复心悸，伴胸闷、气短",
            "present_illness": "患者近一月无明显诱因反复出现心悸，偶伴胸闷、气短，每次持续数分钟至半小时不等，休息后缓解。无胸痛、无晕厥。工作压力大，每日咖啡2-3杯。",
            "diagnosis": "心悸待查：功能性心律失常？焦虑状态？",
            "treatment_plan": "1. 24小时动态心电图监测；2. 心脏彩超；3. 甲状腺功能检查；4. 减少咖啡因摄入；5. 若检查结果无异常，建议心理科咨询",
            "medications": "暂无规律用药",
            "notes": "⚠ 阿司匹林过敏（诱发哮喘），避免使用任何含阿司匹林及NSAIDs药物。患者工作繁忙，建议线上问诊随访。",
        },
        {
            "record_date": "2025-10-20",
            "record_type": "outpatient",
            "title": "上腹痛伴反酸",
            "department": "消化内科",
            "doctor_name": "周明辉",
            "chief_complaint": "反复上腹痛2月，餐后加重，伴反酸、烧心",
            "present_illness": "患者近2月反复上腹部隐痛，餐后明显加重，伴反酸、胸骨后烧灼感。偶有夜间痛。进食辛辣、咖啡后加重。近一周症状加重，自行服用铝碳酸镁效果欠佳。",
            "diagnosis": "胃食管反流病（GERD）；慢性浅表性胃炎（待胃镜确认）",
            "treatment_plan": "1. 奥美拉唑20mg bid餐前；2. 铝碳酸镁咀嚼片餐后+睡前prn；3. 建议行胃镜检查明确诊断；4. 饮食调整：少食多餐、避免刺激性食物、睡前3小时不进食",
            "medications": "奥美拉唑 20mg bid（餐前30min）；铝碳酸镁 1.0g tid prn",
            "notes": "患者因工作原因暂未做胃镜，已预约。注意与心内科就诊记录交叉关联——胸闷也可能与GERD相关。",
        },
    ],
}


# ============================================================================
# 就诊记录数据 —— 每位患者 2-3 条，字段齐全
# ============================================================================

VISIT_RECORDS = {
    "P0001": [
        {
            "visit_date": "2025-12-01",
            "visit_type": "outpatient",
            "department": "心内科",
            "doctor_name": "王志强",
            "campus": "本部院区",
            "chief_complaint": "晨起头晕两周，伴轻微心悸",
            "visit_status": "completed",
            "visit_summary": "血压控制欠佳，调整降压方案：缬沙坦加量+加用氨氯地平。嘱低盐饮食、家庭血压监测。两周后复诊。",
            "follow_up_plan": "两周后复诊心内科，复查血压+心电图。同步复查血脂（上次体检血脂偏高）。",
        },
        {
            "visit_date": "2025-09-15",
            "visit_type": "outpatient",
            "department": "心内科",
            "doctor_name": "王志强",
            "campus": "本部院区",
            "chief_complaint": "常规取药复查",
            "visit_status": "completed",
            "visit_summary": "血压控制良好，继续当前方案。常规取药缬沙坦3个月用量。",
            "follow_up_plan": "三个月后复诊取药。",
        },
        {
            "visit_date": "2024-06-01",
            "visit_type": "outpatient",
            "department": "体检中心",
            "doctor_name": "陈建华",
            "campus": "本部院区",
            "chief_complaint": "年度体检报告解读",
            "visit_status": "completed",
            "visit_summary": "体检示高脂血症，给予阿托伐他汀治疗。建议生活方式干预。",
            "follow_up_plan": "6周后复查血脂+肝功能。",
        },
    ],
    "P0002": [
        {
            "visit_date": "2025-11-20",
            "visit_type": "outpatient",
            "department": "内分泌科",
            "doctor_name": "李美玲",
            "campus": "本部院区",
            "chief_complaint": "血糖波动，餐后偏高",
            "visit_status": "completed",
            "visit_summary": "血糖控制不良，调整二甲双胍剂量。转诊营养科进行饮食指导。患者对药物调整存在焦虑，已详细解释。",
            "follow_up_plan": "三周后复诊内分泌科，空腹+餐后2h血糖+HbA1c。同步营养科门诊。",
        },
        {
            "visit_date": "2025-06-10",
            "visit_type": "follow_up",
            "department": "内分泌科",
            "doctor_name": "李美玲",
            "campus": "本部院区",
            "chief_complaint": "常规取药，无特殊不适",
            "visit_status": "completed",
            "visit_summary": "血糖控制可，常规取药。提醒足部护理和年度眼底检查。",
            "follow_up_plan": "每三个月复诊取药。今年内完成眼底检查。",
        },
    ],
    "P0003": [
        {
            "visit_date": "2025-10-04",
            "visit_type": "inpatient",
            "department": "骨科",
            "doctor_name": "张建国",
            "campus": "本部院区",
            "chief_complaint": "左膝重度骨关节炎，入院行关节置换术",
            "visit_status": "admitted",
            "visit_summary": "入院行左膝全膝关节置换术。术前评估：心肺功能可，手术风险可控。注意磺胺过敏史。",
            "follow_up_plan": "术后2周拆线复查；术后6周X光片+功能评估；术后3/6/12月定期复查。",
        },
        {
            "visit_date": "2025-10-18",
            "visit_type": "follow_up",
            "department": "骨科",
            "doctor_name": "张建国",
            "campus": "本部院区",
            "chief_complaint": "关节置换术后2周拆线+复查",
            "visit_status": "completed",
            "visit_summary": "伤口愈合良好，拆线。关节活动度可（屈曲0-85°）。继续康复训练，鼓励增加活动量。",
            "follow_up_plan": "一月后拍X光片复查。康复科继续随访。",
        },
    ],
    "P0004": [
        {
            "visit_date": "2025-12-05",
            "visit_type": "emergency",
            "department": "儿科",
            "doctor_name": "刘丽华",
            "campus": "本部院区",
            "chief_complaint": "高热39.5°C，抽搐一次",
            "visit_status": "admitted",
            "visit_summary": "急性上呼吸道感染合并热性惊厥。给予退热、补液处理，收入院观察。家长焦虑，已安抚并详细解释病情。",
            "follow_up_plan": "住院观察3天，稳定后出院。出院3天后复诊。若再次惊厥需行脑电图。",
        },
        {
            "visit_date": "2025-12-08",
            "visit_type": "follow_up",
            "department": "儿科",
            "doctor_name": "刘丽华",
            "campus": "本部院区",
            "chief_complaint": "热退，轻咳，复诊评估",
            "visit_status": "completed",
            "visit_summary": "体温正常，未再惊厥。精神食欲恢复，轻咳对症处理。家长情绪稳定。",
            "follow_up_plan": "一周后复诊。家中常备退热药。若发热需及时退热处理，警惕惊厥复发。",
        },
    ],
    "P1001": [
        {
            "visit_date": "2025-11-10",
            "visit_type": "outpatient",
            "department": "心内科",
            "doctor_name": "王志强",
            "campus": "本部院区",
            "chief_complaint": "反复心悸、胸闷",
            "visit_status": "completed",
            "visit_summary": "心悸待查，已开具动态心电图和心脏彩超，待结果回报。建议减少咖啡因摄入。",
            "follow_up_plan": "一周后携带检查结果复诊心内科。若心悸加重随时急诊。",
        },
        {
            "visit_date": "2025-10-20",
            "visit_type": "outpatient",
            "department": "消化内科",
            "doctor_name": "周明辉",
            "campus": "东院区",
            "chief_complaint": "上腹痛、反酸、烧心",
            "visit_status": "completed",
            "visit_summary": "诊断GERD+慢性胃炎可能，启动PPI治疗。胃镜已预约，待检查明确诊断。",
            "follow_up_plan": "两周后消化内科复诊（携带胃镜结果）。药效评估后决定是否调整方案。",
        },
        {
            "visit_date": "2025-09-01",
            "visit_type": "outpatient",
            "department": "消化内科",
            "doctor_name": "周明辉",
            "campus": "东院区",
            "chief_complaint": "偶尔反酸，首次就诊",
            "visit_status": "completed",
            "visit_summary": "症状较轻，建议生活方式调整：少食多餐、避免刺激性食物。暂不用药观察。",
            "follow_up_plan": "若症状持续或加重则复诊。",
        },
    ],
}


# ============================================================================
# 主逻辑
# ============================================================================

def seed():
    db = SessionLocal()
    try:
        count = db.query(Patient).count()
        if count > 0:
            print(f"数据库已有 {count} 位患者，跳过种子数据填充。")
            print("如需重新填充，请先清空 patients/medical_records/visit_records 表。")
            return

        print("=" * 60)
        print("  患者智能辅助 Agent — 种子数据填充")
        print("=" * 60)

        patient_map = {}  # patient_code -> Patient ORM object

        for pdata in PATIENTS:
            code = pdata["patient_code"]
            p = Patient(**pdata)
            db.add(p)
            db.flush()
            patient_map[code] = p
            print(f"\n[OK] 患者: {p.full_name}")
            print(f"    ID: {p.id}")
            print(f"    手机: {p.phone}")
            print(f"    过敏史: {p.allergy_history[:40]}..." if len(p.allergy_history or "") > 40 else f"    过敏史: {p.allergy_history}")

            # ── 添加病历 ──
            mrs = MEDICAL_RECORDS.get(code, [])
            for mr_data in mrs:
                mr = MedicalRecord(
                    patient_id=p.id,
                    hospital_id=pdata["hospital_id"],
                    **mr_data,
                )
                db.add(mr)
            print(f"    -> 病历: {len(mrs)} 条")

            # ── 添加就诊记录 ──
            vrs = VISIT_RECORDS.get(code, [])
            for vr_data in vrs:
                vr = VisitRecord(
                    patient_id=p.id,
                    hospital_id=pdata["hospital_id"],
                    **vr_data,
                )
                db.add(vr)
            print(f"    -> 就诊: {len(vrs)} 条")

        db.commit()

        total_mr = sum(len(v) for v in MEDICAL_RECORDS.values())
        total_vr = sum(len(v) for v in VISIT_RECORDS.values())

        print(f"\n{'=' * 60}")
        print(f"[OK] Done! {len(PATIENTS)} patients, {total_mr} medical records, {total_vr} visit records")
        print(f"{'=' * 60}")
        print("\n患者手机号（可用于测试身份识别）：")
        for pdata in PATIENTS:
            print(f"  {pdata['full_name']}: {pdata['phone']}")

    except Exception as e:
        db.rollback()
        print(f"\n[FAIL] Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
