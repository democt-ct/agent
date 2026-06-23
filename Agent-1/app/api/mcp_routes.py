import base64
import json
import math
import re
import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.redis_client import (
    get_short_term_memory,
    set_short_term_memory,
    delete_session_cache,
)
from app.mcp.auth import verify_auth_token
from app.mcp.llm_router import run_agent_tool_query
from app.mcp.schemas import (
    MCPActiveEntities,
    MCPAgentQueryRequest,
    MCPAgentQueryResponse,
    MCPIssueTokenRequest,
    MCPRecentMessage,
    MCPSessionState,
    MCPRiskSignals,
    MCPShortTermMemory,
    MCPSpeechRequest,
    MCPSpeechResponse,
    MCPToolCallRequest,
    MCPToolCallResponse,
    MCPToolsResponse,
)
from app.mcp.server import mcp_server, normalize_optional_auth_token
from app.mcp.speech import SpeechSynthesisError, synthesize_speech_with_llm
from app.models.memory_key_event import MemoryKeyEvent
from app.models.memory_business_profile import MemoryBusinessProfile
from app.models.memory_conversation_profile import MemoryConversationProfile
from app.models.memory_user_profile import MemoryUserProfile
from app.models.memory_preference import MemoryPreference
from app.models.patient import Patient
from app.services.patient_service import get_patient, list_medical_records, list_visit_records
from app.services.memory_extraction_service import (
    build_knowledge_context,
    create_conversation_message,
    create_session_buffer_message,
    list_conversation_messages,
    promote_session_buffer_to_patient,
)
from app.services.knowledge_retrieval import get_knowledge_retriever


router = APIRouter(prefix="/api/v1/mcp", tags=["mcp-server"])

SHORT_TERM_ROUND_LIMIT = 5

DRUG_TERMS = [
    "阿司匹林", "氯吡格雷", "缬沙坦", "氨氯地平", "硝苯地平", "美托洛尔", "比索洛尔",
    "阿托伐他汀", "瑞舒伐他汀", "二甲双胍", "奥美拉唑", "布洛芬", "华法林", "达比加群",
]
DRUG_SUFFIXES = ["沙坦", "普利", "洛尔", "地平", "他汀", "双胍", "匹林", "吡格雷"]

SYMPTOM_TERMS = [
    "头痛", "头疼", "头晕", "胸闷", "胸痛", "心慌", "心悸", "气短", "气促", "呼吸困难",
    "发烧", "发热", "咳嗽", "咳痰", "恶心", "呕吐", "腹痛", "胃痛", "肚子痛", "腹泻",
    "便秘", "失眠", "乏力", "皮疹", "瘙痒", "麻木", "晕厥", "咽痛", "鼻塞", "流鼻涕",
    "食欲差", "水肿", "背痛", "腰痛", "肩痛", "膝痛", "腿痛", "手痛", "牙痛", "关节痛",
]

TEST_TERMS = [
    "血常规", "尿常规", "便常规", "心电图", "CT", "MRI", "彩超", "B超", "X光", "胸片",
    "化验", "检查", "报告", "复查", "抽血", "化验单", "超声", "核磁",
]

METRIC_TERMS = ["血压", "血糖", "血氧", "心率", "体温", "脉搏", "收缩压", "舒张压"]

RED_FLAG_TERMS = ["胸痛", "呼吸困难", "晕厥", "意识不清", "抽搐", "呕血", "黑便", "高烧", "突然加重"]
MEDICATION_FLAG_TERMS = ["停药", "漏服", "加量", "减量", "不良反应", "副作用", "重复用药"]
MONITORING_FLAG_TERMS = ["监测", "复查", "随访", "观察", "复诊"]

# 否定词列表 — 检查关键词附近是否存在否定/缓解语义
_NEGATION_WORDS = ["没", "不", "无", "否", "未", "没有", "不是", "不会", "不要", "不能", "不必", "不用", "已缓解", "已好转", "已消失", "好了", "没事"]
_HISTORICAL_WORDS = ["之前", "以前", "过去", "曾", "曾经", "之前有过", "已有", "早就", "原来", "原来有", "既往", "旧病", "老毛病"]


def _has_negation(text: str, term: str, window: int = 15) -> bool:
    """Check if `term` in `text` is negated (否定/缓解) nearby (before or after), respecting clause boundaries."""
    idx = text.find(term)
    if idx < 0:
        return False
    # Check text BEFORE the term
    start = max(0, idx - window)
    prefix = text[start:idx]
    # Check text AFTER the term (for recovery words like "已缓解", "好了")
    end = min(len(text), idx + len(term) + window)
    suffix = text[idx + len(term):end]
    combined = prefix + suffix
    for word in _NEGATION_WORDS:
        if word in combined:
            # Verify no clause-separating punctuation sits between the word and the term
            word_idx = combined.find(word)
            if word_idx < 0:
                continue
            # If word is in prefix: check between word and term
            if word in prefix:
                between = prefix[prefix.find(word) + len(word):]
            else:
                between = suffix[:suffix.find(word)]
            if not any(sep in between for sep in ("，", "。", "！", "？", "；", ";", "但是", "不过", "然而")):
                return True
    return False


def _is_historical(text: str, term: str, window: int = 22) -> bool:
    """Check if `term` is mentioned as historical/previously resolved rather than current."""
    idx = text.find(term)
    if idx < 0:
        return False
    start = max(0, idx - window)
    end = min(len(text), idx + len(term) + window)
    context = text[start:end]
    for marker in _HISTORICAL_WORDS:
        if marker in context:
            return True
    return False


def _allergy_context_active(text: str, window: int = 18) -> bool:
    """Check if '过敏' in text refers to an active allergic reaction (not allergy history)."""
    idx = text.find("过敏")
    if idx < 0:
        return False
    if _has_negation(text, "过敏", window=window):
        return False
    start = max(0, idx - window)
    end = min(len(text), idx + 2 + window)
    context = text[start:end]
    active_markers = ["出现", "起了", "症状", "怎么办", "怎么处理", "反应", "红", "痒", "肿", "呼吸困难", "休克"]
    for marker in active_markers:
        if marker in context:
            return True
    return False


def _has_bp_context(text: str, bp_match: re.Match, window: int = 30) -> bool:
    """Check if a blood-pressure-like number is near a BP indicator AND within physiological range."""
    val1 = int(bp_match.group(1))
    val2 = int(bp_match.group(2))
    # 收缩压 60-250, 舒张压 30-150
    if not (60 <= val1 <= 250 and 30 <= val2 <= 150):
        return False
    start = max(0, bp_match.start() - window)
    end = min(len(text), bp_match.end() + window)
    context = text[start:end]
    bp_indicators = ["血压", "收缩压", "舒张压", "上压", "下压", "高压", "低压"]
    return any(ind in context for ind in bp_indicators)


def _resolve_session_id(session_id: Optional[str]) -> str:
    value = (session_id or "").strip()
    return value or str(uuid.uuid4())


def _normalize_profile_name(value: Optional[str]) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    text = re.sub(r"[，。,.!！？?、\s]+", "", text)
    text = re.sub(r"^(我是|叫|我叫|姓名|名字|本人|家属|患者)[:：]?", "", text)
    text = re.sub(r"^[:：]+", "", text)
    text = re.sub(r"(阿姨|叔叔|大爷|大妈|阿伯|伯伯|姐姐|哥哥|妹妹|弟弟|老师|女士|先生|家属)$", "", text)
    return text.strip()


def _parse_birth_year(text: Optional[str]) -> Optional[int]:
    normalized = (text or "").strip()
    if not normalized:
        return None
    match = re.search(r"(?<!\d)(?P<year>(?:19|20)\d{2})(?=\s*(?:年)?(?:出生|生)?(?:\D|$))", normalized)
    if not match:
        match = re.search(r"(?<!\d)(?P<year>\d{2})(?=\s*(?:年)?(?:出生|生))", normalized)
    if not match:
        return None
    year = match.group("year")
    if len(year) == 4:
        return int(year)
    return 1900 + int(year)


def _extract_profile_claims(text: Optional[str]) -> dict[str, Any]:
    normalized = (text or "").strip()
    if not normalized:
        return {}

    name = None
    for pattern in [
        r"(?:我是|我叫|叫|姓名[:：]?\s*|名字[:：]?\s*|本人[:：]?\s*)(?P<name>[\u4e00-\u9fff·]{1,8}(?:阿姨|叔叔|大爷|大妈|阿伯|伯伯|姐姐|哥哥|妹妹|弟弟|老师|女士|先生|家属)?)",
        r"(?<![\u4e00-\u9fff])(?P<name>[\u4e00-\u9fff·]{2,8}(?:阿姨|叔叔|大爷|大妈|阿伯|伯伯|姐姐|哥哥|妹妹|弟弟|老师|女士|先生|家属)?)(?=[，,。.!！？?\s]|$)",
    ]:
        match = re.search(pattern, normalized)
        if match:
            name = _normalize_profile_name(match.group("name"))
            if name:
                break

    birth_year = _parse_birth_year(normalized)
    phone_match = re.search(r"(?<!\d)(1\d{10})(?!\d)", normalized)
    phone = phone_match.group(1) if phone_match else None

    return {
        "name": name or None,
        "birth_year": birth_year,
        "phone": phone,
    }


