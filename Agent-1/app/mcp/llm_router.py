import json
import os
import re
from collections import Counter
from typing import Any, Callable, Dict, List, Optional, Sequence

from fastapi import HTTPException, status

from app.mcp.config import get_llm
from app.mcp.drug_interaction import (
    append_interaction_warnings,
    check_all_interactions,
)
from app.mcp.hallucination_guard import apply_hallucination_check
from app.mcp.schemas import MCPRiskSignals
from app.mcp.server import mcp_server
from app.mcp.vision import analyze_image_with_llm


MEDICAL_DISCLAIMER = (
    "\n\n---\n"
    "⚕️ 免责声明：以上内容仅供参考，不构成医疗诊断或治疗建议。"
    "如有健康问题，请咨询专业医疗机构。"
)

MEDICAL_INTENTS_FOR_DISCLAIMER = {
    "medical_records_query",
    "symptom_consultation",
    "general_medical_question",
}

EMERGENCY_SYMPTOMS = {
    "胸痛": "疑似心绞痛/心肌梗死",
    "呼吸困难": "疑似呼吸系统急症",
    "剧烈头痛": "疑似脑血管意外",
    "意识模糊": "疑似神经系统急症",
    "大量出血": "疑似消化道出血/外伤",
    "高热不退": "疑似严重感染",
    "抽搐": "疑似癫痫/脑部病变",
    "晕厥": "疑似心血管急症",
    "剧烈腹痛": "疑似急腹症",
    "严重过敏": "疑似过敏性休克",
}

EMERGENCY_KEYWORDS = list(EMERGENCY_SYMPTOMS.keys())

LATEST_KEYWORDS = ["最近一次", "最新一次", "最近的", "最后一次", "最近一条", "最近那次"]
VISIT_KEYWORDS = [
    "就诊", "挂号", "看过哪个科", "医生", "上次看病", "复诊",
    "门诊", "急诊", "住院", "出院", "转诊", "会诊",
    "看医生", "看大夫", "找医生", "随访", "复查",
    "就医", "诊疗", "看诊", "问诊",
]
MEDICAL_KEYWORDS = [
    "病历", "病史", "诊断", "治疗", "用药记录", "检查单", "检验单", "报告",
    "检查结果", "化验单", "影像", "CT", "MRI", "X光", "B超", "彩超",
    "心电图", "血常规", "尿常规", "病理", "体检",
    "治疗方案", "手术记录", "出院小结", "入院记录",
    "诊断证明", "疾病证明", "医疗记录",
]
IDENTITY_KEYWORDS = []
PROFILE_KEYWORDS = [
    "画像", "总结", "概况", "整体", "汇总", "档案",
    "个人信息", "个人资料", "基本信息", "我的情况",
    "健康档案", "健康摘要", "病史摘要",
]
ADDRESS_KEYWORDS = ["住址", "地址", "家庭住址", "现住址", "居住地", "所在地"]
SYMPTOM_KEYWORDS = [
    # 头部
    "头晕", "头痛", "头昏", "眩晕", "偏头痛",
    # 心血管
    "血压高", "血压偏高", "血压", "高血压", "低血压",
    "胸闷", "心慌", "心悸", "胸痛", "心绞痛",
    "心跳快", "心跳慢", "心律不齐",
    # 呼吸
    "咳嗽", "咳痰", "气喘", "呼吸困难", "气短", "气促",
    "咽喉痛", "咽痛", "鼻塞", "流鼻涕",
    # 消化
    "腹痛", "胃痛", "肚子痛", "腹胀", "腹泻", "便秘",
    "恶心", "呕吐", "反酸", "烧心", "打嗝",
    "食欲差", "没胃口", "消化不良",
    # 全身
    "发热", "发烧", "发冷", "寒战", "乏力", "没劲",
    "酸痛", "肌肉痛", "关节痛", "背痛", "腰痛",
    "腿痛", "膝盖痛", "肩膀痛", "颈椎痛",
    # 皮肤
    "皮疹", "瘙痒", "红肿", "发疹", "过敏",
    # 神经/精神
    "失眠", "睡不着", "多梦", "焦虑", "烦躁",
    "麻木", "手脚麻", "抽筋", "抽搐",
    # 其他
    "水肿", "浮肿", "消瘦", "体重下降", "体重增加",
    "出汗", "盗汗", "耳鸣", "视力模糊",
    # 通用咨询
    "疼", "难受", "不舒服", "症状", "怎么办", "怎么处理",
    "注意什么", "需要做什么", "严重吗", "要紧吗",
    "有没有大问题", "要不要去医院",
]
ALLERGY_KEYWORDS = [
    "过敏", "过敏史", "药物过敏", "食物过敏",
    "青霉素", "头孢", "磺胺", "阿司匹林",
    "过敏反应", "过敏感",
]
SURGERY_KEYWORDS = [
    "手术", "开刀", "切除", "置换", "移植",
    "术后", "术前", "手术史", "外科",
]
MEDICATION_KEYWORDS = [
    "用药", "药物", "服药", "吃药", "药怎么用",
    "medication", "medicine", "drug",
    "什么药", "哪些药", "药量", "剂量",
    "怎么吃", "怎么服", "怎么用", "服法", "用法",
    "频次", "频率", "几片", "几粒", "几次",
    "一天几次", "饭前", "饭后", "空腹",
    "停药", "减量", "加量", "换药",
]
MEMORY_NOTE_KEYWORDS = [
    "记住这个情况",
    "先记住",
    "帮我记",
    "帮我记录",
    "记一个",
    "记录一下",
    "请记住",
    "把这个记住",
    "作为背景",
    "以后按这个来",
    "后面按这个来",
    "后续按这个来",
]
MEMORY_RECALL_KEYWORDS = [
    "我刚刚问你什么",
    "我刚才问你什么",
    "我刚刚说了什么",
    "我刚才说了什么",
    "前面说了什么",
    "之前说了什么",
    "是不是跟你说过",
    "有没有说过",
    "记得我说过",
    "还记得我说过",
    "记得我刚才说",
]

PATIENT_BOUND_TOOLS = {"get_medical_records", "get_visit_records", "get_patient_profile"}
INTENT_TOOL_HINTS = {
    "visit_records_query": ["get_visit_records"],
    "medical_records_query": ["get_medical_records"],
    "symptom_consultation": ["get_medical_records", "get_visit_records", "get_patient_profile"],
    "patient_profile_summary": ["get_patient_profile", "get_visit_records", "get_medical_records"],
    "multimodal_summary": ["get_patient_profile", "get_medical_records", "get_visit_records"],
    "general_medical_question": [],
    "conversation_memory_note": [],
    "conversation_memory_recall": [],
}

MAX_CANDIDATE_PLANS = 2
MAX_REACT_STEPS = 2

def _format_medical_records_summary(data: Dict[str, Any]) -> str:
    records = data.get("medical_records") or []
    if not records:
        return "没有查到可用的病历记录。"
    latest = records[0]
    return f"最近病历诊断：{latest.get('diagnosis') or '未填写'}"


def _format_visit_records_summary(data: Dict[str, Any]) -> str:
    records = data.get("visit_records") or []
    if not records:
        return "没有查到可用的就诊记录。"
    latest = records[0]
    visit_date = latest.get("visit_date") or "未知时间"
    department = latest.get("department") or "未知科室"
    return f"最近就诊：{visit_date}，{department}"


def _format_patient_profile_summary(data: Dict[str, Any]) -> str:
    patient = data.get("patient") or {}
    medical_records = data.get("medical_records") or []
    visit_records = data.get("visit_records") or []
    patient_name = patient.get("full_name") or "未知患者"
    address = patient.get("address") or "未填写"
    phone = patient.get("phone") or "未填写"
    allergy_history = patient.get("allergy_history") or "未填写"
    family_history = patient.get("family_history") or "未填写"
    notes = patient.get("notes") or "未填写"
    return (
        f"患者: {patient_name} | 住址: {address} | 电话: {phone} | "
        f"过敏史: {allergy_history} | 家族史: {family_history} | 备注: {notes} | "
        f"已汇总 {len(medical_records)} 条病历和 {len(visit_records)} 条就诊记录。"
    )


def _format_identity_summary(data: Dict[str, Any]) -> str:
    return "身份校验通过。" if data.get("authenticated") else "身份校验未通过。"


TOOL_SUMMARY_FORMATTERS = {
    "verify_identity": _format_identity_summary,
    "get_medical_records": _format_medical_records_summary,
    "get_visit_records": _format_visit_records_summary,
    "get_patient_profile": _format_patient_profile_summary,
}


def _format_visit_records_summary(data: Dict[str, Any]) -> str:
    records = data.get("visit_records") or []
    if not records:
        return "æ²¡æœ‰æŸ¥åˆ°å¯ç”¨çš„å°±è¯Šè®°å½•ã€‚"
    latest = records[0]
    visit_date = latest.get("visit_date") or "æœªçŸ¥æ—¶é—´"
    department = latest.get("department") or "æœªçŸ¥ç§‘å®¤"
    doctor_name = latest.get("doctor_name") or "æœªè®°å½•åŒ»ç”Ÿ"
    return f"æœ€è¿‘å°±è¯Šï¼š{visit_date}ï¼Œ{department}ï¼Œå°±è¯ŠåŒ»ç”Ÿæ˜¯ {doctor_name}"


TOOL_SUMMARY_FORMATTERS["get_visit_records"] = _format_visit_records_summary


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            item.get("text", "") if isinstance(item, dict) else str(item)
            for item in content
        )
    return str(content)


def _invoke_text_prompt(llm, prompt: str) -> str:
    response = llm.invoke(prompt)
    return _content_to_text(response.content).strip()


def _extract_json_object(text: str) -> Dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("LLM did not return a JSON object")
    return json.loads(text[start : end + 1])


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_limit(value: Any, default: int, minimum: int = 1, maximum: int = 20) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(number, maximum))