def _build_identity_text(*parts: Optional[str]) -> str:
    return "\n\n".join(part.strip() for part in parts if isinstance(part, str) and part.strip())


def _resolve_patient_from_profile_claims(
    db: Session,
    *,
    hospital_id: Optional[str],
    text: Optional[str],
) -> tuple[Optional[str], Optional[str], list[str]]:
    claims = _extract_profile_claims(text)
    name_hint = claims.get("name")
    birth_year = claims.get("birth_year")
    phone = claims.get("phone")

    def _normalize_phone(value: Optional[str]) -> str:
        return re.sub(r"\D+", "", value or "")

    if False:
        candidates = find_patients_by_identity_hint(
            db,
            hospital_id=hospital_id,
            name_hint=name_hint,
            birth_year=birth_year,
            limit=5,
        )
        if phone:
            phone_candidates = [
                patient
                for patient in list_patients(db, hospital_id, phone=phone)
                if _normalize_phone(patient.phone) == _normalize_phone(phone)
            ]
            if phone_candidates:
                if candidates:
                    candidate_ids = {patient.id for patient in candidates}
                    narrowed = [patient for patient in phone_candidates if patient.id in candidate_ids]
                    if narrowed:
                        candidates = narrowed
                    else:
                        candidates = phone_candidates
                else:
                    candidates = phone_candidates
    else:
        query = db.query(Patient).filter(Patient.is_active.is_(True))
        candidates = []
        normalized_hint = _normalize_profile_name(name_hint)
        for patient in query.order_by(Patient.created_at.desc()).all():
            stored_name = _normalize_profile_name(patient.full_name)
            if normalized_hint:
                if stored_name != normalized_hint and normalized_hint not in stored_name and stored_name not in normalized_hint:
                    continue
            if birth_year is not None and (not patient.birth_date or patient.birth_date.year != birth_year):
                continue
            candidates.append(patient)
            if len(candidates) >= 5:
                break
        if phone:
            normalized_phone = _normalize_phone(phone)
            phone_candidates = [patient for patient in query.order_by(Patient.created_at.desc()).all() if _normalize_phone(patient.phone) == normalized_phone]
            if phone_candidates:
                if candidates:
                    candidate_ids = {patient.id for patient in candidates}
                    narrowed = [patient for patient in phone_candidates if patient.id in candidate_ids]
                    if narrowed:
                        candidates = narrowed
                    else:
                        candidates = phone_candidates
                else:
                    candidates = phone_candidates
    if len(candidates) == 1:
        patient = candidates[0]
        return patient.id, patient.hospital_id, []
    return None, None, [patient.id for patient in candidates]


def _merge_conversation_contexts(*parts: Optional[str]) -> Optional[str]:
    merged = []
    seen = set()
    for part in parts:
        value = (part or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        merged.append(value)
    return "\n\n".join(merged) or None


def _parse_allergy_drugs(allergy_history: Optional[str]) -> list[str]:
    """Extract drug names from patient's allergy_history field for safety checks."""
    text = (allergy_history or "").strip()
    if not text:
        return []
    drugs = _extract_drugs(text)
    allergy_pattern = re.findall(r'对?([\u4e00-\u9fffA-Za-z]{1,20}?)(?:过敏)', text)
    for match in allergy_pattern:
        cleaned = match.strip()
        if cleaned and cleaned not in drugs and cleaned not in {'对', '有', '无', '否', '不', '未', '没', '者'}:
            drugs.append(cleaned)
    return _unique_nonempty(drugs)


def _filter_allergy_from_knowledge(context: str, allergy_drugs: list[str]) -> Optional[str]:
    """Remove knowledge lines that mention any of the patient's allergy drugs."""
    if not allergy_drugs:
        return context
    lines = context.split('\n')
    filtered: list[str] = []
    for line in lines:
        safe = True
        for drug in allergy_drugs:
            if drug.lower() in line.lower():
                safe = False
                break
        if safe:
            filtered.append(line)
    result = '\n'.join(filtered).strip()
    return result or None


def _build_knowledge_context_block(question: str, hospital_id: Optional[str], allergy_drugs: Optional[list[str]] = None) -> Optional[str]:
    try:
        from app.core.database import SessionLocal
    except Exception:
        return None

    db = SessionLocal()
    try:
        context = build_knowledge_context(db, query_text=question, hospital_id=hospital_id, limit=3)
        if context and allergy_drugs:
            context = _filter_allergy_from_knowledge(context, allergy_drugs)
        return context
    except Exception:
        return None
    finally:
        db.close()


def _build_long_term_memory_context(db: Session, patient_id: Optional[str], question: Optional[str] = None) -> Optional[str]:
    if not patient_id:
        return None

    blocks: list[str] = []

    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if patient:
        patient_lines = ["Patient Profile:"]
        patient_lines.append(f"- Name: {patient.full_name}")
        if patient.patient_code:
            patient_lines.append(f"- Patient Code: {patient.patient_code}")
        if patient.gender:
            patient_lines.append(f"- Gender: {patient.gender}")
        if patient.birth_date:
            patient_lines.append(f"- Birth Date: {patient.birth_date}")
        if patient.phone:
            patient_lines.append(f"- Phone: {patient.phone}")
        if patient.address:
            patient_lines.append(f"- Address: {patient.address}")
        if patient.emergency_contact_name:
            patient_lines.append(f"- Emergency Contact: {patient.emergency_contact_name}")
        if patient.emergency_contact_phone:
            patient_lines.append(f"- Emergency Contact Phone: {patient.emergency_contact_phone}")
        if patient.blood_type:
            patient_lines.append(f"- Blood Type: {patient.blood_type}")
        if patient.allergy_history:
            patient_lines.append(f"- Allergy History: {_clip_text(patient.allergy_history, 160)}")
        if patient.family_history:
            patient_lines.append(f"- Family History: {_clip_text(patient.family_history, 160)}")
        if patient.notes:
            patient_lines.append(f"- Notes: {_clip_text(patient.notes, 160)}")
        blocks.append("\n".join(patient_lines))

        recent_medical_records = list_medical_records(db, patient.id, limit=3)
        if recent_medical_records:
            medical_lines = ["Recent Medical Records:"]
            for idx, record in enumerate(recent_medical_records, start=1):
                parts = [f"{idx}. {record.record_date or 'unknown date'}"]
                if record.title:
                    parts.append(record.title)
                if record.department:
                    parts.append(record.department)
                if record.diagnosis:
                    parts.append(f"Diagnosis: {_clip_text(record.diagnosis, 120)}")
                if record.treatment_plan:
                    parts.append(f"Plan: {_clip_text(record.treatment_plan, 120)}")
                medical_lines.append(" | ".join(parts))
            blocks.append("\n".join(medical_lines))

        recent_visit_records = list_visit_records(db, patient.id, limit=3)
        if recent_visit_records:
            visit_lines = ["Recent Visit Records:"]
            for idx, record in enumerate(recent_visit_records, start=1):
                parts = [f"{idx}. {record.visit_date or 'unknown date'}"]
                if record.department:
                    parts.append(record.department)
                if record.doctor_name:
                    parts.append(f"Doctor: {record.doctor_name}")
                if record.visit_summary:
                    parts.append(f"Summary: {_clip_text(record.visit_summary, 120)}")
                if record.follow_up_plan:
                    parts.append(f"Follow-up: {_clip_text(record.follow_up_plan, 120)}")
                visit_lines.append(" | ".join(parts))
            blocks.append("\n".join(visit_lines))

    factual_memory_block = _build_patient_factual_memory_block(db, patient_id, question, limit=5)
    if factual_memory_block:
        blocks.append(factual_memory_block)

    business_profile = db.query(MemoryBusinessProfile).filter(MemoryBusinessProfile.patient_id == patient_id).first()
    if business_profile:
        business_lines = ["Long-Term Business Profile:"]
        if business_profile.profile_summary:
            business_lines.append(f"- Summary: {_clip_text(business_profile.profile_summary, 320)}")
        if business_profile.focus_topics:
            business_lines.append(f"- Focus Topics: {_clip_text(business_profile.focus_topics, 220)}")
        if business_profile.risk_focus:
            business_lines.append(f"- Risk Focus: {_clip_text(business_profile.risk_focus, 220)}")
        if business_profile.care_needs:
            business_lines.append(f"- Care Needs: {_clip_text(business_profile.care_needs, 220)}")
        blocks.append("\n".join(business_lines))

    conversation_profile = db.query(MemoryConversationProfile).filter(MemoryConversationProfile.patient_id == patient_id).first()
    if conversation_profile:
        conversation_lines = ["Long-Term Conversation Profile:"]
        if conversation_profile.profile_summary:
            conversation_lines.append(f"- Summary: {_clip_text(conversation_profile.profile_summary, 320)}")
        if conversation_profile.communication_preference:
            conversation_lines.append(f"- Communication Preference: {conversation_profile.communication_preference}")
        if conversation_profile.focus_topics:
            conversation_lines.append(f"- Focus Topics: {_clip_text(conversation_profile.focus_topics, 220)}")
        blocks.append("\n".join(conversation_lines))

    user_profile = db.query(MemoryUserProfile).filter(MemoryUserProfile.patient_id == patient_id).first()
    if user_profile:
        profile_lines = ["Long-Term User Profile:"]
        if user_profile.profile_summary:
            profile_lines.append(f"- Summary: {_clip_text(user_profile.profile_summary, 320)}")
        if user_profile.communication_preference:
            profile_lines.append(f"- Communication Preference: {user_profile.communication_preference}")
        if user_profile.focus_topics:
            profile_lines.append(f"- Focus Topics: {_clip_text(user_profile.focus_topics, 220)}")
        if user_profile.risk_focus:
            profile_lines.append(f"- Risk Focus: {_clip_text(user_profile.risk_focus, 220)}")
        if user_profile.care_needs:
            profile_lines.append(f"- Care Needs: {_clip_text(user_profile.care_needs, 220)}")
        if user_profile.source_summary:
            profile_lines.append(f"- Source Summary: {_clip_text(user_profile.source_summary, 220)}")
        blocks.append("\n".join(profile_lines))

    preference = db.query(MemoryPreference).filter(MemoryPreference.patient_id == patient_id).first()
    if preference:
        preference_lines = ["Long-Term Response Preference:"]
        preference_lines.append(f"- Answer Style: {preference.answer_style}")
        preference_lines.append(f"- Answer Length: {preference.answer_length}")
        preference_lines.append(f"- Tone Style: {preference.tone_style}")
        preference_lines.append(f"- Medical Term Level: {preference.medical_term_level}")
        preference_lines.append(f"- Risk Alert Level: {preference.risk_alert_level}")
        preference_lines.append(f"- Preferred Language: {preference.preferred_language}")
        preference_lines.append(f"- Prefer Summary First: {preference.prefer_summary_first}")
        preference_lines.append(f"- Prefer Step By Step: {preference.prefer_step_by_step}")
        if preference.notes:
            preference_lines.append(f"- Notes: {_clip_text(preference.notes, 220)}")
        blocks.append("\n".join(preference_lines))

    key_events = (
        db.query(MemoryKeyEvent)
        .filter(MemoryKeyEvent.patient_id == patient_id)
        .order_by(MemoryKeyEvent.updated_at.desc(), MemoryKeyEvent.created_at.desc())
        .limit(5)
        .all()
    )
    if key_events:
        event_lines = ["Long-Term Key Events:"]
        for idx, event in enumerate(key_events, start=1):
            event_lines.append(
                f"{idx}. {event.type}: {_clip_text(event.content, 120) or '-'}; impact={event.impact}; priority={event.priority}"
            )
        blocks.append("\n".join(event_lines))

    return "\n\n".join(blocks) or None


def _clip_text(value: Optional[str], limit: int = 160) -> Optional[str]:
    text = (value or "").strip()
    if not text:
        return None
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "..."


def _unique_nonempty(items: list[str]) -> list[str]:
    result = []
    for item in items:
        value = str(item or "").strip()
        if value and value not in result:
            result.append(value)
    return result


def _clip_items(items: list[str], limit: int, item_limit: int) -> list[str]:
    clipped = []
    for item in items:
        text = _clip_text(item, item_limit)
        if text:
            clipped.append(text)
    return _unique_nonempty(clipped)[-limit:]


def _tokenize_memory_query(text: Optional[str]) -> list[str]:
    normalized = re.sub(r"[^\w\u4e00-\u9fff]+", " ", str(text or "").lower())
    raw_tokens = [token.strip() for token in normalized.split() if token.strip()]
    tokens: list[str] = []
    for token in raw_tokens:
        if re.fullmatch(r"[\u4e00-\u9fff]+", token):
            if len(token) <= 3:
                tokens.append(token)
            else:
                tokens.extend(token[i : i + 2] for i in range(len(token) - 1))
                tokens.extend(token[i : i + 3] for i in range(max(0, len(token) - 2)))
        elif len(token) >= 2:
            tokens.append(token)
    return _unique_nonempty(tokens)


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(float(a) * float(b) for a, b in zip(left, right))
    left_norm = math.sqrt(sum(float(a) * float(a) for a in left))
    right_norm = math.sqrt(sum(float(b) * float(b) for b in right))
    if not left_norm or not right_norm:
        return 0.0
    return max(0.0, min(1.0, dot / (left_norm * right_norm)))


def _score_keyword_overlap(query_text: str, candidate_text: str) -> float:
    query_tokens = _tokenize_memory_query(query_text)
    if not query_tokens:
        return 0.0
    haystack = str(candidate_text or "").lower()
    hits = sum(1 for token in query_tokens if token in haystack)
    return min(1.0, hits / max(1.0, len(query_tokens)))


def _recency_score(value: Any) -> float:
    if not value:
        return 0.0
    try:
        timestamp = value
        if isinstance(timestamp, str):
            timestamp = timestamp.replace("Z", "+00:00")
        dt = timestamp if hasattr(timestamp, "timestamp") else None
        if dt is None:
            return 0.0
        delta_days = max(0.0, (datetime.now(dt.tzinfo) - dt).total_seconds() / 86400.0)
    except Exception:
        return 0.0
    if delta_days <= 7:
        return 1.0
    if delta_days <= 30:
        return 0.8
    if delta_days <= 180:
        return 0.5
    return 0.2


def _build_patient_fact_candidates(db: Session, patient_id: str) -> list[dict[str, Any]]:
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        return []

    candidates: list[dict[str, Any]] = []

    def add_fact(text: Optional[str], citation: str, happened_at: Any = None, weight: float = 0.0) -> None:
        normalized = _clip_text(text, 320)
        if not normalized:
            return
        candidates.append(
            {
                "text": normalized,
                "citation": citation,
                "happened_at": happened_at,
                "weight": weight,
            }
        )

    add_fact(f"患者姓名：{patient.full_name}", "患者主档/姓名", patient.updated_at, 0.12)
    add_fact(f"患者编号：{patient.patient_code}", "患者主档/患者编号", patient.updated_at, 0.1)
    add_fact(f"患者性别：{patient.gender}", "患者主档/性别", patient.updated_at, 0.08)
    add_fact(f"患者出生日期：{patient.birth_date}", "患者主档/出生日期", patient.updated_at, 0.08)
    add_fact(f"患者手机号：{patient.phone}", "患者主档/手机号", patient.updated_at, 0.12)
    add_fact(f"患者住址：{patient.address}", "患者主档/住址", patient.updated_at, 0.15)
    add_fact(f"紧急联系人：{patient.emergency_contact_name}", "患者主档/紧急联系人", patient.updated_at, 0.08)
    add_fact(f"紧急联系人电话：{patient.emergency_contact_phone}", "患者主档/紧急联系人电话", patient.updated_at, 0.08)
    add_fact(f"血型：{patient.blood_type}", "患者主档/血型", patient.updated_at, 0.08)
    add_fact(f"过敏史：{patient.allergy_history}", "患者主档/过敏史", patient.updated_at, 0.14)
    add_fact(f"家族史：{patient.family_history}", "患者主档/家族史", patient.updated_at, 0.12)
    add_fact(f"患者备注：{patient.notes}", "患者主档/备注", patient.updated_at, 0.1)

    for record in list_medical_records(db, patient_id, limit=12):
        text_parts = [
            f"病历日期：{record.record_date or 'unknown'}",
            f"标题：{record.title or '未命名病历'}",
            f"类型：{record.record_type or 'unknown'}",
            f"科室：{record.department or '未知科室'}",
            f"医生：{record.doctor_name or '未知医生'}",
            f"主诉：{record.chief_complaint or '未记录'}",
            f"现病史：{record.present_illness or '未记录'}",
            f"诊断：{record.diagnosis or '未记录'}",
            f"治疗方案：{record.treatment_plan or '未记录'}",
            f"用药信息：{record.medications or '未记录'}",
            f"备注：{record.notes or '未记录'}",
        ]
        add_fact("；".join(text_parts), f"病历/{record.title or record.id}", record.record_date or record.updated_at, 0.06)

    for record in list_visit_records(db, patient_id, limit=12):
        text_parts = [
            f"就诊日期：{record.visit_date or 'unknown'}",
            f"就诊类型：{record.visit_type or 'unknown'}",
            f"科室：{record.department or '未知科室'}",
            f"医生：{record.doctor_name or '未知医生'}",
            f"院区：{record.campus or '未知院区'}",
            f"主诉：{record.chief_complaint or '未记录'}",
            f"就诊摘要：{record.visit_summary or '未记录'}",
            f"复诊计划：{record.follow_up_plan or '未记录'}",
            f"状态：{record.visit_status or '未记录'}",
        ]
        add_fact("；".join(text_parts), f"就诊/{record.visit_date or record.id}", record.visit_date or record.updated_at, 0.06)

    key_events = (
        db.query(MemoryKeyEvent)
        .filter(MemoryKeyEvent.patient_id == patient_id)
        .order_by(MemoryKeyEvent.updated_at.desc(), MemoryKeyEvent.created_at.desc())
        .limit(12)
        .all()
    )
    for event in key_events:
        text_parts = [
            f"关键事件类型：{event.type}",
            f"内容：{event.content}",
            f"影响：{event.impact}",
            f"优先级：{event.priority}",
        ]
        if event.evidence:
            text_parts.append(f"证据：{event.evidence}")
        add_fact("；".join(text_parts), f"关键事件/{event.type}", event.event_time or event.updated_at, 0.08)

    return candidates


def _build_patient_factual_memory_block(
    db: Session,
    patient_id: Optional[str],
    question: Optional[str],
    *,
    limit: int = 5,
) -> Optional[str]:
    resolved_patient_id = (patient_id or "").strip()
    resolved_question = (question or "").strip()
    if not resolved_patient_id or not resolved_question:
        return None

    candidates = _build_patient_fact_candidates(db, resolved_patient_id)
    if not candidates:
        return None

    query_embedding: list[float] = []
    embedder = None
    try:
        embedder = get_knowledge_retriever().embedder
        query_embedding = embedder.embed_query(resolved_question)
    except Exception:
        embedder = None

    scored: list[tuple[float, dict[str, Any]]] = []
    for item in candidates:
        keyword_score = _score_keyword_overlap(resolved_question, item["text"])
        vector_score = 0.0
        if embedder and query_embedding:
            try:
                vector_score = _cosine_similarity(query_embedding, embedder.embed_text(item["text"]))
            except Exception:
                vector_score = 0.0
        recency = _recency_score(item.get("happened_at"))
        final_score = 0.58 * vector_score + 0.27 * keyword_score + 0.08 * recency + float(item.get("weight") or 0.0)
        if final_score > 0.03:
            scored.append((final_score, item))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    top_items = [item for _, item in scored[: max(limit, 1)]]
    if not top_items:
        return None

    lines = ["Patient factual memory:"]
    for index, item in enumerate(top_items, start=1):
        lines.append(f"{index}. [{item['citation']}] {item['text']}")
    return "\n".join(lines)


def _summarize_assistant_reply(messages: list[MCPRecentMessage]) -> str:
    latest_assistant = next(
        (
            item.content
            for item in reversed(messages)
            if (item.role or "").strip().lower() == "assistant" and (item.content or "").strip()
        ),
        "",
    )
    return _clip_text(latest_assistant, 120) or ""


def _infer_next_action(intent: str, latest_user: str, open_questions: list[str]) -> str:
    if open_questions:
        return "优先回答当前未解决的问题，并在必要时引用患者事实或长期记忆。"
    if intent in {"patient_profile_summary", "medical_records_query", "visit_records_query"}:
        return "优先读取并引用结构化患者事实，再给出简短总结。"
    if latest_user:
        return f"围绕用户最新问题继续推进：{_clip_text(latest_user, 60) or latest_user}"
    return "继续围绕当前主题完成本轮回答。"


def _infer_memory_focus(intent: str, entities: MCPActiveEntities) -> str:
    if intent in {"patient_profile_summary", "medical_records_query", "visit_records_query"}:
        return "patient_facts_first"
    if entities.drugs or entities.tests or entities.metrics:
        return "patient_facts_then_long_term"
    return "working_memory_then_long_term"


def _build_working_summary(
    latest_user: str,
    intent: str,
    current_topic: str,
    goal: str,
    constraints: list[str],
    confirmed_facts: list[str],
) -> str:
    parts = []
    if latest_user:
        parts.append(f"当前用户问题：{_clip_text(latest_user, 80) or latest_user}")
    if intent:
        parts.append(f"意图：{intent}")
    if current_topic:
        parts.append(f"主题：{current_topic}")
    if goal:
        parts.append(f"目标：{_clip_text(goal, 80) or goal}")
    if constraints:
        parts.append(f"约束：{'; '.join(constraints[:3])}")
    if confirmed_facts:
        parts.append(f"已确认事实：{'; '.join(confirmed_facts[:2])}")
    return " | ".join(parts[:6])


def _merge_session_state(previous: MCPSessionState, current: MCPSessionState) -> MCPSessionState:
    merged = current.model_copy(deep=True)
    merged.identity_status = previous.identity_status or current.identity_status
    merged.claimed_name = previous.claimed_name or current.claimed_name
    merged.claimed_birth_year = previous.claimed_birth_year or current.claimed_birth_year
    merged.confirmed_patient_id = previous.confirmed_patient_id or current.confirmed_patient_id
    merged.confirmed_patient_name = previous.confirmed_patient_name or current.confirmed_patient_name
    merged.identity_source = previous.identity_source or current.identity_source
    merged.identity_candidates = previous.identity_candidates or current.identity_candidates
    return merged


def _build_memory_debug_payload(
    *,
    chat_mode: str,
    question: str,
    conversation_context: Optional[str],
    rendered_short_term_memory: Optional[str],
    long_term_memory_context: Optional[str],
    knowledge_context: Optional[str],
    updated_short_term_memory: MCPShortTermMemory,
) -> dict[str, Any]:
    session_state = updated_short_term_memory.session_state
    long_term_blocks = [block for block in (long_term_memory_context or "").split("\n\n") if block.strip()]
    factual_memory = next((block for block in long_term_blocks if block.startswith("Patient factual memory:")), None)
    long_term_summary_blocks = [
        block
        for block in long_term_blocks
        if not block.startswith("Patient factual memory:")
    ]
    return {
        "chat_mode": chat_mode,
        "question": question,
        "working_memory": {
            "session_state": session_state.model_dump(),
            "active_entities": updated_short_term_memory.active_entities.model_dump(),
            "risk_signals": updated_short_term_memory.risk_signals.model_dump(),
            "recent_messages": [item.model_dump() for item in updated_short_term_memory.recent_messages],
        },
        "memory_layers": {
            "short_term_memory": rendered_short_term_memory,
            "factual_memory": factual_memory,
            "long_term_summary_memory": "\n\n".join(long_term_summary_blocks) or None,
            "knowledge_memory": knowledge_context,
        },
        "context_blocks": {
            "short_term_context": rendered_short_term_memory,
            "long_term_context": long_term_memory_context,
            "knowledge_context": knowledge_context,
            "merged_conversation_context": conversation_context,
        },
    }


def _render_list_block(title: str, items: list[str]) -> Optional[str]:
    cleaned = [str(item).strip() for item in items if str(item).strip()]
    if not cleaned:
        return None
    return f"{title}:\n" + "\n".join(f"- {item}" for item in cleaned)


def _render_short_term_memory_context(memory: Optional[MCPShortTermMemory]) -> Optional[str]:
    if not memory:
        return None

    blocks = []
    if memory.recent_messages:
        lines = []
        for item in memory.recent_messages:
            role = (item.role or "assistant").strip().lower()
            role_label = {"user": "User", "assistant": "Assistant", "system": "System", "tool": "Tool"}.get(role, role.title())
            content = (item.content or "").strip()
            if content:
                lines.append(f"{role_label}: {content}")
        if lines:
            blocks.append("Recent Messages:\n" + "\n".join(lines))

    state = memory.session_state
    state_lines = ["Session State:"]
    if state.intent:
        state_lines.append(f"- Intent: {state.intent}")
    if state.current_topic:
        state_lines.append(f"- Current Topic: {state.current_topic}")
    if state.goal:
        state_lines.append(f"- Goal: {state.goal}")
    if state.working_summary:
        state_lines.append(f"- Working Summary: {state.working_summary}")
    if state.next_action:
        state_lines.append(f"- Next Action: {state.next_action}")
    if state.memory_focus:
        state_lines.append(f"- Memory Focus: {state.memory_focus}")
    if state.last_assistant_summary:
        state_lines.append(f"- Last Assistant Summary: {state.last_assistant_summary}")
    for title, values in [
        ("Constraints", state.constraints),
        ("Confirmed Facts", state.confirmed_facts),
        ("Open Questions", state.open_questions),
    ]:
        block = _render_list_block(title, values)
        if block:
            state_lines.append(block)
    if len(state_lines) > 1:
        blocks.append("\n".join(state_lines))

    entities = memory.active_entities
    entity_lines = ["Active Entities:"]
    for title, values in [
        ("Drugs", entities.drugs),
        ("Symptoms", entities.symptoms),
        ("Tests", entities.tests),
        ("Metrics", entities.metrics),
    ]:
        block = _render_list_block(title, values)
        if block:
            entity_lines.append(block)
    if len(entity_lines) > 1:
        blocks.append("\n".join(entity_lines))

    signals = memory.risk_signals
    signal_lines = ["Risk Signals:"]
    for title, values in [
        ("Red Flags", signals.red_flags),
        ("Medication Flags", signals.medication_flags),
        ("Monitoring Flags", signals.monitoring_flags),
    ]:
        block = _render_list_block(title, values)
        if block:
            signal_lines.append(block)
    if len(signal_lines) > 1:
        blocks.append("\n".join(signal_lines))

    return "\n\n".join(blocks) or None


def _count_short_term_messages(conversation_context: Optional[str]) -> int:
    count = 0
    for line in (conversation_context or "").splitlines():
        normalized = line.strip().lower()
        if normalized.startswith("user:") or normalized.startswith("assistant:") or normalized.startswith("system:"):
            count += 1
    return count


def _count_short_term_messages_from_memory(memory: Optional[MCPShortTermMemory]) -> int:
    if not memory:
        return 0
    return len([item for item in memory.recent_messages if (item.content or "").strip()])


def _normalize_memory_fact(text: Optional[str]) -> Optional[str]:
    text = (text or "").strip()
    if not text:
        return None
    text = re.sub(r"(先帮我记住这个情况|先记住这个情况|帮我记一下|帮我记住|记录一下|记一下|请记住|作为背景|先记住)", "", text)
    text = re.sub(r"[，。；、,\s]+$", "", text).strip()
    return text or None


def _normalize_entity_text(text: str) -> str:
    value = (text or "").strip()
    if not value:
        return ""
    value = re.sub(
        r"^(我想问|我想了解|我想知道|请问|问一下|我有|我最近|我现在|正在吃|正在用|我在吃|我做了|我做过|医生说我|帮我看看|麻烦看一下)\s*",
        "",
        value,
    )
    value = re.sub(r"(?:一下|吗|呢|呀|吧|请记住|先记住)$", "", value).strip()
    return value


def _find_terms(text: str, terms: list[str]) -> list[str]:
    found = []
    for term in terms:
        if term and term in text and term not in found:
            found.append(term)
    return found


def _extract_drugs(text: str) -> list[str]:
    hits = _find_terms(text, DRUG_TERMS)
    suffix_hits = re.findall(r"[一-龥A-Za-z]{2,16}(?:%s)" % "|".join(DRUG_SUFFIXES), text)
    hits.extend(suffix_hits)
    return _unique_nonempty([_normalize_entity_text(item) for item in hits])


def _extract_symptoms(text: str) -> list[str]:
    hits = _find_terms(text, SYMPTOM_TERMS)
    pain_hits = re.findall(r"(?:头|胸|腹|胃|肚|背|腰|肩|膝|腿|手|牙|咽|喉|颈|关节)?[^，。；、\s]{0,6}(?:痛|疼)", text)
    hits.extend([item for item in pain_hits if item])
    return _unique_nonempty([_normalize_entity_text(item) for item in hits])


def _extract_tests(text: str) -> list[str]:
    return _unique_nonempty([_normalize_entity_text(item) for item in _find_terms(text, TEST_TERMS)])


def _extract_metrics(text: str) -> list[str]:
    metrics = []
    matched_bp = False
    matched_hr = False
    matched_oxy = False
    matched_temp = False
    bp_match = re.search(r"(\d{2,3})\s*/\s*(\d{2,3})", text)
    if bp_match:
        metrics.append(f"血压 {bp_match.group(1)}/{bp_match.group(2)}")
        matched_bp = True
    elif "血压" in text:
        metrics.append("血压")

    hr_match = re.search(r"(\d{2,3})\s*(?:次/分|bpm)", text, re.IGNORECASE)
    if hr_match:
        metrics.append(f"心率 {hr_match.group(1)}次/分")
        matched_hr = True
    elif "心率" in text:
        metrics.append("心率")

    oxy_match = re.search(r"(\d{2,3})\s*%", text)
    if oxy_match and "血氧" in text:
        metrics.append(f"血氧 {oxy_match.group(1)}%")
        matched_oxy = True
    elif "血氧" in text:
        metrics.append("血氧")

    temp_match = re.search(r"(\d+(?:\.\d+)?)\s*℃", text)
    if temp_match:
        metrics.append(f"体温 {temp_match.group(1)}℃")
        matched_temp = True
    elif "体温" in text:
        metrics.append("体温")

    for term in METRIC_TERMS:
        if term == "血压" and matched_bp:
            continue
        if term == "心率" and matched_hr:
            continue
        if term == "血氧" and matched_oxy:
            continue
        if term == "体温" and matched_temp:
            continue
        if term in text and term not in metrics:
            metrics.append(term)

    return _unique_nonempty(metrics)


def _extract_entities_from_text(text: str) -> dict[str, list[str]]:
    return {
        "drugs": _extract_drugs(text),
        "symptoms": _extract_symptoms(text),
        "tests": _extract_tests(text),
        "metrics": _extract_metrics(text),
    }


def _collect_entities(messages: list[MCPRecentMessage]) -> MCPActiveEntities:
    drugs: list[str] = []
    symptoms: list[str] = []
    tests: list[str] = []
    metrics: list[str] = []
    for item in messages:
        if (item.role or "").strip().lower() != "user":
            continue
        text = _normalize_memory_fact(item.content) or item.content
        extracted = _extract_entities_from_text(text)
        drugs.extend(extracted["drugs"])
        symptoms.extend(extracted["symptoms"])
        tests.extend(extracted["tests"])
        metrics.extend(extracted["metrics"])
    return MCPActiveEntities(
        drugs=_clip_items(drugs, limit=5, item_limit=40),
        symptoms=_clip_items(symptoms, limit=5, item_limit=40),
        tests=_clip_items(tests, limit=5, item_limit=40),
        metrics=_clip_items(metrics, limit=5, item_limit=60),
    )


def _is_question(text: str) -> bool:
    lowered = text.lower()
    return "？" in text or "?" in text or any(token in lowered for token in ["怎么", "如何", "是否", "要不要", "能不能", "吗"])


def _infer_intent(text: str, entities: MCPActiveEntities) -> str:
    lowered = text.lower()
    if any(token in lowered for token in ["饭前", "饭后", "服用", "用法", "用量", "怎么吃", "吃法", "服药"]):
        return "询问药物服用方式"
    if any(token in lowered for token in ["检查", "报告", "化验", "心电图", "ct", "mri", "b超", "彩超", "血常规", "尿常规"]):
        return "询问检查结果"
    if any(token in lowered for token in ["复诊", "复查", "随访", "预约", "回诊"]):
        return "询问复诊安排"
    if any(token in lowered for token in ["血压", "血糖", "血氧", "心率", "体温", "指标", "数值"]):
        return "提供指标并寻求判断"
    if entities.drugs:
        return "围绕药物继续提问"
    if entities.tests:
        return "询问检查结果"
    if entities.symptoms:
        return "描述症状并寻求建议"
    if _is_question(text):
        return "继续提问"
    return "继续当前对话"


def _infer_goal(intent: str, current_topic: str, latest_user: str) -> str:
    if intent == "询问药物服用方式" and current_topic:
        return f"判断{current_topic}的服用方式"
    if intent == "询问检查结果" and current_topic:
        return f"解读{current_topic}"
    if intent == "询问复诊安排":
        return "确认复诊与后续安排"
    if intent == "提供指标并寻求判断":
        return "判断指标是否异常"
    if intent == "描述症状并寻求建议":
        return "判断症状意义和下一步处理"
    if intent == "围绕药物继续提问" and current_topic:
        return f"围绕{current_topic}继续回答用药问题"
    return _clip_text(latest_user, 80) or "继续当前对话"


def _infer_current_topic(entities: MCPActiveEntities, latest_user: str) -> str:
    for group in (entities.drugs, entities.tests, entities.metrics, entities.symptoms):
        if group:
            return group[-1]
    return _clip_text(latest_user, 40) or ""


def _extract_constraints(messages: list[MCPRecentMessage]) -> list[str]:
    joined = " ".join(item.content for item in messages if (item.role or "").strip().lower() == "user")
    constraints = []
    if "先给结论" in joined or "先说结论" in joined:
        constraints.append("先给结论")
    if "少术语" in joined or "通俗" in joined:
        constraints.append("少术语")
    if "简短" in joined or "别太长" in joined or "短一点" in joined:
        constraints.append("回答简短")
    if "逐步" in joined or "一步一步" in joined:
        constraints.append("需要分步说明")
    return constraints


def _extract_confirmed_facts(messages: list[MCPRecentMessage], entities: MCPActiveEntities) -> list[str]:
    facts = []
    if entities.drugs:
        facts.append(f"用户正在围绕药物 {', '.join(entities.drugs)} 进行提问")
    if entities.symptoms:
        facts.append(f"用户提到症状 {', '.join(entities.symptoms)}")
    if entities.tests:
        facts.append(f"用户提到检查/报告 {', '.join(entities.tests)}")
    if entities.metrics:
        facts.append(f"用户提供指标 {', '.join(entities.metrics)}")
    latest_user = next((item.content for item in reversed(messages) if (item.role or "").strip().lower() == "user" and (item.content or "").strip()), "")
    if latest_user:
        facts.append(f"当前最新用户问题: {_clip_text(latest_user, 80) or latest_user}")
    return _clip_items(facts, limit=8, item_limit=120)


def _extract_open_questions(messages: list[MCPRecentMessage], intent: str) -> list[str]:
    latest_user = next((item.content for item in reversed(messages) if (item.role or "").strip().lower() == "user" and (item.content or "").strip()), "")
    open_questions = []
    if latest_user and _is_question(latest_user):
        clipped = _clip_text(latest_user, 120)
        if clipped:
            open_questions.append(clipped)
    if intent == "询问药物服用方式":
        open_questions.append("药物应如何服用")
    elif intent == "询问检查结果":
        open_questions.append("检查/报告代表什么")
    elif intent == "询问复诊安排":
        open_questions.append("复诊安排是什么")
    elif intent == "提供指标并寻求判断":
        open_questions.append("当前指标是否异常")
    elif intent == "描述症状并寻求建议":
        open_questions.append("这些症状是否需要进一步处理")
    return _clip_items(open_questions, limit=5, item_limit=100)


def _extract_risk_signals(messages: list[MCPRecentMessage], entities: MCPActiveEntities) -> MCPRiskSignals:
    red_flags: list[str] = []
    medication_flags: list[str] = []
    monitoring_flags: list[str] = []
    for item in messages:
        if (item.role or "").strip().lower() != "user":
            continue
        text = (item.content or "").strip()
        if not text:
            continue

        # 红旗信号：需排除否定和过去时
        for term in RED_FLAG_TERMS:
            if term not in text:
                continue
            if _has_negation(text, term):
                continue  # e.g. "我没有胸痛"
            if _is_historical(text, term):
                continue  # e.g. "之前有过呼吸困难，已确诊"
            red_flags.append(term)

        # 用药信号：需排除否定和医生建议上下文
        for term in MEDICATION_FLAG_TERMS:
            if term not in text:
                continue
            if _has_negation(text, term):
                continue
            if term in ("停药", "加量", "减量"):
                idx = text.find(term)
                prefix = text[max(0, idx - 12):idx]
                if any(w in prefix for w in ("不要", "不能", "务必不要", "切忌", "遵医嘱", "医生建议", "被要求")):
                    continue
            medication_flags.append(term)

        # 过敏单独处理：仅在活动过敏时触发
        if _allergy_context_active(text):
            medication_flags.append("过敏反应")

        # 监测信号
        for term in MONITORING_FLAG_TERMS:
            if term not in text:
                continue
            if _has_negation(text, term):
                continue
            monitoring_flags.append(term)

        # 血压数值提取：需要上下文确认
        bp = re.search(r"(\d{2,3})\s*/\s*(\d{2,3})", text)
        if bp and _has_bp_context(text, bp):
            monitoring_flags.append(f"血压 {bp.group(1)}/{bp.group(2)}")
        hr = re.search(r"(\d{2,3})\s*(?:次/分|bpm)", text, re.IGNORECASE)
        if hr:
            monitoring_flags.append(f"心率 {hr.group(1)}次/分")
        temp = re.search(r"(\d+(?:\.\d+)?)\s*℃", text)
        if temp:
            monitoring_flags.append(f"体温 {temp.group(1)}℃")

    if entities.metrics:
        monitoring_flags.extend(entities.metrics)
    if entities.symptoms and any(item in entities.symptoms for item in ["胸痛", "呼吸困难", "晕厥", "意识不清"]):
        red_flags.extend([item for item in entities.symptoms if item in ["胸痛", "呼吸困难", "晕厥", "意识不清"]])

    return MCPRiskSignals(
        red_flags=_clip_items(red_flags, limit=6, item_limit=80),
        medication_flags=_clip_items(medication_flags, limit=6, item_limit=80),
        monitoring_flags=_clip_items(monitoring_flags, limit=8, item_limit=80),
    )


def _build_session_state(messages: list[MCPRecentMessage], entities: MCPActiveEntities) -> MCPSessionState:
    latest_user = next((item.content for item in reversed(messages) if (item.role or "").strip().lower() == "user" and (item.content or "").strip()), "")
    intent = _infer_intent(latest_user, entities)
    current_topic = _infer_current_topic(entities, latest_user)
    goal = _infer_goal(intent, current_topic, latest_user)
    constraints = _extract_constraints(messages)
    confirmed_facts = _extract_confirmed_facts(messages, entities)
    open_questions = _extract_open_questions(messages, intent)
    working_summary = _build_working_summary(latest_user, intent, current_topic, goal, constraints, confirmed_facts)
    next_action = _infer_next_action(intent, latest_user, open_questions)
    memory_focus = _infer_memory_focus(intent, entities)
    last_assistant_summary = _summarize_assistant_reply(messages)
    return MCPSessionState(
        intent=intent,
        current_topic=current_topic,
        goal=goal,
        working_summary=working_summary,
        next_action=next_action,
        memory_focus=memory_focus,
        last_assistant_summary=last_assistant_summary,
        constraints=constraints,
        confirmed_facts=confirmed_facts,
        open_questions=open_questions,
    )


def _default_short_term_memory() -> MCPShortTermMemory:
    return MCPShortTermMemory(
        recent_messages=[],
        session_state=MCPSessionState(),
        active_entities=MCPActiveEntities(),
        risk_signals=MCPRiskSignals(),
    )


def _roll_short_term_memory(
    memory: Optional[MCPShortTermMemory],
    *,
    user_message: str,
    assistant_message: str,
) -> MCPShortTermMemory:
    current = memory.model_copy(deep=True) if memory else _default_short_term_memory()
    recent_messages = list(current.recent_messages)
    recent_messages.append(MCPRecentMessage(role="user", content=user_message))
    if assistant_message.strip():
        recent_messages.append(MCPRecentMessage(role="assistant", content=assistant_message))
    recent_messages = [item for item in recent_messages if (item.content or "").strip()]
    recent_messages = recent_messages[-(SHORT_TERM_ROUND_LIMIT * 2):]

    entities = _collect_entities(recent_messages)
    session_state = _build_session_state(recent_messages, entities)
    risk_signals = _extract_risk_signals(recent_messages, entities)

    current.recent_messages = recent_messages
    current.session_state = session_state
    current.active_entities = entities
    current.risk_signals = risk_signals
    return current


def _persist_chat_turns(
    db: Session,
    *,
    patient_id: Optional[str],
    hospital_id: Optional[str],
    session_id: str,
    user_content: str,
    assistant_content: str,
) -> None:
    if patient_id:
        create_conversation_message(
            db,
            session_id=session_id,
            patient_id=patient_id,
            hospital_id=hospital_id,
            role="user",
            content=user_content,
        )
        create_conversation_message(
            db,
            session_id=session_id,
            patient_id=patient_id,
            hospital_id=hospital_id,
            role="assistant",
            content=assistant_content,
        )
        return

    create_session_buffer_message(
        db,
        session_id=session_id,
        hospital_id=hospital_id,
        role="user",
        content=user_content,
    )
    create_session_buffer_message(
        db,
        session_id=session_id,
        hospital_id=hospital_id,
        role="assistant",
        content=assistant_content,
    )


def _resolve_bound_identity(
    db: Session,
    *,
    patient_id: Optional[str],
    hospital_id: Optional[str],
    auth_token: Optional[str],
) -> tuple[Optional[str], Optional[str]]:
    resolved_patient_id = (patient_id or "").strip() or None
    resolved_hospital_id = (hospital_id or "").strip() or None
    normalized_auth_token = normalize_optional_auth_token(auth_token)
    if normalized_auth_token:
        identity = verify_auth_token(db, normalized_auth_token)
        resolved_patient_id = identity["patient_id"]
        resolved_hospital_id = identity["hospital_id"]
    return resolved_patient_id, resolved_hospital_id


def _normalize_chat_mode(chat_mode: Optional[str]) -> str:
    return (chat_mode or "").strip().lower()


def _promote_buffer_if_bound(
    db: Session,
    *,
    patient_id: Optional[str],
    hospital_id: Optional[str],
    session_id: str,
) -> None:
    if not patient_id:
        return
    promote_session_buffer_to_patient(
        db,
        session_id=session_id,
        patient_id=patient_id,
        hospital_id=hospital_id,
    )


@router.get("/health", summary="MCP Health Check", description="Check whether the MCP service is ready.")
def mcp_health_check():
    return {"status": "ok", "server": "patient-mcp-server"}


@router.get("/tools", response_model=MCPToolsResponse, summary="List MCP tools", description="Return registered MCP tools.")
def list_mcp_tools():
    return {"tools": mcp_server.list_tools()}


@router.post("/call", response_model=MCPToolCallResponse, summary="Call MCP tool", description="Directly call a tool for debugging.")
def call_mcp_tool(payload: MCPToolCallRequest):
    return mcp_server.call_tool(payload.tool_name, payload.arguments)


@router.post("/auth/issue-token", response_model=MCPToolCallResponse, summary="Issue demo token", description="Issue a demo auth token.")
def issue_demo_token(payload: MCPIssueTokenRequest):
    return mcp_server.call_tool(
        "issue_identity_token",
        {
            "patient_id": payload.patient_id,
            "hospital_id": payload.hospital_id,
            "expires_in_minutes": payload.expires_in_minutes,
        },
    )


@router.post(
    "/agent/query",
    response_model=MCPAgentQueryResponse,
    summary="Text chat",
    description="Use the current request's short-term memory and conversation context.",
)
def mcp_agent_query(payload: MCPAgentQueryRequest, db: Session = Depends(get_db)):
    auth_token = normalize_optional_auth_token(payload.auth_token)
    session_id = _resolve_session_id(payload.session_id)
    chat_mode = _normalize_chat_mode(payload.chat_mode)
    
    # Try to load short-term memory from Redis cache first
    cached_memory = get_short_term_memory(session_id)
    if cached_memory:
        try:
            input_short_term_memory = MCPShortTermMemory.model_validate(cached_memory)
        except Exception:
            input_short_term_memory = payload.short_term_memory or _default_short_term_memory()
    else:
        input_short_term_memory = payload.short_term_memory or _default_short_term_memory()
    
    session_state = input_short_term_memory.session_state

    if chat_mode == "memory" and not (payload.patient_id or auth_token):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先填写个人信息并绑定患者后，再开启记忆聊天。",
        )

    if chat_mode == "general":
        resolved_patient_id = None
        resolved_hospital_id = None
        allergy_drugs: list[str] = []
        allergy_history_unknown: bool = False
        client_context = (payload.conversation_context or "").strip() or None
        conversation_context = client_context
        rendered_memory_context = _render_short_term_memory_context(input_short_term_memory)
        long_term_memory_context = None
        knowledge_context = None
    else:
        resolved_patient_id, resolved_hospital_id = _resolve_bound_identity(
            db,
            patient_id=payload.patient_id,
            hospital_id=payload.hospital_id,
            auth_token=auth_token,
        )
        allergy_drugs: list[str] = []
        allergy_history_unknown: bool = False
        if resolved_patient_id:
            patient = get_patient(db, resolved_patient_id)
            allergy_history = (patient.allergy_history or "").strip()
            if allergy_history:
                allergy_drugs = _parse_allergy_drugs(allergy_history)
            else:
                allergy_history_unknown = True
        rendered_memory_context = _render_short_term_memory_context(input_short_term_memory)
        long_term_memory_context = _build_long_term_memory_context(db, resolved_patient_id, payload.question)
        client_context = (payload.conversation_context or "").strip() or None
        knowledge_context = _build_knowledge_context_block(payload.question, resolved_hospital_id, allergy_drugs=allergy_drugs)
        conversation_context = _merge_conversation_contexts(
            rendered_memory_context,
            long_term_memory_context,
            knowledge_context,
            client_context,
        )

    # Extract risk signals from current question for answer safety advice injection
    current_risk_signals = _extract_risk_signals(
        [MCPRecentMessage(role="user", content=payload.question)],
        input_short_term_memory.active_entities if input_short_term_memory else MCPActiveEntities(),
    )

    data = run_agent_tool_query(
        question=payload.question,
        auth_token=auth_token,
        patient_id=resolved_patient_id,
        hospital_id=resolved_hospital_id,
        chat_mode=chat_mode,
        conversation_context=conversation_context,
        allergy_drugs=allergy_drugs,
        allergy_history_unknown=allergy_history_unknown,
        risk_signals=current_risk_signals,
    )
    updated_short_term_memory = _roll_short_term_memory(
        input_short_term_memory,
        user_message=payload.question,
        assistant_message=data.get("answer") or "",
    )
    merged_session_state = _merge_session_state(session_state, updated_short_term_memory.session_state)
    if merged_session_state.identity_status != "confirmed" and resolved_patient_id:
        try:
            confirmed_patient = get_patient(db, resolved_patient_id)
            merged_session_state.identity_status = "confirmed"
            merged_session_state.confirmed_patient_id = confirmed_patient.id
            merged_session_state.confirmed_patient_name = confirmed_patient.full_name
            merged_session_state.identity_source = merged_session_state.identity_source or "session_resolved"
        except Exception:
            pass
    updated_short_term_memory.session_state = merged_session_state
    
    # Cache updated short-term memory to Redis
    try:
        set_short_term_memory(session_id, updated_short_term_memory.model_dump())
    except Exception:
        pass
    
    data["session_id"] = session_id
    data["patient_id"] = resolved_patient_id
    data["hospital_id"] = resolved_hospital_id
    data["short_term_memory"] = updated_short_term_memory
    data["short_term_memory_count"] = _count_short_term_messages_from_memory(updated_short_term_memory) or _count_short_term_messages(conversation_context)
    data["memory_debug"] = _build_memory_debug_payload(
        chat_mode=chat_mode,
        question=payload.question,
        conversation_context=conversation_context,
        rendered_short_term_memory=rendered_memory_context,
        long_term_memory_context=long_term_memory_context,
        knowledge_context=knowledge_context,
        updated_short_term_memory=updated_short_term_memory,
    )
    try:
        _promote_buffer_if_bound(
            db,
            patient_id=resolved_patient_id,
            hospital_id=resolved_hospital_id,
            session_id=session_id,
        )
        _persist_chat_turns(
            db,
            patient_id=resolved_patient_id,
            hospital_id=resolved_hospital_id,
            session_id=session_id,
            user_content=payload.question,
            assistant_content=data.get("answer") or "",
        )
    except Exception:
        pass
    return data