def _strip_markdown_for_speech(text: str) -> str:
    cleaned = (text or "").strip()
    cleaned = re.sub(r"```[\s\S]*?```", " ", cleaned)
    cleaned = re.sub(r"`([^`]*)`", r"\1", cleaned)
    cleaned = re.sub(r"^#{1,6}\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\*\*(.*?)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"\*(.*?)\*", r"\1", cleaned)
    cleaned = re.sub(r"^>\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^[-*+]\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\d+\.\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\n+", "\n", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    return cleaned.strip()


def _looks_like_single_latest(question: str) -> bool:
    normalized = (question or "").strip()
    return any(keyword in normalized for keyword in LATEST_KEYWORDS)


def _looks_like_symptom_consult(question: str) -> bool:
    normalized = (question or "").strip()
    return any(keyword in normalized for keyword in SYMPTOM_KEYWORDS)


def _looks_like_medication_follow_up(question: str) -> bool:
    normalized = (question or "").strip().lower()
    return any(keyword in normalized for keyword in ["用药", "药物", "服药", "吃药", "药怎么用", "medication", "medicine", "drug"])


def _looks_like_medication_dose_question(question: str) -> bool:
    normalized = (question or "").strip().lower()
    if not normalized:
        return False
    dose_keywords = ["怎么吃", "怎么服", "怎么用", "服法", "用法", "剂量", "频次", "频率", "几片", "几粒", "几次", "一天几次", "一天几片", "饭前", "饭后", "空腹", "多久吃", "多久服"]
    if any(keyword in normalized for keyword in dose_keywords):
        return True
    return False


def _looks_like_visit_doctor_question(question: str) -> bool:
    normalized = (question or "").strip()
    return any(keyword in normalized for keyword in ["å°±è¯ŠåŒ»ç”Ÿ", "æŽ¥è¯ŠåŒ»ç”Ÿ", "åŒ»ç”Ÿæ˜¯è°", "çœ‹ç—…åŒ»ç”Ÿ", "ä½ çš„åŒ»ç”Ÿ"])


def _format_visit_records_summary(data: Dict[str, Any]) -> str:
    records = data.get("visit_records") or []
    if not records:
        return "æ²¡æœ‰æŸ¥åˆ°å¯ç”¨çš„å°±è¯Šè®°å½•ã€‚"
    latest = records[0]
    visit_date = latest.get("visit_date") or "æœªçŸ¥æ—¶é—´"
    department = latest.get("department") or "æœªçŸ¥ç§‘å®¤"
    doctor_name = latest.get("doctor_name") or "æœªè®°å½•åŒ»ç”Ÿ"
    return f"æœ€è¿‘å°±è¯Šï¼š{visit_date}ï¼Œ{department}ï¼Œå°±è¯ŠåŒ»ç”Ÿæ˜¯ {doctor_name}"


def _looks_like_memory_note(question: str) -> bool:
    normalized = (question or "").strip()
    return bool(normalized) and any(keyword in normalized for keyword in MEMORY_NOTE_KEYWORDS)


def _looks_like_memory_recall_question(question: str) -> bool:
    normalized = (question or "").strip()
    return bool(normalized) and any(keyword in normalized for keyword in MEMORY_RECALL_KEYWORDS)


def _is_memory_meta_question(text: str) -> bool:
    normalized = (text or "").strip()
    return bool(normalized) and (_looks_like_memory_note(normalized) or _looks_like_memory_recall_question(normalized))


def _normalize_memory_fact(text: str) -> str:
    normalized = (text or "").strip()
    normalized = re.sub(r"^(先记住|帮我记住|帮我记录|请记住|记录一下|记住一下|把这个记住|作为背景)", "", normalized).strip()
    normalized = re.sub(r"^(我最近|最近|刚刚|刚才)\s*", "", normalized).strip()
    normalized = re.sub(r"[，。；、\s]+$", "", normalized).strip()
    return normalized or (text or "").strip()


def _extract_user_and_assistant_messages(conversation_context: Optional[str]) -> Dict[str, List[str]]:
    user_messages: List[str] = []
    assistant_messages: List[str] = []
    for raw_line in (conversation_context or "").splitlines():
        line = raw_line.strip()
        lower = line.lower()
        if lower.startswith("user:"):
            content = line.split(":", 1)[1].strip()
            if content:
                user_messages.append(content)
        elif lower.startswith("assistant:"):
            content = line.split(":", 1)[1].strip()
            if content:
                assistant_messages.append(content)
    return {"user_messages": user_messages, "assistant_messages": assistant_messages}


def _clip_text(value: str, *, max_chars: int = 120) -> str:
    text = (value or "").strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "..."


def _extract_salient_user_facts(conversation_context: Optional[str]) -> List[str]:
    messages = _extract_user_and_assistant_messages(conversation_context)["user_messages"]
    facts: List[str] = []
    for message in messages:
        if _looks_like_memory_note(message):
            candidate = _normalize_memory_fact(message)
            if candidate:
                facts.append(candidate)
            continue
        if _looks_like_symptom_consult(message) or _looks_like_medication_follow_up(message):
            facts.append(_clip_text(message, max_chars=80))
    return list(dict.fromkeys([item for item in facts if item]))[-4:]


def _extract_recent_context_snippets(conversation_context: Optional[str]) -> Dict[str, str]:
    extracted = _extract_user_and_assistant_messages(conversation_context)
    user_messages = extracted["user_messages"]
    facts = _extract_salient_user_facts(conversation_context)
    lines = [line.strip() for line in (conversation_context or "").splitlines() if line.strip()]
    recent_user = ""
    recent_assistant = ""
    for line in reversed(lines):
        lower = line.lower()
        if not recent_assistant and lower.startswith("assistant:"):
            recent_assistant = line.split(":", 1)[1].strip()
            continue
        if not recent_user and lower.startswith("user:"):
            recent_user = line.split(":", 1)[1].strip()
        if recent_user and recent_assistant:
            break
    return {
        "recent_user": recent_user,
        "recent_assistant": recent_assistant,
        "previous_user": user_messages[-2] if len(user_messages) >= 2 else "",
        "remembered_user_fact": facts[-1] if facts else "",
    }


def _build_conversation_context_hint(conversation_context: Optional[str]) -> Optional[str]:
    snippets = _extract_recent_context_snippets(conversation_context)
    recent_user = snippets["recent_user"]
    recent_assistant = snippets["recent_assistant"]
    previous_user = snippets.get("previous_user", "")
    remembered_user_fact = snippets.get("remembered_user_fact", "")
    if not recent_user and not recent_assistant and not remembered_user_fact:
        return None

    parts = ["这是同一轮对话的后续。"]
    if remembered_user_fact:
        parts.append(f"已记住的短期事实：{_clip_text(remembered_user_fact)}")
    if recent_user:
        if _looks_like_memory_note(recent_user):
            parts.append(f"上一轮已记录的背景：{_clip_text(recent_user)}")
        else:
            parts.append(f"上一轮用户话题：{_clip_text(recent_user)}")
    elif previous_user:
        parts.append(f"上一轮用户话题：{_clip_text(previous_user)}")
    if recent_assistant:
        parts.append(f"上一轮助手回复：{_clip_text(recent_assistant)}")
    return "\n".join(parts)


def _extract_identity_hint(question: str) -> Dict[str, str]:
    text = (question or "").strip()
    if not text:
        return {}

    relation_patterns = [
        ("self", [r"我自己", r"本人", r"我本人", r"我自?己"]),
        ("mother", [r"我妈", r"妈妈", r"母亲", r"我母亲"]),
        ("father", [r"我爸", r"爸爸", r"父亲", r"我父亲"]),
        ("partner", [r"爱人", r"配偶", r"另一半", r"对象"]),
        ("child", [r"孩子", r"儿子", r"女儿", r"宝宝"]),
        ("family", [r"家人", r"家里老人", r"老人", r"亲属"]),
    ]
    for label, patterns in relation_patterns:
        for pattern in patterns:
            if re.search(pattern, text):
                return {"type": "relation", "value": label}

    stopwords = {"医生", "医院", "患者", "病历", "报告", "检查", "结果", "这次", "上次", "今天", "昨天", "刚刚", "目前", "现在"}
    name_patterns = [
        r"(?:帮我(?:查|看|找|确认|查询)|查询|看看|查一下)?(?:一下)?([\u4e00-\u9fff]{2,4})(?:的)?(?:病历|报告|检查|就诊|复诊|记录)",
        r"([\u4e00-\u9fff]{2,4})(?:的)?(?:上次|最近|最新)?(?:病历|报告|检查|就诊|复诊|记录)",
    ]
    for pattern in name_patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        candidate = (match.group(1) or "").strip()
        candidate = re.sub(r"(看看|查询|查一下|帮我|一下)$", "", candidate).strip()
        if candidate and candidate not in stopwords:
            return {"type": "name", "value": candidate}
    return {}


def _extract_identity_key_points(question: str) -> List[str]:
    text = (question or "").strip()
    if not text:
        return []

    keyword_groups = [
        ["用药", "吃药", "停药", "继续用药", "降压药", "胰岛素"],
        ["检查", "报告", "化验", "复查", "指标", "结果"],
        ["头晕", "头痛", "胸闷", "心慌", "咳嗽", "发热", "血压", "血糖", "血脂"],
        ["就诊", "门诊", "复诊", "住院", "挂号", "医生"],
    ]

    points: List[str] = []
    for group in keyword_groups:
        for keyword in group:
            if keyword in text and keyword not in points:
                points.append(keyword)
    return points[:3]


def _looks_like_patient_specific_question(question: str) -> bool:
    normalized = (question or "").strip()
    if not normalized:
        return False
    if re.search(r"(我最近|我这几天|我现在|我的症状|我头晕|我血压|我吃药|我用药|我该不该|我还能不能|我这种情况|按我情况|我上次|上次|之前|继续|还要不要|后续治疗|下一步|怎么治疗|怎么处理|要不要治疗|怎么干预|怎么调整|复查|随访)", normalized):
        return True
    if re.search(r"(我的|我家|我妈|我爸|我父|我母|家属|本人).*(病历|检查|报告|复诊|用药|停药|换药|症状|结果)", normalized):
        return True
    if re.search(r"(病历|检查|报告|复诊|用药|停药|换药|症状|结果).*(我的|我家|我妈|我爸|我父|我母|家属|本人)", normalized):
        return True
    return False
def _needs_identity_for_question(question: str, intent: str) -> bool:
    return False


def _should_answer_directly_without_identity(question: str, image_analysis: Optional[str] = None) -> bool:
    return True


def _has_historical_context(question: str) -> bool:
    """Detect if question is about past/historical data rather than current symptoms."""
    normalized = (question or "").strip()
    historical = ["之前", "以前", "过去", "曾", "曾经", "既往", "旧", "老毛病",
                   "history", "previous", "past", "before", "上次", "上回",
                   "原有的", "原有的", "原有的"]
    return any(kw in normalized for kw in historical)


def _fallback_intent(question: str, image_analysis: Optional[str] = None) -> Dict[str, Any]:
    normalized = (question or "").strip()
    has_historical = _has_historical_context(normalized)
    is_symptom = _looks_like_symptom_consult(normalized)
    is_visit = any(kw in normalized for kw in VISIT_KEYWORDS)
    is_medical = any(kw in normalized for kw in MEDICAL_KEYWORDS)
    is_profile = any(kw in normalized for kw in PROFILE_KEYWORDS)
    is_address = any(kw in normalized for kw in ADDRESS_KEYWORDS)
    is_allergy = any(kw in normalized for kw in ALLERGY_KEYWORDS)
    is_surgery = any(kw in normalized for kw in SURGERY_KEYWORDS)
    is_medication = _looks_like_medication_follow_up(normalized)
    is_image = bool(image_analysis)

    # ── 多意图融合 ──
    matched_categories = []
    if is_symptom: matched_categories.append("symptom")
    if is_visit: matched_categories.append("visit")
    if is_medical: matched_categories.append("medical")
    if is_profile: matched_categories.append("profile")
    if is_address: matched_categories.append("address")
    if is_allergy: matched_categories.append("allergy")
    if is_surgery: matched_categories.append("surgery")
    if is_medication: matched_categories.append("medication")

    intent = "general_medical_question"
    focus = ["general medical advice"]

    if is_address:
        intent = "patient_profile_summary"
        focus = ["address", "profile", "patient master record"]
    elif is_allergy:
        intent = "medical_records_query"
        focus = ["allergy", "medical record", "safety"]
    elif is_surgery and has_historical:
        matched_count = len(matched_categories)
        if matched_count >= 2:
            intent = "patient_profile_summary"
            focus = ["surgery", "medical records", "visits", "summary"]
        else:
            intent = "medical_records_query"
            focus = ["surgery", "operation", "medical record"]
    elif is_medication and has_historical:
        intent = "medical_records_query"
        focus = ["medication", "record", "treatment"]
    elif is_medication and not has_historical:
        intent = "symptom_consultation"
        focus = ["medication", "consultation", "symptom"]
    elif is_visit and is_medical:
        intent = "patient_profile_summary"
        focus = ["medical records", "visits", "summary"]
    elif is_visit and is_symptom and has_historical:
        intent = "visit_records_query"
        focus = ["visit history", "symptom", "past visit"]
    elif is_profile:
        intent = "patient_profile_summary"
        focus = ["profile", "records", "summary"]
    elif is_visit:
        intent = "visit_records_query"
        focus = ["recent visit", "department", "doctor"]
    elif is_medical:
        intent = "medical_records_query"
        focus = ["record", "diagnosis", "treatment"]
    elif is_surgery:
        intent = "medical_records_query"
        focus = ["surgery", "operation"]
    elif is_symptom:
        if has_historical:
            intent = "medical_records_query"
            focus = ["symptom history", "medical record", "past visit"]
        else:
            intent = "symptom_consultation"
            focus = ["symptom", "risk", "next step"]
    elif is_image:
        intent = "multimodal_summary"
        focus = ["image", "patient context", "reminder"]

    return {
        "intent": intent,
        "confidence": 0.55,
        "latest_only": _looks_like_single_latest(normalized),
        "needs_identity_verification": False,
        "requires_multimodal_reasoning": bool(image_analysis),
        "reasoning_summary": f"Fallback intent selected from keywords. Matched: {', '.join(matched_categories) or 'none'}. Historical: {has_historical}.",
        "focus": focus,
    }


def _normalize_intent_result(
    raw: Dict[str, Any],
    *,
    question: str,
    image_analysis: Optional[str],
) -> Dict[str, Any]:
    fallback = _fallback_intent(question, image_analysis=image_analysis)
    intent = str(raw.get("intent") or fallback["intent"]).strip()
    if intent not in INTENT_TOOL_HINTS:
        intent = fallback["intent"]
    normalized_question = (question or "").strip()
    if any(keyword in normalized_question for keyword in ADDRESS_KEYWORDS):
        intent = "patient_profile_summary"
        fallback["focus"] = ["address", "profile", "patient master record"]

    focus = raw.get("focus")
    if not isinstance(focus, list):
        focus = fallback["focus"]
    focus = [str(item).strip() for item in focus if str(item).strip()][:4] or fallback["focus"]

    confidence = _safe_float(raw.get("confidence"), fallback["confidence"])
    confidence = max(0.0, min(confidence, 1.0))

    return {
        "intent": intent,
        "confidence": confidence,
        "latest_only": bool(raw.get("latest_only", fallback["latest_only"])),
        "needs_identity_verification": bool(raw.get("needs_identity_verification", fallback["needs_identity_verification"])),
        "requires_multimodal_reasoning": bool(raw.get("requires_multimodal_reasoning", fallback["requires_multimodal_reasoning"])),
        "reasoning_summary": str(raw.get("reasoning_summary") or fallback["reasoning_summary"]).strip(),
        "focus": focus,
    }


def _identify_intent(
    llm,
    *,
    question: str,
    enriched_question: str,
    image_analysis: Optional[str],
    auth_token: Optional[str],
    patient_id: Optional[str],
    hospital_id: Optional[str],
) -> Dict[str, Any]:
    fallback = _fallback_intent(question, image_analysis=image_analysis)

    # Only short-circuit for very clear-cut cases, let LLM handle ambiguity
    normalized_question = (question or "").strip()
    if not normalized_question:
        return fallback

    # Clear address queries → skip LLM
    if any(keyword in normalized_question for keyword in ADDRESS_KEYWORDS):
        return fallback

    prompt = f"""你是一个医疗对话意图分类器。分析用户问题，输出 JSON。

允许的 intent:
- visit_records_query     — 查询就诊记录、挂号、医生、科室
- medical_records_query   — 查询病历、诊断、检查结果、治疗、用药
- symptom_consultation    — 当前症状咨询、注意事项、严重程度
- patient_profile_summary — 总结/概况患者全部信息
- multimodal_summary      — 图片/化验单分析
- general_medical_question— 普通医疗知识问题
- uncertain               — 如果无法确定，输出此值

示例:
问题: "我上次看病的医生是谁？"
{{"intent": "visit_records_query", "confidence": 0.95, "focus": ["visit history", "doctor"], "reasoning_summary": "明显是查询就诊记录"}}

问题: "我的体检报告有问题吗？"
{{"intent": "medical_records_query", "confidence": 0.92, "focus": ["medical report", "examination"], "reasoning_summary": "查询检查报告"}}

问题: "我最近血压高，怎么办？"
{{"intent": "symptom_consultation", "confidence": 0.9, "focus": ["blood pressure", "symptom", "advice"], "reasoning_summary": "当前症状咨询"}}

问题: "高血压患者饮食注意什么？"
{{"intent": "general_medical_question", "confidence": 0.95, "focus": ["general medical advice", "diet"], "reasoning_summary": "通用医疗知识，不涉及个人数据"}}

问题: "帮我总结一下我的病历和就诊情况"
{{"intent": "patient_profile_summary", "confidence": 0.93, "focus": ["profile", "summary", "records"], "reasoning_summary": "需要聚合所有信息"}}

规则:
- 问题涉及个人就诊/病历记录 → visit_records_query 或 medical_records_query
- 问题关于"怎么办""严不严重"且提到症状 → symptom_consultation
- 问题要求总结/概况患者信息 → patient_profile_summary
- 问题不含个人数据、仅问一般医学知识 → general_medical_question
- 不确定时输出 uncertain

问题: {question}
补充信息: {enriched_question or '无'}
图片: {'有' if image_analysis else '无'}
患者已绑定: {'是' if patient_id else '否'}
"""
    try:
        raw = _extract_json_object(_invoke_text_prompt(llm, prompt))
        intent = str(raw.get("intent") or "")
        # If LLM is uncertain, fall back to keyword-based
        if intent == "uncertain":
            return fallback
        return _normalize_intent_result(raw, question=question, image_analysis=image_analysis)
    except Exception:
        return fallback


def _tool_names_from_steps(steps: Sequence[Dict[str, Any]]) -> List[str]:
    return [step.get("tool_name", "") for step in steps if step.get("tool_name")]


def _build_default_plan_candidates(question: str, *, intent_state: Dict[str, Any]) -> List[Dict[str, Any]]:
    intent = intent_state["intent"]
    latest_only = bool(intent_state.get("latest_only"))
    if False:
        return []
    if intent == "visit_records_query":
        return [
            {
                "plan_id": "visit_records",
                "confidence": 0.88,
                "reasoning_summary": "Fetch visit records directly.",
                "steps": [{"tool_name": "get_visit_records", "arguments": {"limit": 1 if latest_only else 10}, "purpose": "Fetch visit records"}],
            }
        ]
    if intent == "medical_records_query":
        return [
            {
                "plan_id": "medical_records",
                "confidence": 0.88,
                "reasoning_summary": "Fetch medical records directly.",
                "steps": [{"tool_name": "get_medical_records", "arguments": {"limit": 1 if latest_only else 10}, "purpose": "Fetch medical records"}],
            }
        ]
    if intent in {"patient_profile_summary", "symptom_consultation", "multimodal_summary"}:
        return [
            {
                "plan_id": "profile_summary",
                "confidence": 0.84,
                "reasoning_summary": "Use the aggregated profile for context.",
                "steps": [
                    {
                        "tool_name": "get_patient_profile",
                        "arguments": {"medical_record_limit": 1 if latest_only else 10, "visit_limit": 1 if latest_only else 10},
                        "purpose": "Fetch aggregated profile",
                    }
                ],
            }
        ]
    return []


def _generate_plan_candidates(
    llm,
    *,
    question: str,
    enriched_question: str,
    tools: List[Dict[str, Any]],
    intent_state: Dict[str, Any],
    auth_token: Optional[str],
    patient_id: Optional[str],
    hospital_id: Optional[str],
    image_analysis: Optional[str],
) -> List[Dict[str, Any]]:
    intent = intent_state["intent"]
    default_candidates = _build_default_plan_candidates(question, intent_state=intent_state)
    if default_candidates:
        return default_candidates
    prompt = f"""
You are a planner for a patient assistant agent.
Return a JSON array with 1 to 2 candidate plans.

Question: {question}
Enriched question: {enriched_question}
Intent state: {json.dumps(intent_state, ensure_ascii=False)}
Image summary: {image_analysis or "none"}
Auth token: {'yes' if auth_token else 'no'}
Patient id: {patient_id or 'none'}
Hospital id: {hospital_id or 'none'}
Available tools: {json.dumps(tools, ensure_ascii=False, indent=2)}
"""
    try:
        raw = json.loads(_invoke_text_prompt(llm, prompt))
        if not isinstance(raw, list):
            raise ValueError("plan candidates must be a list")
    except Exception:
        return default_candidates

    normalized: List[Dict[str, Any]] = []
    allowed_tool_names = {tool_name for names in INTENT_TOOL_HINTS.values() for tool_name in names}
    for index, candidate in enumerate(raw[:MAX_CANDIDATE_PLANS]):
        if not isinstance(candidate, dict):
            continue
        steps = candidate.get("steps")
        if not isinstance(steps, list):
            continue
        normalized_steps: List[Dict[str, Any]] = []
        for raw_step in steps[:MAX_REACT_STEPS]:
            if not isinstance(raw_step, dict):
                continue
            tool_name = str(raw_step.get("tool_name") or "").strip()
            if tool_name not in allowed_tool_names:
                continue
            arguments = raw_step.get("arguments") if isinstance(raw_step.get("arguments"), dict) else {}
            normalized_steps.append(
                {
                    "tool_name": tool_name,
                    "arguments": _apply_question_constraints(question, tool_name, arguments, latest_only=bool(intent_state.get("latest_only"))),
                    "purpose": str(raw_step.get("purpose") or "Collect the next required piece of information.").strip(),
                }
            )
        if not normalized_steps:
            continue
        normalized.append(
            {
                "plan_id": str(candidate.get("plan_id") or f"candidate_{index + 1}").strip(),
                "confidence": max(0.0, min(_safe_float(candidate.get("confidence"), 0.55), 1.0)),
                "reasoning_summary": str(candidate.get("reasoning_summary") or "Plan candidate generated from the current intent.").strip(),
                "steps": normalized_steps,
            }
        )
    return normalized or default_candidates


def _select_consensus_plan(candidates: List[Dict[str, Any]], intent_state: Dict[str, Any]) -> Dict[str, Any]:
    if not candidates:
        return {"plan_id": "empty", "confidence": 0.0, "reasoning_summary": "No candidate plan.", "steps": []}
    sequence_counter = Counter(">".join(_tool_names_from_steps(candidate["steps"])) for candidate in candidates)
    first_tool_counter = Counter(candidate["steps"][0]["tool_name"] for candidate in candidates if candidate.get("steps"))
    expected_tools = set(INTENT_TOOL_HINTS.get(intent_state["intent"], []))

    best_candidate = candidates[0]
    best_score = float("-inf")
    for candidate in candidates:
        tool_names = _tool_names_from_steps(candidate["steps"])
        sequence_key = ">".join(tool_names)
        first_tool = tool_names[0] if tool_names else ""
        confidence = _safe_float(candidate.get("confidence"), 0.6)
        overlap_bonus = 0.2 if expected_tools.intersection(tool_names[:2]) else 0.0
        consensus_score = confidence + sequence_counter[sequence_key] * 0.35 + first_tool_counter[first_tool] * 0.15 + overlap_bonus - max(0, len(tool_names) - 1) * 0.05
        candidate["consensus_score"] = round(consensus_score, 4)
        candidate["tool_sequence"] = tool_names
        if consensus_score > best_score:
            best_score = consensus_score
            best_candidate = candidate
    return best_candidate


def _apply_question_constraints(
    question: str,
    tool_name: str,
    tool_arguments: Dict[str, Any],
    latest_only: Optional[bool] = None,
) -> Dict[str, Any]:
    arguments = dict(tool_arguments)
    latest = _looks_like_single_latest(question) if latest_only is None else latest_only
    if tool_name in {"get_visit_records", "get_medical_records"}:
        arguments["limit"] = _coerce_limit(arguments.get("limit"), 1 if latest else 10)
    elif tool_name == "get_patient_profile":
        default_limit = 1 if latest else 10
        arguments["visit_limit"] = _coerce_limit(arguments.get("visit_limit"), default_limit)
        arguments["medical_record_limit"] = _coerce_limit(arguments.get("medical_record_limit"), default_limit)
    return arguments


def _normalize_tool_result(tool_result: Any) -> Dict[str, Any]:
    if hasattr(tool_result, "model_dump"):
        return tool_result.model_dump()
    if isinstance(tool_result, dict):
        return tool_result
    return {"data": tool_result}


def _summarize_tool_observation(tool_name: str, tool_result: Dict[str, Any]) -> str:
    data = tool_result.get("data") or {}
    formatter = TOOL_SUMMARY_FORMATTERS.get(tool_name)
    if formatter:
        return formatter(data)
    return "工具执行完成。"
def _call_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    tool_result = mcp_server.call_tool(tool_name, arguments)
    return _normalize_tool_result(tool_result)


def _build_focus_from_intent(intent_state: Dict[str, Any]) -> List[str]:
    return list(intent_state.get("focus") or [])


def _build_answer_prompt(
    *,
    question: str,
    intent_state: Dict[str, Any],
    chosen_plan: Dict[str, Any],
    execution_trace: List[Dict[str, Any]],
    latest_tool_name: str,
    latest_tool_result: Dict[str, Any],
    image_analysis: Optional[str],
    conversation_context: Optional[str],
    allergy_drugs: Optional[list[str]] = None,
    allergy_history_unknown: bool = False,
) -> str:
    context_hint = _build_conversation_context_hint(conversation_context) or "none"
    patient_profile_summary = ""
    if latest_tool_name == "get_patient_profile":
        patient_profile_summary = _summarize_tool_observation(latest_tool_name, latest_tool_result)
    allergy_unknown_disclaimer = ""
    if allergy_history_unknown:
        allergy_unknown_disclaimer = (
            "\n回答涉及药物建议时，请给出全面、适当的回答，"
            "自然包含必要的用药提醒（如咨询医生、确认禁忌等）"
            "作为回答行文的一部分，不要以独立提醒块的形式出现。\n"
        )
    allergy_warning = ""
    if allergy_drugs:
        allergy_warning = (
            f"\n患者过敏警告：患者对 {', '.join(allergy_drugs)} 过敏。"
            f"绝不要推荐这些药物或同类药物。"
            f"如果标准治疗包含其中任何药物，必须明确说明患者不能使用并建议替代方案。\n"
        )
    return f"""
你是一个患者智能助手。
请仅用中文给出用户可直接阅读的答案，要求：
1. 不要做正式诊断。
2. 不要给处方或停药指令。
3. 如果信息不足，要明确说信息不够。
4. 如果用户是在追问上一轮，请延续上下文，不要重新开场。
5. 不要提内部计划、工具、JSON。
{allergy_warning}
{allergy_unknown_disclaimer}
问题: {question}
连续性提示: {context_hint}
意图: {intent_state['intent']}
关注点: {json.dumps(_build_focus_from_intent(intent_state), ensure_ascii=False)}
最近限定: {intent_state['latest_only']}
图片摘要: {image_analysis or 'none'}
选择的计划: {json.dumps(chosen_plan, ensure_ascii=False, indent=2)}
执行轨迹: {json.dumps(execution_trace, ensure_ascii=False, indent=2)}
主工具: {latest_tool_name}
主工具结果: {json.dumps(latest_tool_result, ensure_ascii=False, indent=2)}
患者主档摘要: {patient_profile_summary}
"""


def _generate_answer_text(
    llm,
    *,
    question: str,
    intent_state: Dict[str, Any],
    chosen_plan: Dict[str, Any],
    execution_trace: List[Dict[str, Any]],
    latest_tool_name: str,
    latest_tool_result: Dict[str, Any],
    image_analysis: Optional[str],
    conversation_context: Optional[str],
    allergy_drugs: Optional[list[str]] = None,
    allergy_history_unknown: bool = False,
    risk_signals: Optional[MCPRiskSignals] = None,
) -> str:
    prompt = _build_answer_prompt(
        question=question,
        intent_state=intent_state,
        chosen_plan=chosen_plan,
        execution_trace=execution_trace,
        latest_tool_name=latest_tool_name,
        latest_tool_result=latest_tool_result,
        image_analysis=image_analysis,
        conversation_context=conversation_context,
        allergy_drugs=allergy_drugs,
        allergy_history_unknown=allergy_history_unknown,
    )
    intent = intent_state.get("intent", "")
    try:
        answer = _invoke_text_prompt(llm, prompt)
        if answer:
            answer = _check_allergy_safety(answer, allergy_drugs)
            answer = _append_risk_advice(answer, risk_signals)
            # Check drug interactions if medications are available
            medications = _extract_medications_from_data(latest_tool_result)
            if medications:
                interactions = check_all_interactions(medications)
                answer = append_interaction_warnings(answer, interactions)
            # Check for hallucinations
            answer = apply_hallucination_check(
                answer, latest_tool_result, conversation_context,
                strict_mode=True, use_llm_fallback=False,
            )
            answer = _append_medical_disclaimer(answer, intent)
            return _strip_markdown_for_speech(answer)
    except Exception:
        pass

    data = latest_tool_result.get("data") or {}
    if latest_tool_name == "get_visit_records" and data.get("visit_records"):
        latest = data.get("visit_records")[0]
        if _looks_like_visit_doctor_question(question):
            return f"æˆ‘æŸ¥åˆ°ä½ çš„å°±è¯ŠåŒ»ç”Ÿæ˜¯ {latest.get('doctor_name') or 'æœªè®°å½•åŒ»ç”Ÿ'}ã€‚"
    formatter = TOOL_SUMMARY_FORMATTERS.get(latest_tool_name)
    if formatter:
        summary = formatter(data)
        if latest_tool_name == "get_medical_records" and data.get("medical_records"):
            latest = data.get("medical_records")[0]
            diagnosis = latest.get("diagnosis") or "未填写"
            return f"我查到了最近的病历，诊断信息是 {diagnosis}。如果你要继续看用药或复查，需要结合完整病历一起判断。"
        if latest_tool_name == "get_visit_records" and data.get("visit_records"):
            latest = data.get("visit_records")[0]
            return f"我查到了最近一次就诊，时间是 {latest.get('visit_date') or '未知时间'}，科室是 {latest.get('department') or '未知科室'}。"
        if latest_tool_name == "get_patient_profile":
            medical_records = data.get("medical_records") or []
            visit_records = data.get("visit_records") or []
            return f"我已经汇总了 {len(medical_records)} 条病历和 {len(visit_records)} 条就诊记录。"
        if latest_tool_name == "verify_identity":
            return "身份校验已完成。"
        return summary
    if image_analysis:
        return f"根据图片摘要来看：{image_analysis}"
    return "我已经根据当前信息做了整理，但信息还不够完整。"
def _answer_direct_memory_note(question: str, conversation_context: Optional[str] = None) -> str:
    snippets = _extract_recent_context_snippets(conversation_context)
    source_text = snippets.get("remembered_user_fact") or snippets["recent_user"] or _normalize_memory_fact(question)
    return f"我记住了这个情况：{_clip_text(source_text, max_chars=60)}。后面你继续问用药、复查或症状变化时，我会把它作为背景一起考虑。"


def _answer_direct_memory_recall(question: str, conversation_context: Optional[str] = None) -> str:
    facts = _extract_salient_user_facts(conversation_context)
    snippets = _extract_recent_context_snippets(conversation_context)
    recent_user = snippets.get("recent_user", "")
    if not facts and recent_user and not _is_memory_meta_question(recent_user):
        facts = [_clip_text(_normalize_memory_fact(recent_user), max_chars=80)]
    if not facts:
        return "我还没稳定提炼到可复用的短期事实。你可以直接把要记住的症状、用药或检查结果单独说一遍，我再帮你沉淀。"
    latest_fact = facts[-1]
    if any(keyword in (question or "") for keyword in ["是不是跟你说过", "有没有说过", "记得我说过"]):
        return f"有，你前面提到过“{latest_fact}”。"
    if any(keyword in (question or "") for keyword in ["刚才问你什么", "前面说了什么", "之前说了什么"]):
        joined = "；".join(facts[-2:] if len(facts) > 1 else facts)
        return f"你前面重点提到的是：{joined}。"
    return f"我记得你前面提到过“{latest_fact}”。"


def _answer_identity_confirmation(question: str, intent: str) -> str:
    return _build_guardrail_reply("identity", question, intent=intent)


def _answer_with_image_only(question: str, image_analysis: str) -> str:
    if _looks_like_single_latest(question):
        return f"结合图片里能看到的信息，当前最明确的重点是：{image_analysis}"
    return f"结合你上传的图片，我先提取到这些关键信息：{image_analysis}"


def _answer_symptom_without_records(question: str) -> str:
    return _build_guardrail_reply("symptom", question)


def _answer_general_medical_question(question: str) -> str:
    return _build_guardrail_reply("general_medical", question)


def _build_guardrail_reply(kind: str, question: str, intent: Optional[str] = None) -> str:
    normalized = (question or "").strip()
    if kind == "identity":
        return "目前无法判断，需要你补充个人信息。"
    if kind == "symptom":
        if any(keyword in normalized for keyword in ["血压", "头晕", "胸闷", "心慌"]):
            return "你提到的症状里有头晕和血压偏高这类情况，先记录最近血压变化、发作时间和是否伴随胸闷或恶心。若头晕明显加重、血压持续很高，或出现胸痛、肢体无力、说话不清，请尽快就医。"
        return "你描述的更像是在咨询当前症状和下一步处理。先留意症状持续时间、诱因和是否加重，如果症状明显或反复，建议尽快线下就医确认。"
    if kind == "general_medical":
        return "目前无法判断，需要你补充个人信息。"
    return "目前无法判断，需要你补充个人信息。"


def _needs_personal_info_via_llm(
    llm,
    *,
    question: str,
    intent: str,
    image_analysis: Optional[str],
    conversation_context: Optional[str],
) -> bool:
    context_hint = _build_conversation_context_hint(conversation_context) or "none"
    prompt = f"""
你是一个医疗对话路由器，只输出 JSON。

判断用户当前问题是否需要先补充个人信息再回答。

输出格式：
{{"needs_personal_info": true/false, "reason": "一句话原因"}}

判定为 true 的情况：
- 问的是某个具体人的情况，包括本人、家属、患者、这次报告、这张图片、后续处理、后续治疗、下一步怎么办、怎么处理、怎么治疗、复查、随访、用药调整、症状变化
- 回答需要结合病史、检查结果、病历、图片或具体对象信息

判定为 false 的情况：
- 纯医学常识、概念、机制、一般性建议
- 不依赖某个具体人的病情、检查或图片就能回答的问题

注意：
- 图片只作为上下文，不要因为“有图片”就自动判为 true
- 如果问题明显是在问具体对象的后续处理，就判为 true

问题：{question}
意图：{intent}
连续性提示：{context_hint}
图片摘要：{image_analysis or "none"}
"""
    try:
        raw = _extract_json_object(_invoke_text_prompt(llm, prompt))
        return bool(raw.get("needs_personal_info", False))
    except Exception:
        return False


def _generate_open_answer(
    llm,
    *,
    question: str,
    image_analysis: Optional[str] = None,
    conversation_context: Optional[str] = None,
) -> str:
    context_hint = _build_conversation_context_hint(conversation_context) or "none"
    medication_hint = ""
    if _looks_like_medication_dose_question(question) or any(keyword in (question or "") for keyword in ["用药", "药物", "吃药"]):
        medication_hint = """
结尾直接给安全提醒，不要写成“请告诉我……”或“以下是需要明确的信息”这种提示式开头。
"""
    prompt = f"""
你是一个中文医疗助手。
请直接回答用户问题，不要提工具、计划、JSON 或内部流程。
要求：
1. 如果问题不是针对某个具体患者，就直接给出自然、具体、可读的完整回答，不要刻意压短。
2. 优先把结论、原因、注意点、下一步和必要的边界说完整，长度由内容决定。
3. 如果问题涉及图片，请自然结合图片摘要。
4. 如果信息不足，要明确说明信息不足，但不要只回“信息不够”；同时说明还差哪些关键点。
5. 不要做正式诊断，不要输出空泛套话。
{medication_hint}

问题：{question}
连续性提示：{context_hint}
图片摘要：{image_analysis or 'none'}
"""
    answer = _invoke_text_prompt(llm, prompt)
    return answer or "目前无法判断，需要你补充个人信息。"


def _needs_personal_info_v2(
    llm,
    *,
    question: str,
    intent: str,
    image_analysis: Optional[str],
    conversation_context: Optional[str],
) -> bool:
    context_hint = _build_conversation_context_hint(conversation_context) or "none"
    prompt_context = _build_prompt_context_block(conversation_context, max_chars=1400)
    prompt = f"""
You are a medical dialogue router. Output JSON only.

Decide whether the user must provide more personal information before the assistant can answer.

Output format:
{{"needs_personal_info": true/false, "reason": "one sentence"}}

Return true when:
- the question is about a specific person's current condition, report, image, follow-up treatment, medication adjustment, symptom change, review, or next step
- the answer depends on missing patient-specific medical history, test results, or identity

Return false when:
- the question can be answered as general medical information
- the context already includes confirmed identity, long-term memory profile, key events, or stable patient background
- the context already contains enough patient-specific information to answer naturally

Question: {question}
Intent: {intent}
Context hint: {context_hint}
Full context: {prompt_context}
Image summary: {image_analysis or "none"}
"""
    try:
        raw = _extract_json_object(_invoke_text_prompt(llm, prompt))
        return bool(raw.get("needs_personal_info", False))
    except Exception:
        return False


def _check_allergy_safety(answer: str, allergy_drugs: Optional[list[str]]) -> str:
    """Scan the generated answer for the patient's allergy drugs.

    If any allergy drug is mentioned in the answer, inject a prominent
    safety warning reminding about the patient's known allergy.
    """
    if not allergy_drugs or not answer:
        return answer
    answer_lower = answer.lower()
    triggered: list[str] = []
    for drug in allergy_drugs:
        if drug.lower() in answer_lower:
            triggered.append(drug)
    if not triggered:
        return answer
    drug_list = "、".join(triggered)
    warning = (
        f"\n\n---\n"
        f"⚠️ **安全提醒**：系统检测到回答中提到了 **{drug_list}**。"
        f"根据患者档案，患者对该药物**已知过敏**。"
        f"请在用药前务必确认患者的过敏史，避免使用过敏药物。"
    )
    return answer + warning


def _detect_emergency_symptoms(answer: str) -> list[str]:
    """Detect emergency symptoms in the answer text."""
    detected = []
    for keyword, description in EMERGENCY_SYMPTOMS.items():
        if keyword in answer:
            detected.append(f"{keyword}（{description}）")
    return detected


def _append_risk_advice(answer: str, risk_signals: Optional[MCPRiskSignals]) -> str:
    """Append medical safety advice to the answer when risk signals are detected.

    - Emergency symptoms: urgent referral with prominent warning
    - Red flags (胸痛, 呼吸困难, etc.): urgent medical consultation advice
    - Medication flags (停药, 漏服, etc.): medication safety reminder
    - Monitoring flags alone do NOT trigger additional advice (routine follow-up)

    The advice blends into the assistant's conversational tone — no separator line,
    no system-style warning markers.
    """
    if not answer or not risk_signals:
        return answer

    red = [item for item in (risk_signals.red_flags or []) if item]
    med = [item for item in (risk_signals.medication_flags or []) if item]

    if not red and not med:
        return answer

    lines: list[str] = []

    if red:
        emergency_detected = _detect_emergency_symptoms(answer)
        if emergency_detected:
            emergency_list = "、".join(emergency_detected)
            lines.append(
                f"🚨 **紧急提醒**：你描述的症状包含 {emergency_list}，"
                f"这些可能是危及生命的急症。请立即拨打120急救电话或尽快前往最近的急诊科就诊，不要延误！"
            )
        else:
            red_list = "、".join(red[:4])
            lines.append(
                f"另外，你提到的{red_list}是需要重视的信号，"
                f"建议尽快去医院让医生看一下，别单靠线上咨询来判断。"
            )

    if med:
        med_list = "、".join(med[:4])
        lines.append(
            f"还有，关于{med_list}这件事，用药方面最好不要自己调整，"
            f"先问问主治医生的意见更稳妥。"
        )

    if lines:
        return answer.rstrip() + "\n\n" + "\n".join(lines)

    return answer


def _append_medical_disclaimer(answer: str, intent: str) -> str:
    """Append medical disclaimer for medical-related intents."""
    if not answer or intent not in MEDICAL_INTENTS_FOR_DISCLAIMER:
        return answer
    if "免责声明" in answer:
        return answer
    return answer + MEDICAL_DISCLAIMER


def _extract_medications_from_data(tool_result: Dict[str, Any]) -> list[str]:
    """Extract medication list from tool result data."""
    medications = []
    data = tool_result.get("data") or {}
    
    # Check medical records for medications
    medical_records = data.get("medical_records") or []
    for record in medical_records:
        meds_text = record.get("medications") or ""
        if meds_text:
            # Split by common delimiters and clean up
            for med in re.split(r'[,，、;；\n]+', meds_text):
                med = med.strip()
                if med and len(med) > 1 and len(med) < 30:
                    medications.append(med)
    
    # Deduplicate while preserving order
    seen = set()
    unique_meds = []
    for med in medications:
        if med not in seen:
            seen.add(med)
            unique_meds.append(med)
    
    return unique_meds[:10]  # Limit to 10 medications


def _calculate_answer_confidence(
    intent: str,
    latest_tool_name: str,
    latest_tool_result: Dict[str, Any],
    has_image: bool = False,
    has_conversation_context: bool = False,
) -> tuple[float, str]:
    """Calculate answer confidence based on available data sources.
    
    Returns:
        (confidence, reason) tuple
    """
    confidence = 0.5
    reasons = []
    
    data = latest_tool_result.get("data") or {}
    
    if latest_tool_name == "get_medical_records":
        medical_records = data.get("medical_records") or []
        if medical_records:
            confidence = 0.9
            reasons.append(f"有{len(medical_records)}条病历数据支撑")
        else:
            confidence = 0.4
            reasons.append("病历查询无结果")
    elif latest_tool_name == "get_visit_records":
        visit_records = data.get("visit_records") or []
        if visit_records:
            confidence = 0.85
            reasons.append(f"有{len(visit_records)}条就诊记录支撑")
        else:
            confidence = 0.4
            reasons.append("就诊记录查询无结果")
    elif latest_tool_name == "get_patient_profile":
        confidence = 0.8
        reasons.append("有患者档案数据支撑")
    elif latest_tool_name == "direct_model_answer":
        if intent == "general_medical_question":
            confidence = 0.6
            reasons.append("通用医疗知识回答")
        elif has_image:
            confidence = 0.7
            reasons.append("有图片信息补充")
        elif has_conversation_context:
            confidence = 0.65
            reasons.append("有对话上下文支撑")
        else:
            confidence = 0.5
            reasons.append("无数据支撑的直接回答")
    else:
        confidence = 0.6
        reasons.append(f"基于工具{latest_tool_name}的回答")
    
    if "信息不够" in str(latest_tool_result.get("message", "")):
        confidence = min(confidence, 0.4)
        reasons.append("信息不足")
    
    return round(confidence, 2), "；".join(reasons)


def _generate_open_answer_v2(
    llm,
    *,
    question: str,
    image_analysis: Optional[str] = None,
    conversation_context: Optional[str] = None,
    allergy_drugs: Optional[list[str]] = None,
    allergy_history_unknown: bool = False,
    risk_signals: Optional[MCPRiskSignals] = None,
    intent: str = "",
) -> str:
    prompt_context = _build_prompt_context_block(conversation_context, max_chars=2200)
    context_hint = _build_conversation_context_hint(conversation_context) or "none"
    medication_hint = ""
    if _looks_like_medication_dose_question(question) or any(keyword in (question or "") for keyword in ["ç”¨è¯", "è¯ç‰©", "åƒè¯"]):
        medication_hint = """
If medication details are insufficient, explain what is missing inside the answer itself.
Do not use a questionnaire style opening.
Do not invent specific dosage instructions.
"""
    allergy_unknown_disclaimer = ""
    if allergy_history_unknown:
        allergy_unknown_disclaimer = (
            "When your response includes medication-related advice, "
            "make sure the answer is comprehensive and appropriate — naturally include "
            "necessary precautions (e.g., consult a doctor, check contraindications) "
            "as part of the response flow, not as a separate warning block.\n"
        )
    allergy_warning = ""
    if allergy_drugs:
        allergy_warning = (
            f"PATIENT ALLERGY WARNING: The patient is allergic to: {', '.join(allergy_drugs)}. "
            f"NEVER recommend or suggest these drugs or any drugs in the same class. "
            f"If a standard treatment would normally involve any of these drugs, "
            f"clearly state that the patient cannot use them due to allergy and suggest alternatives.\n"
        )
    prompt = f"""
You are a Chinese medical assistant with persistent memory about the user.

GENERAL BEHAVIOR:
- Answer in Chinese
- Use the provided conversation context as recent dialogue memory when relevant
- Do not mention tools, routing, JSON, or system design
- Keep the answer natural and direct

STYLE:
- Prefer: conclusion -> reasoning -> caution -> suggestion
- Avoid questionnaire style openings unless more info is genuinely required

MEDICAL SAFETY:
- Do not give diagnosis
- Do not invent dosage
- If info insufficient, explain what is missing
- Always check patient allergy history before mentioning any drug

{allergy_warning}
{allergy_unknown_disclaimer}
{medication_hint}


Question: {question}
Context hint: {context_hint}
Full context: {prompt_context}
Image summary: {image_analysis or "none"}
"""
    answer = _invoke_text_prompt(llm, prompt)
    answer = _check_allergy_safety(answer, allergy_drugs)
    answer = _append_risk_advice(answer, risk_signals)
    answer = _append_medical_disclaimer(answer, intent)
    return answer or "ç›®å‰–æ— æ³•åˆ¤æ–­ï¼Œéœ€è¦ä½è¡¥å……ä¸ªäººä¿¡æ¯ã€‚"


def _execute_plan_steps(
    *,
    question: str,
    intent_state: Dict[str, Any],
    chosen_plan: Dict[str, Any],
    auth_token: Optional[str],
    patient_id: Optional[str],
    hospital_id: Optional[str],
) -> Dict[str, Any]:
    steps = list(chosen_plan.get("steps") or [])
    if not steps:
        return {
            "chosen_tool": "direct_answer",
            "tool_arguments": {},
            "tool_result": {"tool_name": "direct_answer", "success": True, "data": {}, "message": "ok"},
            "chosen_tools": ["direct_answer"],
            "execution_trace": [],
            "finish_reasoning": "Answered directly without tool execution.",
        }

    execution_trace: List[Dict[str, Any]] = []
    chosen_tools: List[str] = []
    latest_tool_name = "direct_answer"
    latest_tool_arguments: Dict[str, Any] = {}
    latest_tool_result: Dict[str, Any] = {"tool_name": "direct_answer", "success": True, "data": {}, "message": "ok"}
    finish_reasoning = "Completed the query flow based on the chosen plan."

    for step in steps[:MAX_REACT_STEPS]:
        tool_name = step["tool_name"]
        arguments = dict(step.get("arguments") or {})
        if tool_name in PATIENT_BOUND_TOOLS:
            if auth_token:
                arguments.setdefault("auth_token", auth_token)
            if patient_id:
                arguments.setdefault("patient_id", patient_id)
            if hospital_id:
                arguments.setdefault("hospital_id", hospital_id)
        if tool_name == "verify_identity" and auth_token:
            arguments.setdefault("auth_token", auth_token)
        try:
            tool_result = _call_tool(tool_name, arguments)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"MCP tool execution failed: {exc}") from exc

        chosen_tools.append(tool_name)
        latest_tool_name = tool_name
        latest_tool_arguments = arguments
        latest_tool_result = tool_result
        observation_summary = _summarize_tool_observation(tool_name, tool_result)
        execution_trace.append(
            {
                "step": len(execution_trace) + 1,
                "reasoning_summary": step.get("purpose") or "Run the planned step.",
                "tool_name": tool_name,
                "arguments": arguments,
                "purpose": step.get("purpose") or "Run the planned step.",
                "observation_summary": observation_summary,
                "tool_result": tool_result,
            }
        )

    return {
        "chosen_tool": latest_tool_name,
        "tool_arguments": latest_tool_arguments,
        "tool_result": latest_tool_result,
        "chosen_tools": chosen_tools,
        "execution_trace": execution_trace,
        "finish_reasoning": finish_reasoning,
    }


def _has_confirmed_identity_context(auth_token: Optional[str], patient_id: Optional[str]) -> bool:
    return False


def _has_claimed_identity_context(
    claimed_name: Optional[str],
    claimed_phone: Optional[str],
    claimed_birth_year: Optional[int],
) -> bool:
    return False



def _build_enriched_question(question: str, image_analysis: Optional[str], conversation_context: Optional[str] = None) -> str:
    parts = [question.strip()]
    context_hint = _build_conversation_context_hint(conversation_context)
    if context_hint:
        parts.append(f"Conversation continuity hint:\n{context_hint}")
    if image_analysis:
        parts.append(f"Image context: {image_analysis}")
    return "\n\n".join(part for part in parts if part)


def _build_prompt_context_block(conversation_context: Optional[str], *, max_chars: int = 2200) -> str:
    text = (conversation_context or "").strip()
    if not text:
        return "none"
    if len(text) <= max_chars:
        return text
    head = text[: int(max_chars * 0.7)].rstrip()
    tail = text[-int(max_chars * 0.3) :].lstrip()
    return f"{head}\n...\n{tail}"


def _select_direct_path(
    *,
    llm,
    question: str,
    intent_state: Dict[str, Any],
    image_analysis: Optional[str],
    conversation_context: Optional[str],
    auth_token: Optional[str],
    patient_id: Optional[str],
    claimed_name: Optional[str] = None,
    claimed_phone: Optional[str] = None,
    claimed_birth_year: Optional[int] = None,
    confirmed_patient_name: Optional[str] = None,
    allergy_drugs: Optional[list[str]] = None,
    allergy_history_unknown: bool = False,
    risk_signals: Optional[MCPRiskSignals] = None,
) -> Optional[Dict[str, Any]]:
    intent = intent_state["intent"]
    if intent in {"visit_records_query", "medical_records_query", "patient_profile_summary"}:
        return None
    if _looks_like_memory_note(question):
        answer = _answer_direct_memory_note(question, conversation_context=conversation_context)
        return {
            "question": question,
            "answer": answer,
            "speech_text": _strip_markdown_for_speech(answer),
            "image_analysis": image_analysis,
            "intent": "conversation_memory_note",
            "intent_confidence": 0.98,
            "planning_strategy": "memory_note_direct_answer",
            "chosen_tool": "memory_note_direct_answer",
            "chosen_tools": ["memory_note_direct_answer"],
            "tool_arguments": {},
            "tool_result": {"tool_name": "memory_note_direct_answer", "success": True, "data": {"note": question}, "message": "ok"},
            "execution_trace": [],
            "planning": {"intent_reasoning": "Detected a memory note.", "focus": ["memory", "continuity"], "latest_only": False, "candidates": [], "chosen_plan": {"plan_id": "memory_note_direct_answer", "steps": []}},
        }
    if _looks_like_memory_recall_question(question):
        answer = _answer_direct_memory_recall(question, conversation_context=conversation_context)
        return {
            "question": question,
            "answer": answer,
            "speech_text": _strip_markdown_for_speech(answer),
            "image_analysis": image_analysis,
            "intent": "conversation_memory_recall",
            "intent_confidence": 0.98,
            "planning_strategy": "memory_recall_direct_answer",
            "chosen_tool": "memory_recall_direct_answer",
            "chosen_tools": ["memory_recall_direct_answer"],
            "tool_arguments": {},
            "tool_result": {"tool_name": "memory_recall_direct_answer", "success": True, "data": {"facts": _extract_salient_user_facts(conversation_context)}, "message": "ok"},
            "execution_trace": [],
            "planning": {"intent_reasoning": "Detected a memory recall question.", "focus": ["memory", "continuity"], "latest_only": False, "candidates": [], "chosen_plan": {"plan_id": "memory_recall_direct_answer", "steps": []}},
        }
    confirmed_identity = True
    claimed_identity = False
    needs_personal_info = False
    if not confirmed_identity and not claimed_identity:
        needs_personal_info = _needs_personal_info_v2(
            llm,
            question=question,
            intent=intent,
            image_analysis=image_analysis,
            conversation_context=conversation_context,
        )
    if False:
        answer = _answer_identity_confirmation(question, intent)
        return {
            "question": question,
            "answer": answer,
            "speech_text": _strip_markdown_for_speech(answer),
            "image_analysis": image_analysis,
            "intent": intent,
            "intent_confidence": intent_state["confidence"],
            "planning_strategy": "identity_confirmation_needed",
            "chosen_tool": "identity_confirmation_needed",
            "chosen_tools": ["identity_confirmation_needed"],
            "tool_arguments": {},
            "tool_result": {"tool_name": "identity_confirmation_needed", "success": True, "data": {"identity_status": "unconfirmed"}, "message": "identity confirmation required"},
            "execution_trace": [],
            "planning": {"intent_reasoning": intent_state["reasoning_summary"], "focus": _build_focus_from_intent(intent_state), "latest_only": intent_state["latest_only"], "candidates": [], "chosen_plan": {"plan_id": "identity_confirmation_needed", "steps": []}},
        }

    answer = _generate_open_answer_v2(llm, question=question, image_analysis=image_analysis, conversation_context=conversation_context, allergy_drugs=allergy_drugs, allergy_history_unknown=allergy_history_unknown, risk_signals=risk_signals, intent=intent)
    confidence, confidence_reason = _calculate_answer_confidence(
        intent=intent,
        latest_tool_name="direct_model_answer",
        latest_tool_result={"tool_name": "direct_model_answer", "success": True, "data": {"source": "direct_model_answer"}, "message": "ok"},
        has_image=bool(image_analysis),
        has_conversation_context=bool(conversation_context),
    )
    return {
        "question": question,
        "answer": answer,
        "speech_text": _strip_markdown_for_speech(answer),
        "image_analysis": image_analysis,
        "intent": intent,
        "intent_confidence": intent_state["confidence"],
        "planning_strategy": "direct_model_answer",
        "chosen_tool": "direct_model_answer",
        "chosen_tools": ["direct_model_answer"],
        "tool_arguments": {},
        "tool_result": {"tool_name": "direct_model_answer", "success": True, "data": {"source": "direct_model_answer"}, "message": "ok"},
        "execution_trace": [],
        "planning": {"intent_reasoning": intent_state["reasoning_summary"], "focus": _build_focus_from_intent(intent_state), "latest_only": intent_state["latest_only"], "candidates": [], "chosen_plan": {"plan_id": "direct_model_answer", "steps": []}},
        "answer_confidence": confidence,
        "confidence_reason": confidence_reason,
    }
def run_agent_tool_query(
    question: str,
    auth_token: Optional[str] = None,
    patient_id: Optional[str] = None,
    hospital_id: Optional[str] = None,
    chat_mode: Optional[str] = None,
    claimed_name: Optional[str] = None,
    claimed_phone: Optional[str] = None,
    claimed_birth_year: Optional[int] = None,
    confirmed_patient_name: Optional[str] = None,
    image_bytes: Optional[bytes] = None,
    image_content_type: Optional[str] = None,
    image_filename: Optional[str] = None,
    conversation_context: Optional[str] = None,
    allergy_drugs: Optional[list[str]] = None,
    allergy_history_unknown: bool = False,
    risk_signals: Optional[MCPRiskSignals] = None,
) -> Dict[str, Any]:
    try:
        llm = get_llm()
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    normalized_chat_mode = (chat_mode or "").strip().lower()
    image_analysis = None
    if image_bytes:
        try:
            image_analysis = analyze_image_with_llm(
                question=question,
                image_bytes=image_bytes,
                content_type=image_content_type,
                filename=image_filename,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    if normalized_chat_mode == "general":
        answer = _generate_open_answer_v2(
            llm,
            question=question,
            image_analysis=image_analysis,
            conversation_context=conversation_context,
            allergy_drugs=allergy_drugs,
            allergy_history_unknown=allergy_history_unknown,
            risk_signals=risk_signals,
            intent="general_chat",
        )
        speech_text = _strip_markdown_for_speech(answer)
        confidence, confidence_reason = _calculate_answer_confidence(
            intent="general_chat",
            latest_tool_name="direct_model_answer",
            latest_tool_result={"tool_name": "direct_model_answer", "success": True, "data": {"source": "general_direct_answer"}, "message": "ok"},
            has_image=bool(image_analysis),
            has_conversation_context=bool(conversation_context),
        )
        return {
            "question": question,
            "answer": answer,
            "speech_text": speech_text,
            "image_analysis": image_analysis,
            "intent": "general_chat",
            "intent_confidence": 1.0,
            "planning_strategy": "general_direct_answer",
            "chosen_tool": "direct_model_answer",
            "chosen_tools": ["direct_model_answer"],
            "tool_arguments": {},
            "tool_result": {"tool_name": "direct_model_answer", "success": True, "data": {"source": "general_direct_answer"}, "message": "ok"},
            "execution_trace": [],
            "planning": {
                "intent_reasoning": "General chat mode bypassed tool routing.",
                "focus": [],
                "latest_only": False,
                "candidates": [],
                "chosen_plan": {"plan_id": "general_direct_answer", "steps": []},
                "finish_reasoning": "Answered directly in general chat mode.",
            },
            "answer_confidence": confidence,
            "confidence_reason": confidence_reason,
        }

    intent_state = _identify_intent(
        llm,
        question=question,
        enriched_question=_build_enriched_question(question, image_analysis, conversation_context=conversation_context),
        image_analysis=image_analysis,
        auth_token=auth_token,
        patient_id=patient_id,
        hospital_id=hospital_id,
    )

    direct = _select_direct_path(
        llm=llm,
        question=question,
        intent_state=intent_state,
        image_analysis=image_analysis,
        conversation_context=conversation_context,
        auth_token=auth_token,
        patient_id=patient_id,
        claimed_name=claimed_name,
        claimed_phone=claimed_phone,
        claimed_birth_year=claimed_birth_year,
        confirmed_patient_name=confirmed_patient_name,
        allergy_drugs=allergy_drugs,
        allergy_history_unknown=allergy_history_unknown,
        risk_signals=risk_signals,
    )
    if direct is not None:
        return direct

    tools = [tool.model_dump() for tool in mcp_server.list_tools() if tool.name != "issue_identity_token"]
    plan_candidates = _generate_plan_candidates(
        llm,
        question=question,
        enriched_question=_build_enriched_question(question, image_analysis, conversation_context=conversation_context),
        tools=tools,
        intent_state=intent_state,
        auth_token=auth_token,
        patient_id=patient_id,
        hospital_id=hospital_id,
        image_analysis=image_analysis,
    )
    chosen_plan = _select_consensus_plan(plan_candidates, intent_state)
    execution = _execute_plan_steps(
        question=question,
        intent_state=intent_state,
        chosen_plan=chosen_plan,
        auth_token=auth_token,
        patient_id=patient_id,
        hospital_id=hospital_id,
    )

    try:
        answer = _generate_answer_text(
            llm,
            question=question,
            intent_state=intent_state,
            chosen_plan=chosen_plan,
            execution_trace=execution["execution_trace"],
            latest_tool_name=execution["chosen_tool"],
            latest_tool_result=execution["tool_result"],
            image_analysis=image_analysis,
            conversation_context=conversation_context,
            allergy_drugs=allergy_drugs,
            allergy_history_unknown=allergy_history_unknown,
            risk_signals=risk_signals,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"回答生成失败，请检查 LLM 配置后重试: {exc}",
        ) from exc

    speech_text = _strip_markdown_for_speech(answer)
    confidence, confidence_reason = _calculate_answer_confidence(
        intent=intent_state["intent"],
        latest_tool_name=execution["chosen_tool"],
        latest_tool_result=execution["tool_result"],
        has_image=bool(image_analysis),
        has_conversation_context=bool(conversation_context),
    )
    return {
        "question": question,
        "answer": answer,
        "speech_text": speech_text,
        "image_analysis": image_analysis,
        "intent": intent_state["intent"],
        "intent_confidence": intent_state["confidence"],
        "planning_strategy": "intent_plan_then_generate",
        "chosen_tool": execution["chosen_tool"],
        "chosen_tools": execution["chosen_tools"],
        "tool_arguments": execution["tool_arguments"],
        "tool_result": execution["tool_result"],
        "execution_trace": execution["execution_trace"],
        "planning": {
            "intent_reasoning": intent_state["reasoning_summary"],
            "focus": _build_focus_from_intent(intent_state),
            "latest_only": intent_state["latest_only"],
            "candidates": [
                {
                    "plan_id": candidate.get("plan_id"),
                    "confidence": candidate.get("confidence"),
                    "consensus_score": candidate.get("consensus_score"),
                    "reasoning_summary": candidate.get("reasoning_summary"),
                    "tool_sequence": candidate.get("tool_sequence") or _tool_names_from_steps(candidate.get("steps", [])),
                }
                for candidate in plan_candidates
            ],
            "chosen_plan": chosen_plan,
            "finish_reasoning": execution["finish_reasoning"],
        },
        "answer_confidence": confidence,
        "confidence_reason": confidence_reason,
    }


# ============================================================
# Streaming variant — emits phase callbacks for real-time SSE
# ============================================================

PhaseCallback = Callable[[str, str], None]  # (phase, message) -> None


def run_agent_tool_query_stream(
    question: str,
    *,
    on_phase: Optional[PhaseCallback] = None,
    auth_token: Optional[str] = None,
    patient_id: Optional[str] = None,
    hospital_id: Optional[str] = None,
    chat_mode: Optional[str] = None,
    claimed_name: Optional[str] = None,
    claimed_phone: Optional[str] = None,
    claimed_birth_year: Optional[int] = None,
    confirmed_patient_name: Optional[str] = None,
    image_bytes: Optional[bytes] = None,
    image_content_type: Optional[str] = None,
    image_filename: Optional[str] = None,
    conversation_context: Optional[str] = None,
    allergy_drugs: Optional[list[str]] = None,
    allergy_history_unknown: bool = False,
    risk_signals: Optional[MCPRiskSignals] = None,
) -> Dict[str, Any]:
    """Streaming-capable variant of run_agent_tool_query.

    Calls on_phase(phase, message) at each pipeline stage so the caller
    can push real-time SSE events.  The return value is identical to the
    non-streaming version.
    """

    def _emit(phase: str, message: str):
        if on_phase:
            try:
                on_phase(phase, message)
            except Exception:
                pass

    # ── LLM init ──
    _emit("agent", "正在初始化模型...")
    try:
        llm = get_llm()
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    normalized_chat_mode = (chat_mode or "").strip().lower()
    image_analysis = None
    if image_bytes:
        _emit("agent", "正在分析图片...")
        try:
            image_analysis = analyze_image_with_llm(
                question=question,
                image_bytes=image_bytes,
                content_type=image_content_type,
                filename=image_filename,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    # ── General chat short-circuit ──
    if normalized_chat_mode == "general":
        _emit("agent", "正在生成回答...")
        answer = _generate_open_answer_v2(
            llm,
            question=question,
            image_analysis=image_analysis,
            conversation_context=conversation_context,
            allergy_drugs=allergy_drugs,
            allergy_history_unknown=allergy_history_unknown,
            risk_signals=risk_signals,
            intent="general_chat",
        )
        speech_text = _strip_markdown_for_speech(answer)
        confidence, confidence_reason = _calculate_answer_confidence(
            intent="general_chat",
            latest_tool_name="direct_model_answer",
            latest_tool_result={"tool_name": "direct_model_answer", "success": True, "data": {"source": "general_direct_answer"}, "message": "ok"},
            has_image=bool(image_analysis),
            has_conversation_context=bool(conversation_context),
        )
        return {
            "question": question,
            "answer": answer,
            "speech_text": speech_text,
            "image_analysis": image_analysis,
            "intent": "general_chat",
            "intent_confidence": 1.0,
            "planning_strategy": "general_direct_answer",
            "chosen_tool": "direct_model_answer",
            "chosen_tools": ["direct_model_answer"],
            "tool_arguments": {},
            "tool_result": {"tool_name": "direct_model_answer", "success": True, "data": {"source": "general_direct_answer"}, "message": "ok"},
            "execution_trace": [],
            "planning": {
                "intent_reasoning": "General chat mode bypassed tool routing.",
                "focus": [],
                "latest_only": False,
                "candidates": [],
                "chosen_plan": {"plan_id": "general_direct_answer", "steps": []},
                "finish_reasoning": "Answered directly in general chat mode.",
            },
            "answer_confidence": confidence,
            "confidence_reason": confidence_reason,
        }

    # ── Intent identification ──
    _emit("intent", "正在识别问题意图...")
    intent_state = _identify_intent(
        llm,
        question=question,
        enriched_question=_build_enriched_question(question, image_analysis, conversation_context=conversation_context),
        image_analysis=image_analysis,
        auth_token=auth_token,
        patient_id=patient_id,
        hospital_id=hospital_id,
    )
    _emit("intent", f"意图: {intent_state['intent']}（置信度 {intent_state['confidence']:.0%}）")

    # ── Direct path check ──
    direct = _select_direct_path(
        llm=llm,
        question=question,
        intent_state=intent_state,
        image_analysis=image_analysis,
        conversation_context=conversation_context,
        auth_token=auth_token,
        patient_id=patient_id,
        claimed_name=claimed_name,
        claimed_phone=claimed_phone,
        claimed_birth_year=claimed_birth_year,
        confirmed_patient_name=confirmed_patient_name,
        allergy_drugs=allergy_drugs,
        allergy_history_unknown=allergy_history_unknown,
        risk_signals=risk_signals,
    )
    if direct is not None:
        _emit("agent", "直接生成回答...")
        return direct

    # ── Planning ──
    _emit("planning", "正在规划查询方案...")
    tools = [tool.model_dump() for tool in mcp_server.list_tools() if tool.name != "issue_identity_token"]
    plan_candidates = _generate_plan_candidates(
        llm,
        question=question,
        enriched_question=_build_enriched_question(question, image_analysis, conversation_context=conversation_context),
        tools=tools,
        intent_state=intent_state,
        auth_token=auth_token,
        patient_id=patient_id,
        hospital_id=hospital_id,
        image_analysis=image_analysis,
    )
    chosen_plan = _select_consensus_plan(plan_candidates, intent_state)
    plan_steps = chosen_plan.get("steps") or []
    if plan_steps:
        tool_seq = " → ".join(s.get("tool_name", "") for s in plan_steps)
        _emit("planning", f"方案: {tool_seq}")

    # ── Tool execution ──
    _emit("tool_execution", "正在执行工具查询...")
    execution = _execute_plan_steps(
        question=question,
        intent_state=intent_state,
        chosen_plan=chosen_plan,
        auth_token=auth_token,
        patient_id=patient_id,
        hospital_id=hospital_id,
    )
    if execution.get("chosen_tools") and execution["chosen_tools"] != ["direct_answer"]:
        tool_names = ", ".join(execution["chosen_tools"])
        _emit("tool_execution", f"已完成: {tool_names}")

    # ── Answer generation ──
    _emit("agent", "正在生成回答...")
    try:
        answer = _generate_answer_text(
            llm,
            question=question,
            intent_state=intent_state,
            chosen_plan=chosen_plan,
            execution_trace=execution["execution_trace"],
            latest_tool_name=execution["chosen_tool"],
            latest_tool_result=execution["tool_result"],
            image_analysis=image_analysis,
            conversation_context=conversation_context,
            allergy_drugs=allergy_drugs,
            allergy_history_unknown=allergy_history_unknown,
            risk_signals=risk_signals,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"回答生成失败，请检查 LLM 配置后重试: {exc}",
        ) from exc

    speech_text = _strip_markdown_for_speech(answer)
    confidence, confidence_reason = _calculate_answer_confidence(
        intent=intent_state["intent"],
        latest_tool_name=execution["chosen_tool"],
        latest_tool_result=execution["tool_result"],
        has_image=bool(image_analysis),
        has_conversation_context=bool(conversation_context),
    )
    return {
        "question": question,
        "answer": answer,
        "speech_text": speech_text,
        "image_analysis": image_analysis,
        "intent": intent_state["intent"],
        "intent_confidence": intent_state["confidence"],
        "planning_strategy": "intent_plan_then_generate",
        "chosen_tool": execution["chosen_tool"],
        "chosen_tools": execution["chosen_tools"],
        "tool_arguments": execution["tool_arguments"],
        "tool_result": execution["tool_result"],
        "execution_trace": execution["execution_trace"],
        "planning": {
            "intent_reasoning": intent_state["reasoning_summary"],
            "focus": _build_focus_from_intent(intent_state),
            "latest_only": intent_state["latest_only"],
            "candidates": [
                {
                    "plan_id": candidate.get("plan_id"),
                    "confidence": candidate.get("confidence"),
                    "consensus_score": candidate.get("consensus_score"),
                    "reasoning_summary": candidate.get("reasoning_summary"),
                    "tool_sequence": candidate.get("tool_sequence") or _tool_names_from_steps(candidate.get("steps", [])),
                }
                for candidate in plan_candidates
            ],
            "chosen_plan": chosen_plan,
            "finish_reasoning": execution["finish_reasoning"],
        },
        "answer_confidence": confidence,
        "confidence_reason": confidence_reason,
    }