@router.post(
    "/agent/query-with-image",
    response_model=MCPAgentQueryResponse,
    summary="Image chat",
    description="Use the current request's short-term memory and image context.",
)
async def mcp_agent_query_with_image(
    question: str = Form(..., description="Question"),
    image: UploadFile = File(..., description="Uploaded image"),
    auth_token: str | None = Form(default=None, description="Auth token"),
    patient_id: str | None = Form(default=None, description="Patient ID"),
    hospital_id: str | None = Form(default=None, description="Hospital ID"),
    chat_mode: str | None = Form(default=None, description="Chat mode"),
    session_id: str | None = Form(default=None, description="Session ID"),
    conversation_context: str | None = Form(default=None, description="Conversation context"),
    short_term_memory_json: str | None = Form(default=None, description="Structured short-term memory JSON"),
    db: Session = Depends(get_db),
):
    resolved_auth_token = normalize_optional_auth_token(auth_token)
    resolved_session_id = _resolve_session_id(session_id)
    resolved_chat_mode = _normalize_chat_mode(chat_mode)
    
    # Try to load short-term memory from Redis cache first
    cached_memory = get_short_term_memory(resolved_session_id)
    if cached_memory:
        try:
            parsed_short_term_memory = MCPShortTermMemory.model_validate(cached_memory)
        except Exception:
            parsed_short_term_memory = None
    else:
        parsed_short_term_memory = None
    
    if not parsed_short_term_memory and short_term_memory_json:
        try:
            parsed_short_term_memory = MCPShortTermMemory.model_validate_json(short_term_memory_json)
        except Exception:
            parsed_short_term_memory = None

    if resolved_chat_mode == "memory" and not (patient_id or resolved_auth_token):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先填写个人信息并绑定患者后，再开启记忆聊天。",
        )

    if resolved_chat_mode == "general":
        resolved_patient_id = None
        resolved_hospital_id = None
        allergy_drugs: list[str] = []
        allergy_history_unknown: bool = False
    else:
        resolved_patient_id, resolved_hospital_id = _resolve_bound_identity(
            db,
            patient_id=patient_id,
            hospital_id=hospital_id,
            auth_token=resolved_auth_token,
        )
        allergy_drugs: list[str] = []
        allergy_history_unknown: bool = False
        if resolved_patient_id:
            patient = get_patient(db, resolved_patient_id)
            allergy_history = (patient.allergy_history or "").strip()
            if allergy_history:
                allergy_drugs = _parse_allergy_drugs(allergy_history)
            else:
                allergy_history_unknown = True
    input_short_term_memory = parsed_short_term_memory or _default_short_term_memory()
    session_state = input_short_term_memory.session_state

    rendered_memory_context = _render_short_term_memory_context(input_short_term_memory)
    if resolved_chat_mode == "general":
        client_context = (conversation_context or "").strip() or None
        conversation_context = client_context
        long_term_memory_context = None
        knowledge_context = None
    else:
        long_term_memory_context = _build_long_term_memory_context(db, resolved_patient_id, question)
        client_context = (conversation_context or "").strip() or None
        knowledge_context = _build_knowledge_context_block(question, resolved_hospital_id, allergy_drugs=allergy_drugs)
        conversation_context = _merge_conversation_contexts(
            rendered_memory_context,
            long_term_memory_context,
            knowledge_context,
            client_context,
        )

    image_bytes = await image.read()

    # Extract risk signals from current question for answer safety advice injection
    current_risk_signals = _extract_risk_signals(
        [MCPRecentMessage(role="user", content=question)],
        input_short_term_memory.active_entities if input_short_term_memory else MCPActiveEntities(),
    )

    data = run_agent_tool_query(
        question=question,
        auth_token=resolved_auth_token,
        patient_id=resolved_patient_id,
        hospital_id=resolved_hospital_id,
        chat_mode=resolved_chat_mode,
        image_bytes=image_bytes,
        image_content_type=image.content_type,
        image_filename=image.filename,
        conversation_context=conversation_context,
        allergy_drugs=allergy_drugs,
        allergy_history_unknown=allergy_history_unknown,
        risk_signals=current_risk_signals,
    )
    updated_short_term_memory = _roll_short_term_memory(
        input_short_term_memory,
        user_message=question if not image.filename else f"{question} [uploaded image:{image.filename}]",
        assistant_message=data.get("answer") or "",
    )
    merged_session_state = _merge_session_state(session_state, updated_short_term_memory.session_state)
    if merged_session_state.identity_status != "confirmed" and resolved_patient_id:
        try:
            confirmed_patient = get_patient(db, resolved_patient_id)
            merged_session_state.identity_status = "confirmed"
            merged_session_state.confirmed_patient_id = confirmed_patient.id
            merged_session_state.confirmed_patient_name = confirmed_patient.full_name
            merged_session_state.identity_source = merged_session_state.identity_source or "session_resolved"
        except Exception:
            pass
    updated_short_term_memory.session_state = merged_session_state
    
    # Cache updated short-term memory to Redis
    try:
        set_short_term_memory(resolved_session_id, updated_short_term_memory.model_dump())
    except Exception:
        pass
    
    data["session_id"] = resolved_session_id
    data["patient_id"] = resolved_patient_id
    data["hospital_id"] = resolved_hospital_id
    data["short_term_memory"] = updated_short_term_memory
    data["short_term_memory_count"] = _count_short_term_messages_from_memory(updated_short_term_memory) or _count_short_term_messages(conversation_context)
    data["memory_debug"] = _build_memory_debug_payload(
        chat_mode=resolved_chat_mode,
        question=question,
        conversation_context=conversation_context,
        rendered_short_term_memory=rendered_memory_context,
        long_term_memory_context=long_term_memory_context,
        knowledge_context=knowledge_context,
        updated_short_term_memory=updated_short_term_memory,
    )
    try:
        user_content = question if not image.filename else f"{question}\n[uploaded image: {image.filename}]"
        _promote_buffer_if_bound(
            db,
            patient_id=resolved_patient_id,
            hospital_id=resolved_hospital_id,
            session_id=resolved_session_id,
        )
        _persist_chat_turns(
            db,
            patient_id=resolved_patient_id,
            hospital_id=resolved_hospital_id,
            session_id=resolved_session_id,
            user_content=user_content,
            assistant_content=data.get("answer") or "",
        )
    except Exception:
        pass
    return data


@router.post(
    "/agent/speech",
    response_model=MCPSpeechResponse,
    summary="Speech output",
    description="Convert answer text to base64 audio.",
)
def mcp_agent_speech(payload: MCPSpeechRequest):
    try:
        audio_bytes, mime_type, voice, model_name, actual_format = synthesize_speech_with_llm(
            text=payload.text,
            voice=payload.voice,
            response_format=payload.response_format,
        )
    except SpeechSynthesisError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={
                "message": str(exc),
                "provider": exc.provider,
                "retryable": exc.retryable,
            },
        ) from exc
    return {
        "text": payload.text,
        "audio_base64": base64.b64encode(audio_bytes).decode("ascii"),
        "mime_type": mime_type,
        "voice": voice,
        "model": model_name,
        "response_format": actual_format,
    }


# ── RAGAS-style LLM-as-Judge 评估端点 ──

from pydantic import BaseModel as _BaseModel

class RAGASJudgeRequest(_BaseModel):
    question: str
    answer: str
    context: str = ""
    reference: str = ""
    patient_id: Optional[str] = None

class RAGASDimensionResult(_BaseModel):
    score: float
    reason: str

class RAGASJudgeResponse(_BaseModel):
    faithfulness: RAGASDimensionResult
    answer_relevancy: RAGASDimensionResult
    context_recall: RAGASDimensionResult
    context_precision: RAGASDimensionResult
    overall_score: float


def _build_ragas_judge_prompt(question: str, answer: str, context: str, reference: str) -> str:
    context_block = f"\n\n【检索上下文】\n{context}" if context else ""
    reference_block = f"\n\n【标准参考答案】\n{reference}" if reference else ""

    return f"""你是一个专业的 RAG (Retrieval-Augmented Generation) 评估专家。请对以下问答对进行多维度评估。

【用户问题】
{question}

【模型回答】
{answer}{context_block}{reference_block}

请从以下 4 个维度进行评分，每个维度 0-1 分（0.1 为最低，1.0 为最高），并给出简短理由。

1. **faithfulness（忠实度）**：回答是否忠实于检索到的上下文？是否有幻觉或捏造信息？回答中的事实是否都能在上下文中找到依据？
2. **answer_relevancy（答案相关性）**：回答是否切题、是否直接回答了用户的问题？是否包含了不必要的冗余信息？
3. **context_recall（上下文召回率）**：检索到的上下文是否包含了回答该问题所需的所有关键信息？是否有信息遗漏？
4. **context_precision（上下文精确度）**：检索到的上下文是否精准？是否混入了大量不相关的噪声信息？

请严格按以下 JSON 格式输出（不要输出其他内容）：
```json
{{
  "faithfulness": {{"score": 0.0, "reason": "理由"}},
  "answer_relevancy": {{"score": 0.0, "reason": "理由"}},
  "context_recall": {{"score": 0.0, "reason": "理由"}},
  "context_precision": {{"score": 0.0, "reason": "理由"}}
}}
```"""


@router.post(
    "/evaluate/ragas-judge",
    response_model=RAGASJudgeResponse,
    summary="RAGAS-style LLM-as-Judge evaluation",
    description="使用 LLM 对问答对进行忠实度、相关性、召回率、精确度评估。",
)
def ragas_judge(payload: RAGASJudgeRequest):
    from app.mcp.config import get_llm
    import json as _json

    llm = get_llm()
    prompt = _build_ragas_judge_prompt(
        question=payload.question,
        answer=payload.answer,
        context=payload.context,
        reference=payload.reference,
    )

    try:
        response = llm.invoke(prompt)
        raw_text = response.content.strip()
        json_match = re.search(r"\{[\s\S]*\}", raw_text)
        if not json_match:
            raise ValueError(f"LLM 返回了非 JSON 内容: {raw_text[:200]}")
        parsed = _json.loads(json_match.group())
    except Exception as exc:
        default = {"score": 0.0, "reason": f"评估失败: {exc}"}
        return RAGASJudgeResponse(
            faithfulness=RAGASDimensionResult(**default),
            answer_relevancy=RAGASDimensionResult(**default),
            context_recall=RAGASDimensionResult(**default),
            context_precision=RAGASDimensionResult(**default),
            overall_score=0.0,
        )

    def _safe_dim(key):
        d = parsed.get(key, {"score": 0.0, "reason": "未返回"})
        return RAGASDimensionResult(
            score=max(0.0, min(1.0, float(d.get("score", 0.0)))),
            reason=str(d.get("reason", "无")),
        )

    faith = _safe_dim("faithfulness")
    relev = _safe_dim("answer_relevancy")
    recall = _safe_dim("context_recall")
    preci = _safe_dim("context_precision")
    overall = round((faith.score + relev.score + recall.score + preci.score) / 4, 3)

    return RAGASJudgeResponse(
        faithfulness=faith,
        answer_relevancy=relev,
        context_recall=recall,
        context_precision=preci,
        overall_score=overall,
    )
