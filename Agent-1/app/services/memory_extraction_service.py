import json
import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.mcp.config import get_llm
from app.models.memory_business_profile import MemoryBusinessProfile
from app.models.memory_conversation import MemoryConversationMessage
from app.models.memory_conversation_profile import MemoryConversationProfile
from app.models.memory_key_event import MemoryKeyEvent
from app.models.memory_knowledge_chunk import MemoryKnowledgeChunk
from app.models.memory_preference import MemoryPreference
from app.models.memory_session_buffer import MemorySessionBufferMessage
from app.models.memory_user_profile import MemoryUserProfile
from app.services.knowledge_retrieval import get_knowledge_retriever
from app.services.patient_service import get_patient, list_medical_records, list_visit_records

BUSINESS_EVENT_SOURCE_TYPES = {"medical_record", "visit_record", "business"}
CONVERSATION_EVENT_SOURCE_TYPES = {"conversation", "conversation_signal", "conversation_preference"}
KEY_EVENT_STATUS_ACTIVE = "active"
KEY_EVENT_STATUS_SUPERSEDED = "superseded"
KEY_EVENT_PRIORITY_HIGH = "high"
KEY_EVENT_PRIORITY_MEDIUM = "medium"
KEY_EVENT_PRIORITY_LOW = "low"
KEY_EVENT_WRITE_THRESHOLD = 0.75
CONVERSATION_EVENT_WRITE_THRESHOLD = 0.82
BUSINESS_EVENT_WRITE_THRESHOLD = 0.9


def create_conversation_message(
    db: Session,
    *,
    session_id: str,
    patient_id: str,
    hospital_id: Optional[str],
    role: str,
    content: str,
) -> MemoryConversationMessage:
    patient = get_patient(db, patient_id)
    if hospital_id and hospital_id != patient.hospital_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="hospital_id does not match the patient record",
        )

    message = MemoryConversationMessage(
        session_id=session_id,
        patient_id=patient.id,
        hospital_id=patient.hospital_id,
        role=role.strip().lower(),
        content=content.strip(),
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def create_session_buffer_message(
    db: Session,
    *,
    session_id: str,
    hospital_id: Optional[str],
    role: str,
    content: str,
) -> MemorySessionBufferMessage:
    message = MemorySessionBufferMessage(
        session_id=session_id,
        hospital_id=(hospital_id or "").strip() or None,
        role=role.strip().lower(),
        content=content.strip(),
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def list_session_buffer_messages(
    db: Session,
    *,
    session_id: str,
    limit: int = 20,
) -> List[MemorySessionBufferMessage]:
    return (
        db.query(MemorySessionBufferMessage)
        .filter(MemorySessionBufferMessage.session_id == session_id)
        .order_by(MemorySessionBufferMessage.created_at.desc())
        .limit(limit)
        .all()[::-1]
    )


def delete_session_buffer_messages(
    db: Session,
    *,
    session_id: str,
) -> int:
    deleted = (
        db.query(MemorySessionBufferMessage)
        .filter(MemorySessionBufferMessage.session_id == session_id)
        .delete(synchronize_session=False)
    )
    db.commit()
    return int(deleted or 0)


def promote_session_buffer_to_patient(
    db: Session,
    *,
    session_id: str,
    patient_id: str,
    hospital_id: Optional[str],
) -> Dict[str, Any]:
    patient = get_patient(db, patient_id)
    if hospital_id and hospital_id != patient.hospital_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="hospital_id does not match the patient record",
        )

    buffered_messages = (
        db.query(MemorySessionBufferMessage)
        .filter(MemorySessionBufferMessage.session_id == session_id)
        .order_by(MemorySessionBufferMessage.created_at.asc())
        .all()
    )
    if not buffered_messages:
        return {
            "session_id": session_id,
            "patient_id": patient.id,
            "hospital_id": patient.hospital_id,
            "promoted_messages": 0,
        }

    existing_pairs = {
        (item.role, item.content.strip())
        for item in (
            db.query(MemoryConversationMessage)
            .filter(
                MemoryConversationMessage.patient_id == patient.id,
                MemoryConversationMessage.session_id == session_id,
            )
            .all()
        )
    }

    promoted_count = 0
    for item in buffered_messages:
        key = ((item.role or "").strip().lower(), (item.content or "").strip())
        if not key[1] or key in existing_pairs:
            continue
        db.add(
            MemoryConversationMessage(
                session_id=session_id,
                patient_id=patient.id,
                hospital_id=patient.hospital_id,
                role=key[0],
                content=key[1],
                created_at=item.created_at,
            )
        )
        existing_pairs.add(key)
        promoted_count += 1

    for item in buffered_messages:
        db.delete(item)
    db.commit()

    return {
        "session_id": session_id,
        "patient_id": patient.id,
        "hospital_id": patient.hospital_id,
        "promoted_messages": promoted_count,
    }


def list_conversation_messages(
    db: Session,
    *,
    patient_id: str,
    session_id: Optional[str] = None,
    limit: int = 20,
) -> List[MemoryConversationMessage]:
    get_patient(db, patient_id)
    query = db.query(MemoryConversationMessage).filter(MemoryConversationMessage.patient_id == patient_id)
    if session_id:
        query = query.filter(MemoryConversationMessage.session_id == session_id)
    return query.order_by(MemoryConversationMessage.created_at.desc()).limit(limit).all()[::-1]


def build_conversation_context(
    messages: List[MemoryConversationMessage],
    *,
    limit: int = 12,
) -> Optional[str]:
    normalized = []
    for item in messages[-limit:]:
        role = (getattr(item, "role", "assistant") or "assistant").strip().lower()
        content = (getattr(item, "content", "") or "").strip()
        if not content:
            continue
        role_label = {"user": "User", "assistant": "Assistant", "system": "System"}.get(role, role)
        normalized.append(f"{role_label}: {content}")
    return "\n".join(normalized) or None


def list_conversation_sessions(
    db: Session,
    *,
    patient_id: str,
    limit: int = 10,
) -> List[dict]:
    patient = get_patient(db, patient_id)
    rows = (
        db.query(
            MemoryConversationMessage.session_id.label("session_id"),
            func.count(MemoryConversationMessage.id).label("message_count"),
            func.max(MemoryConversationMessage.created_at).label("latest_message_at"),
        )
        .filter(MemoryConversationMessage.patient_id == patient.id)
        .group_by(MemoryConversationMessage.session_id)
        .order_by(func.max(MemoryConversationMessage.created_at).desc())
        .limit(limit)
        .all()
    )

    sessions = []
    for row in rows:
        latest_message = (
            db.query(MemoryConversationMessage)
            .filter(
                MemoryConversationMessage.patient_id == patient.id,
                MemoryConversationMessage.session_id == row.session_id,
            )
            .order_by(MemoryConversationMessage.created_at.desc())
            .first()
        )
        preview = None
        if latest_message and latest_message.content:
            preview = latest_message.content.strip().replace("\n", " ")[:80]
        sessions.append(
            {
                "session_id": row.session_id,
                "patient_id": patient.id,
                "hospital_id": patient.hospital_id,
                "message_count": int(row.message_count or 0),
                "latest_message_preview": preview,
                "latest_message_at": row.latest_message_at,
            }
        )
    return sessions


def delete_conversation_messages(
    db: Session,
    *,
    patient_id: str,
    session_id: Optional[str] = None,
) -> int:
    patient = get_patient(db, patient_id)
    query = db.query(MemoryConversationMessage).filter(MemoryConversationMessage.patient_id == patient.id)
    if session_id:
        query = query.filter(MemoryConversationMessage.session_id == session_id)
    deleted = query.delete(synchronize_session=False)
    db.commit()
    return int(deleted or 0)


def clear_patient_long_term_memory(
    db: Session,
    *,
    patient_id: str,
    include_preferences: bool = False,
) -> Dict[str, int]:
    patient = get_patient(db, patient_id)
    deleted_counts = {
        "conversation_messages": int(
            db.query(MemoryConversationMessage)
            .filter(MemoryConversationMessage.patient_id == patient.id)
            .delete(synchronize_session=False)
            or 0
        ),
        "key_events": int(
            db.query(MemoryKeyEvent)
            .filter(MemoryKeyEvent.patient_id == patient.id)
            .delete(synchronize_session=False)
            or 0
        ),
        "user_profiles": int(
            db.query(MemoryUserProfile)
            .filter(MemoryUserProfile.patient_id == patient.id)
            .delete(synchronize_session=False)
            or 0
        ),
    }
    if include_preferences:
        deleted_counts["preferences"] = int(
            db.query(MemoryPreference)
            .filter(MemoryPreference.patient_id == patient.id)
            .delete(synchronize_session=False)
            or 0
        )
    db.commit()
    return deleted_counts


def _validate_patient_context(
    db: Session,
    *,
    patient_id: str,
    hospital_id: Optional[str],
):
    patient = get_patient(db, patient_id)
    if hospital_id and hospital_id != patient.hospital_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="hospital_id does not match the patient record",
        )
    return patient


def _normalize_event_time(value):
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        raw = raw.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            return None
    return None


def _safe_json_load(text: str):
    try:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        return json.loads(text[start : end + 1])
    except Exception:
        return None


def _merge_unique_text(existing: Optional[str], incoming: Optional[str], delimiter: str) -> Optional[str]:
    items = []
    for value in (existing, incoming):
        raw = (value or "").strip()
        if not raw:
            continue
        parts = [piece.strip() for piece in raw.split(delimiter)] if delimiter in raw else [raw]
        for piece in parts:
            if piece and piece not in items:
                items.append(piece)
    return delimiter.join(items) if items else None


def _merge_unique_text_limited(
    existing: Optional[str],
    incoming: Optional[str],
    delimiter: str,
    *,
    max_items: int = 3,
    item_max_chars: int = 80,
) -> Optional[str]:
    items = []
    for value in (existing, incoming):
        raw = (value or "").strip()
        if not raw:
            continue
        parts = [piece.strip() for piece in raw.split(delimiter)] if delimiter in raw else [raw]
        for piece in parts:
            clipped = _clip_text(piece, max_chars=item_max_chars)
            if clipped and clipped not in items:
                items.append(clipped)
            if len(items) >= max_items:
                return delimiter.join(items)
    return delimiter.join(items) if items else None


def _normalize_source_ref(value: Optional[str]) -> Optional[str]:
    raw = _normalize_text(str(value or ""))
    if not raw:
        return None
    parts = re.split(r"[,\|;\n]+", raw)
    for part in parts:
        text = _normalize_text(part)
        if text:
            return text
    return None


def _compose_business_profile_summary(
    patient_name: str,
    *,
    focus_topics: Optional[str],
    risk_focus: Optional[str],
    care_needs: Optional[str],
) -> str:
    parts = []
    if focus_topics:
        parts.append(f"Focus: {_clip_text(focus_topics, max_chars=80)}")
    if risk_focus:
        parts.append(f"Risk: {_clip_text(risk_focus, max_chars=80)}")
    if care_needs:
        parts.append(f"Care: {_clip_text(care_needs, max_chars=80)}")
    if parts:
        return f"Current patient: {patient_name}. " + " | ".join(parts)
    return f"Current patient: {patient_name}. Business profile awaiting more stable medical memory signals."


def _compose_conversation_profile_summary(
    patient_name: str,
    *,
    communication_preference: Optional[str],
    focus_topics: Optional[str],
) -> str:
    parts = []
    if focus_topics:
        parts.append(f"Focus: {_clip_text(focus_topics, max_chars=80)}")
    if communication_preference:
        parts.append(f"Communication: {_clip_text(communication_preference, max_chars=80)}")
    if parts:
        return f"Current patient: {patient_name}. " + " | ".join(parts)
    return f"Current patient: {patient_name}. Conversation profile awaiting more stable dialogue signals."


def _compose_profile_summary(
    patient_name: str,
    *,
    communication_preference: Optional[str],
    focus_topics: Optional[str],
    risk_focus: Optional[str],
    care_needs: Optional[str],
) -> str:
    parts = []
    if focus_topics:
        parts.append(f"Focus: {_clip_text(focus_topics, max_chars=80)}")
    if communication_preference:
        parts.append(f"Communication: {_clip_text(communication_preference, max_chars=80)}")
    if risk_focus:
        parts.append(f"Risk: {_clip_text(risk_focus, max_chars=80)}")
    if care_needs:
        parts.append(f"Care: {_clip_text(care_needs, max_chars=80)}")
    if parts:
        return f"Current patient: {patient_name}. " + " | ".join(parts)
    return f"Current patient: {patient_name}. Profile awaiting merged business and conversation signals."


def _normalize_text(value: Optional[str]) -> str:
    return " ".join((value or "").strip().split())


def _clip_text(value: str, *, max_chars: int = 120) -> str:
    text = _normalize_text(value)
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 1)].rstrip() + "…"


def _clip_items(values: Sequence[str], *, limit: int, item_limit: int) -> List[str]:
    clipped = []
    for value in values:
        text = _clip_text(value, max_chars=item_limit)
        if text and text not in clipped:
            clipped.append(text)
        if len(clipped) >= limit:
            break
    return clipped


def _normalize_tags(tags: Optional[Any]) -> Optional[str]:
    if tags is None:
        return None
    if isinstance(tags, str):
        values = [piece.strip() for piece in tags.split(",") if piece.strip()]
    elif isinstance(tags, (list, tuple, set)):
        values = [str(piece).strip() for piece in tags if str(piece).strip()]
    else:
        values = [str(tags).strip()] if str(tags).strip() else []
    return ",".join(dict.fromkeys(values)) if values else None


def _event_priority_from_confidence(confidence: float) -> str:
    if confidence >= 0.9:
        return KEY_EVENT_PRIORITY_HIGH
    if confidence >= 0.8:
        return KEY_EVENT_PRIORITY_MEDIUM
    return KEY_EVENT_PRIORITY_LOW


def _canonical_event_key(
    *,
    patient_id: str,
    event_type: str,
    source_type: str,
    source_ref: Optional[str],
    content: str,
) -> str:
    ref = (source_ref or "").strip() or _clip_text(content, max_chars=64)
    return f"{patient_id}|{event_type}|{source_type}|{ref}".lower()


def _normalize_key_event_payload(
    payload: Dict[str, Any],
    *,
    patient_id: str,
    source_scope: str,
) -> Optional[Dict[str, Any]]:
    event_type = _normalize_text(str(payload.get("type") or payload.get("event_type") or payload.get("title") or ""))
    content = _normalize_text(str(payload.get("content") or payload.get("summary") or payload.get("title") or ""))
    impact = _normalize_text(str(payload.get("impact") or ""))
    source = payload.get("source")
    source_type = _normalize_text(str(payload.get("source_type") or (source or {}).get("source_type") or source_scope))
    source_ref = _normalize_source_ref(payload.get("source_ref") or (source or {}).get("source_ref"))
    evidence = _normalize_text(str(payload.get("evidence") or (source or {}).get("evidence") or ""))
    confidence_raw = payload.get("confidence")
    try:
        confidence = float(confidence_raw)
    except (TypeError, ValueError):
        confidence = 0.8 if source_scope == "business" else 0.75
    confidence = max(0.0, min(confidence, 1.0))
    tags = _normalize_tags(payload.get("tags"))
    event_time = _normalize_event_time(payload.get("event_time") or (source or {}).get("timestamp"))
    if not event_type or not content or not impact:
        return None
    canonical_key = _canonical_event_key(
        patient_id=patient_id,
        event_type=event_type,
        source_type=source_type or source_scope,
        source_ref=str(source_ref) if source_ref is not None else None,
        content=content,
    )
    return {
        "type": event_type,
        "content": content,
        "impact": impact,
        "confidence": confidence,
        "source_type": source_type or source_scope,
        "source_ref": source_ref,
        "evidence": evidence or None,
        "canonical_key": canonical_key,
        "status": KEY_EVENT_STATUS_ACTIVE,
        "priority": payload.get("priority") or _event_priority_from_confidence(confidence),
        "tags": tags,
        "event_time": event_time,
        "last_confirmed_at": event_time or datetime.utcnow(),
    }


def _should_write_key_event(normalized_payload: Dict[str, Any], *, scope: str) -> bool:
    if not normalized_payload:
        return False
    confidence = float(normalized_payload.get("confidence") or 0.0)
    if scope == "business":
        threshold = BUSINESS_EVENT_WRITE_THRESHOLD
    elif scope == "conversation":
        threshold = CONVERSATION_EVENT_WRITE_THRESHOLD
    else:
        threshold = KEY_EVENT_WRITE_THRESHOLD
    if confidence < threshold:
        return False
    content = _normalize_text(str(normalized_payload.get("content") or ""))
    impact = _normalize_text(str(normalized_payload.get("impact") or ""))
    if len(content) < 4 or len(impact) < 4:
        return False
    return True


def _merge_key_event_record(existing: MemoryKeyEvent, incoming: Dict[str, Any]) -> MemoryKeyEvent:
    existing.content = incoming["content"]
    existing.impact = incoming["impact"]
    existing.confidence = max(float(existing.confidence or 0.0), float(incoming["confidence"] or 0.0))
    existing.source_type = incoming["source_type"]
    if not existing.source_ref:
        existing.source_ref = incoming["source_ref"]
    existing.evidence = _merge_unique_text(existing.evidence, incoming.get("evidence"), " | ")
    existing.status = KEY_EVENT_STATUS_ACTIVE
    existing.priority = incoming["priority"]
    existing.tags = _merge_unique_text(existing.tags, incoming.get("tags"), ", ")
    existing.event_time = incoming.get("event_time") or existing.event_time
    existing.last_confirmed_at = incoming.get("last_confirmed_at") or datetime.utcnow()
    return existing


def _event_to_dict(event: MemoryKeyEvent) -> Dict[str, Any]:
    return {
        "id": event.id,
        "patient_id": event.patient_id,
        "hospital_id": event.hospital_id,
        "type": event.type,
        "content": event.content,
        "impact": event.impact,
        "confidence": event.confidence,
        "source_type": event.source_type,
        "source_ref": event.source_ref,
        "evidence": event.evidence,
        "canonical_key": event.canonical_key,
        "status": event.status,
        "priority": event.priority,
        "tags": event.tags,
        "event_time": event.event_time,
        "last_confirmed_at": event.last_confirmed_at,
        "created_at": event.created_at,
        "updated_at": event.updated_at,
    }


def _knowledge_chunk_to_dict(chunk: MemoryKnowledgeChunk) -> Dict[str, Any]:
    return {
        "id": chunk.id,
        "hospital_id": chunk.hospital_id,
        "domain": chunk.domain,
        "title": chunk.title,
        "chunk_text": chunk.chunk_text,
        "source_type": chunk.source_type,
        "source_ref": chunk.source_ref,
        "version": chunk.version,
        "confidence": chunk.confidence,
        "tags": chunk.tags,
        "embedding_key": chunk.embedding_key,
        "effective_from": chunk.effective_from,
        "expires_at": chunk.expires_at,
        "created_at": chunk.created_at,
        "updated_at": chunk.updated_at,
    }


def _knowledge_query_tokens(text: str) -> List[str]:
    normalized = _normalize_text(text)
    if not normalized:
        return []

    parts = [piece.strip() for piece in re.split(r"[\s,，。！？；;、/|]+", normalized) if piece.strip()]
    tokens: List[str] = []
    for part in parts:
        if part not in tokens:
            tokens.append(part)

        if any("\u4e00" <= ch <= "\u9fff" for ch in part):
            for window in (4, 3, 2):
                if len(part) < window:
                    continue
                for idx in range(0, len(part) - window + 1):
                    gram = part[idx : idx + window]
                    if gram not in tokens:
                        tokens.append(gram)

    return tokens[:20]


def _extract_last_user_message(messages: Sequence[MemoryConversationMessage]) -> Optional[MemoryConversationMessage]:
    for item in reversed(list(messages)):
        if (item.role or "").strip().lower() == "user" and (item.content or "").strip():
            return item
    return None


def _extract_business_events_with_rules(medical_records, visit_records):
    events = []
    for record in medical_records[:3]:
        title = record.title or record.diagnosis or "Clinical update"
        content = _normalize_text(
            f"{record.title or record.record_type or 'medical record'}: {record.diagnosis or record.present_illness or record.treatment_plan or 'record updated'}"
        )
        impact = _normalize_text(
            f"Future questions should continue to consider {record.diagnosis or record.department or 'this medical record'} and the latest treatment plan."
        )
        events.append(
            {
                "type": "diagnosis_confirmed" if record.diagnosis else "clinical_update",
                "title": title,
                "content": content,
                "impact": impact,
                "confidence": 0.97 if record.diagnosis or record.treatment_plan else 0.9,
                "source": {
                    "source_type": "medical_record",
                    "source_ref": record.id,
                    "evidence": f"{record.record_date}, department {record.department or '-'}, diagnosis {record.diagnosis or '-'}, plan {record.treatment_plan or '-'}",
                    "timestamp": record.record_date,
                },
                "tags": ",".join(filter(None, [record.record_type, record.department, record.diagnosis])) or None,
                "event_time": record.record_date,
            }
        )
    for visit in visit_records[:3]:
        content = _normalize_text(
            f"{visit.department or 'Visit'} on {visit.visit_date}: {visit.visit_summary or visit.chief_complaint or 'follow-up recorded'}"
        )
        impact = _normalize_text(
            f"Future answers should respect the latest follow-up plan {visit.follow_up_plan or visit.visit_summary or 'and the visit summary'}."
        )
        events.append(
            {
                "type": "follow_up_plan" if visit.follow_up_plan else "visit_summary",
                "title": visit.department or "Visit record",
                "content": content,
                "impact": impact,
                "confidence": 0.95 if visit.follow_up_plan else 0.88,
                "source": {
                    "source_type": "visit_record",
                    "source_ref": visit.id,
                    "evidence": f"{visit.visit_date}, department {visit.department or '-'}, doctor {visit.doctor_name or '-'}, summary {visit.visit_summary or '-'}, follow-up {visit.follow_up_plan or '-'}",
                    "timestamp": visit.visit_date,
                },
                "tags": ",".join(filter(None, [visit.visit_type, visit.department, visit.visit_status])) or None,
                "event_time": visit.visit_date,
            }
        )
    return events


def _extract_conversation_events_with_rules(messages: Sequence[MemoryConversationMessage]):
    joined = "\n".join(f"{m.role}: {m.content}" for m in messages if (m.content or "").strip())
    if not joined:
        return []

    last_user = _extract_last_user_message(messages)
    if not last_user:
        return []

    events = []
    lower = joined.lower()
    session_ref = last_user.session_id
    created_at = last_user.created_at

    medication_hits = [term for term in ["阿司匹林", "布洛芬", "服药", "用药", "吃药", "剂量", "饭前", "饭后"] if term in joined]
    symptom_hits = [term for term in ["胸闷", "心慌", "头痛", "头晕", "恶心", "呕吐", "咳嗽", "发热", "血压"] if term in joined]
    followup_hits = [term for term in ["复诊", "复查", "随访", "回诊", "预约"] if term in joined]
    preference_hits = [term for term in ["简短", "详细", "步骤", "通俗", "专业", "先说结论"] if term in joined]

    if medication_hits and len(medication_hits) >= 1:
        events.append(
            {
                "type": "medication_question",
                "title": "Medication question focus",
                "content": f"User is repeatedly asking about {medication_hits[0]} or related medication use.",
                "impact": "Future turns should continue to interpret medication advice in the context of the current drug question.",
                "confidence": 0.86 if len(medication_hits) > 1 else 0.82,
                "source": {
                    "source_type": "conversation_signal",
                    "source_ref": session_ref,
                    "evidence": _clip_text(joined, max_chars=180),
                    "timestamp": created_at,
                },
                "tags": ["medication", "conversation"],
                "event_time": created_at,
            }
        )

    if symptom_hits and len(symptom_hits) >= 1:
        events.append(
            {
                "type": "symptom_persistence",
                "title": "Symptom focus",
                "content": f"User keeps mentioning {symptom_hits[0]} in the current conversation.",
                "impact": "Future symptom analysis should keep the latest symptom focus in context.",
                "confidence": 0.84 if len(symptom_hits) > 1 else 0.8,
                "source": {
                    "source_type": "conversation_signal",
                    "source_ref": session_ref,
                    "evidence": _clip_text(joined, max_chars=180),
                    "timestamp": created_at,
                },
                "tags": ["symptom", "monitoring", "conversation"],
                "event_time": created_at,
            }
        )

    if followup_hits:
        events.append(
            {
                "type": "follow_up_plan",
                "title": "Follow-up planning focus",
                "content": "User is focused on follow-up planning, revisit timing, or next steps.",
                "impact": "Future answers should preserve the follow-up agenda until resolved.",
                "confidence": 0.85 if len(followup_hits) > 1 else 0.8,
                "source": {
                    "source_type": "conversation_signal",
                    "source_ref": session_ref,
                    "evidence": _clip_text(joined, max_chars=180),
                    "timestamp": created_at,
                },
                "tags": ["follow-up", "conversation"],
                "event_time": created_at,
            }
        )

    if preference_hits:
        events.append(
            {
                "type": "communication_preference",
                "title": "Communication preference signal",
                "content": f"User prefers {preference_hits[0]} responses in the current conversation.",
                "impact": "Future responses should honor the user's conversation style preference.",
                "confidence": 0.83,
                "source": {
                    "source_type": "conversation_preference",
                    "source_ref": session_ref,
                    "evidence": _clip_text(joined, max_chars=160),
                    "timestamp": created_at,
                },
                "tags": ["preference", "conversation"],
                "event_time": created_at,
            }
        )

    if not events:
        preview = _clip_text(last_user.content, max_chars=96)
        events.append(
            {
                "type": "conversation_focus",
                "title": "Recent conversation focus",
                "content": preview,
                "impact": "Keep the latest user concern in short-term continuity, but do not over-persist it.",
                "confidence": 0.76,
                "source": {
                    "source_type": "conversation_signal",
                    "source_ref": session_ref,
                    "evidence": preview,
                    "timestamp": created_at,
                },
                "tags": ["short-term-memory"],
                "event_time": created_at,
            }
        )
    return events


def _build_business_profile_with_rules(patient, medical_records, visit_records):
    focus_topics = []
    if medical_records:
        latest_record = medical_records[0]
        if latest_record.diagnosis:
            focus_topics.append(f"diagnosis: {latest_record.diagnosis}")
        elif latest_record.department:
            focus_topics.append(f"department: {latest_record.department}")
    if visit_records and visit_records[0].follow_up_plan:
        focus_topics.append("follow-up management")
    if patient.family_history:
        focus_topics.append("family history risk")

    risk_focus = []
    if patient.family_history:
        risk_focus.append(patient.family_history)
    if medical_records and medical_records[0].diagnosis:
        risk_focus.append(f"recent diagnosis: {medical_records[0].diagnosis}")
    if visit_records and visit_records[0].follow_up_plan:
        risk_focus.append(f"follow-up plan: {visit_records[0].follow_up_plan}")

    care_needs = []
    if medical_records and medical_records[0].treatment_plan:
        care_needs.append(medical_records[0].treatment_plan)
    if visit_records and visit_records[0].follow_up_plan:
        care_needs.append(visit_records[0].follow_up_plan)

    source_summary = (
        f"Built from {len(medical_records)} medical records, {len(visit_records)} visit records, "
        f"and medical-business signals only."
    )
    return {
        "profile_summary": "",
        "risk_focus": "; ".join(risk_focus) if risk_focus else None,
        "focus_topics": ", ".join(dict.fromkeys(focus_topics)) if focus_topics else None,
        "care_needs": "; ".join(care_needs) if care_needs else None,
        "source_summary": source_summary,
    }


def _build_conversation_profile_with_rules(preference, messages: Sequence[MemoryConversationMessage]):
    joined = "\n".join(f"{m.role}: {m.content}" for m in messages if (m.content or "").strip())

    focus_topics = []
    if any(keyword in joined for keyword in ["follow-up", "review", "复诊", "随诊", "回诊"]):
        focus_topics.append("follow-up planning")
    if any(keyword in joined for keyword in ["blood pressure", "dizzy", "血压", "头晕", "胸闷", "心慌"]):
        focus_topics.append("symptoms and blood pressure monitoring")
    if any(keyword in joined for keyword in ["medication", "medicine", "药物", "用药", "吃药"]):
        focus_topics.append("medication questions")

    communication_preference = None
    if preference:
        if preference.answer_style == "brief" or preference.answer_length == "short":
            communication_preference = "prefers concise answers"
        elif preference.prefer_step_by_step:
            communication_preference = "prefers step-by-step explanations"
    elif any(keyword in joined for keyword in ["simple", "brief", "summary first", "简短", "直接", "先给结论"]):
        communication_preference = "recent conversation suggests concise communication"

    source_summary = (
        f"Built from {len(messages)} short-term conversation messages and "
        f"{'manual memory preferences' if preference else 'no manual memory preference yet'}."
    )
    return {
        "profile_summary": "",
        "communication_preference": communication_preference,
        "focus_topics": ", ".join(dict.fromkeys(focus_topics)) if focus_topics else None,
        "source_summary": source_summary,
    }


def _normalize_business_profile_payload(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    focus_topics = _normalize_text(str(payload.get("focus_topics") or ""))
    risk_focus = _normalize_text(str(payload.get("risk_focus") or ""))
    care_needs = _normalize_text(str(payload.get("care_needs") or ""))
    source_summary = _normalize_text(str(payload.get("source_summary") or ""))
    if not any([focus_topics, risk_focus, care_needs, source_summary]):
        return None
    return {
        "focus_topics": focus_topics or None,
        "risk_focus": risk_focus or None,
        "care_needs": care_needs or None,
        "source_summary": source_summary or None,
    }


def _normalize_conversation_profile_payload(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    communication_preference = _normalize_text(str(payload.get("communication_preference") or ""))
    focus_topics = _normalize_text(str(payload.get("focus_topics") or ""))
    source_summary = _normalize_text(str(payload.get("source_summary") or ""))
    if not any([communication_preference, focus_topics, source_summary]):
        return None
    return {
        "communication_preference": communication_preference or None,
        "focus_topics": focus_topics or None,
        "source_summary": source_summary or None,
    }


def _upsert_business_profile(
    db: Session,
    *,
    patient,
    incoming_profile: dict,
) -> MemoryBusinessProfile:
    profile = db.query(MemoryBusinessProfile).filter(MemoryBusinessProfile.patient_id == patient.id).first()
    if not profile:
        profile = MemoryBusinessProfile(patient_id=patient.id, hospital_id=patient.hospital_id, profile_summary="")
        db.add(profile)

    profile.hospital_id = patient.hospital_id
    profile.risk_focus = _merge_unique_text_limited(profile.risk_focus, incoming_profile.get("risk_focus"), "; ")
    profile.focus_topics = _merge_unique_text_limited(profile.focus_topics, incoming_profile.get("focus_topics"), ", ")
    profile.care_needs = _merge_unique_text_limited(profile.care_needs, incoming_profile.get("care_needs"), "; ")
    profile.source_summary = _merge_unique_text_limited(profile.source_summary, incoming_profile.get("source_summary"), " | ", max_items=3, item_max_chars=96)
    profile.profile_summary = _compose_business_profile_summary(
        patient.full_name,
        focus_topics=profile.focus_topics,
        risk_focus=profile.risk_focus,
        care_needs=profile.care_needs,
    )
    return profile


def _upsert_conversation_profile(
    db: Session,
    *,
    patient,
    incoming_profile: dict,
) -> MemoryConversationProfile:
    profile = db.query(MemoryConversationProfile).filter(MemoryConversationProfile.patient_id == patient.id).first()
    if not profile:
        profile = MemoryConversationProfile(patient_id=patient.id, hospital_id=patient.hospital_id, profile_summary="")
        db.add(profile)

    profile.hospital_id = patient.hospital_id
    incoming_communication = (incoming_profile.get("communication_preference") or "").strip() or None
    if incoming_communication:
        profile.communication_preference = incoming_communication
    profile.focus_topics = _merge_unique_text_limited(profile.focus_topics, incoming_profile.get("focus_topics"), ", ")
    profile.source_summary = _merge_unique_text_limited(profile.source_summary, incoming_profile.get("source_summary"), " | ", max_items=3, item_max_chars=96)
    profile.profile_summary = _compose_conversation_profile_summary(
        patient.full_name,
        communication_preference=profile.communication_preference,
        focus_topics=profile.focus_topics,
    )
    return profile


def _rebuild_merged_profile(
    db: Session,
    *,
    patient,
) -> MemoryUserProfile:
    business_profile = db.query(MemoryBusinessProfile).filter(MemoryBusinessProfile.patient_id == patient.id).first()
    conversation_profile = db.query(MemoryConversationProfile).filter(MemoryConversationProfile.patient_id == patient.id).first()
    merged = db.query(MemoryUserProfile).filter(MemoryUserProfile.patient_id == patient.id).first()
    if not merged:
        merged = MemoryUserProfile(patient_id=patient.id, hospital_id=patient.hospital_id, profile_summary="")
        db.add(merged)

    merged.hospital_id = patient.hospital_id
    merged.communication_preference = conversation_profile.communication_preference if conversation_profile else None
    merged.risk_focus = getattr(business_profile, "risk_focus", None)
    merged.focus_topics = _merge_unique_text_limited(
        getattr(business_profile, "focus_topics", None),
        getattr(conversation_profile, "focus_topics", None),
        ", ",
        max_items=5,
        item_max_chars=80,
    )
    merged.care_needs = getattr(business_profile, "care_needs", None)
    merged.source_summary = _merge_unique_text_limited(
        getattr(business_profile, "source_summary", None),
        getattr(conversation_profile, "source_summary", None),
        " | ",
        max_items=3,
        item_max_chars=96,
    )
    merged.profile_summary = _compose_profile_summary(
        patient.full_name,
        communication_preference=merged.communication_preference,
        focus_topics=merged.focus_topics,
        risk_focus=merged.risk_focus,
        care_needs=merged.care_needs,
    )
    return merged


def _extract_business_with_llm(patient, medical_records, visit_records):
    try:
        llm = get_llm()
    except Exception:
        return None

    prompt = f"""
You are the business-memory extraction module for a patient support agent.
Use only the patient profile, medical records, and visit records below to extract:
1. key_events
2. user_profile

Requirements:
1. Do not use short-term conversation in this extraction.
2. Keep key_events to 1-5 items with clear evidence-backed medical events.
3. The user_profile should focus on stable communication preferences, stable focus topics, and care needs.
4. Return JSON only.

Patient profile: name={patient.full_name}, gender={patient.gender or '-'}, family_history={patient.family_history or '-'}, notes={patient.notes or '-'}
Medical records: {json.dumps([{'title': r.title, 'department': r.department, 'diagnosis': r.diagnosis, 'treatment_plan': r.treatment_plan, 'record_date': str(r.record_date)} for r in medical_records], ensure_ascii=False)}
Visit records: {json.dumps([{'department': v.department, 'doctor_name': v.doctor_name, 'visit_summary': v.visit_summary, 'follow_up_plan': v.follow_up_plan, 'visit_date': str(v.visit_date)} for v in visit_records], ensure_ascii=False)}

Return format:
{{
  "key_events": [
    {{
      "type": "medication_change",
      "content": "...",
      "impact": "...",
      "confidence": 0.9,
      "source": {{
      "source_type": "medical_record",
      "source_ref": "...",
        "evidence": "...",
        "timestamp": "..."
      }},
      "tags": "..."
    }}
  ],
  "user_profile": {{
    "profile_summary": "...",
    "risk_focus": "...",
    "focus_topics": "...",
    "care_needs": "...",
    "source_summary": "..."
  }}
}}
"""
    try:
        raw = llm.invoke(prompt)
        text = raw.content if isinstance(raw.content, str) else str(raw.content)
        data = _safe_json_load(text)
        if isinstance(data, dict):
            return data
    except Exception:
        return None
    return None


def _extract_conversation_with_llm(patient, preference, messages: Sequence[MemoryConversationMessage]):
    try:
        llm = get_llm()
    except Exception:
        return None

    prompt = f"""
You are the conversation-memory extraction module for a patient support agent.
Use only the recent short-term conversation below to extract:
1. key_events
2. user_profile

Requirements:
1. Do not use medical records or visit records in this extraction.
2. Keep key_events only when the conversation shows a stable, reusable concern or preference.
3. The user_profile should focus on communication_preference and focus_topics that are directly supported by the conversation.
4. If manual preference exists, merge it naturally into communication_preference.
5. Return JSON only.

Patient profile: name={patient.full_name}, notes={patient.notes or '-'}
Manual preference: notes={preference.notes if preference else 'none'}, style={preference.answer_style if preference else 'not set'}, length={preference.answer_length if preference else 'not set'}, term_level={preference.medical_term_level if preference else 'not set'}
Short-term conversation: {json.dumps([{'role': m.role, 'content': m.content} for m in messages], ensure_ascii=False)}

Return format:
{{
  "key_events": [
    {{
      "type": "symptom_persistence",
      "content": "...",
      "impact": "...",
      "confidence": 0.8,
      "source": {{
        "source_type": "conversation_signal",
        "source_ref": "...",
        "evidence": "...",
        "timestamp": "..."
      }},
      "tags": "..."
    }}
  ],
  "user_profile": {{
    "profile_summary": "...",
    "communication_preference": "...",
    "focus_topics": "...",
    "source_summary": "..."
  }}
}}
"""
    try:
        raw = llm.invoke(prompt)
        text = raw.content if isinstance(raw.content, str) else str(raw.content)
        data = _safe_json_load(text)
        if isinstance(data, dict):
            return data
    except Exception:
        return None
    return None


def _normalize_scope_source_type(raw_value: Optional[str], *, scope: str) -> str:
    value = (raw_value or "").strip()
    if scope == "business":
        return value if value in BUSINESS_EVENT_SOURCE_TYPES else "business"
    return value if value in CONVERSATION_EVENT_SOURCE_TYPES else "conversation"


def _replace_scope_events(
    db: Session,
    *,
    patient,
    scope: str,
    event_payloads: Sequence[dict],
) -> List[MemoryKeyEvent]:
    persisted_events = []
    existing_events = (
        db.query(MemoryKeyEvent)
        .filter(
            MemoryKeyEvent.patient_id == patient.id,
            MemoryKeyEvent.status == KEY_EVENT_STATUS_ACTIVE,
        )
        .all()
    )
    existing_by_key = {event.canonical_key: event for event in existing_events}
    for item in event_payloads:
        if not isinstance(item, dict):
            continue
        normalized = _normalize_key_event_payload(item, patient_id=patient.id, source_scope=scope)
        if not normalized or not _should_write_key_event(normalized, scope=scope):
            continue

        event = existing_by_key.get(normalized["canonical_key"])
        if event:
            event = _merge_key_event_record(event, normalized)
        else:
            event = MemoryKeyEvent(
                patient_id=patient.id,
                hospital_id=patient.hospital_id,
                type=normalized["type"],
                content=normalized["content"],
                impact=normalized["impact"],
                confidence=normalized["confidence"],
                source_type=normalized["source_type"],
                source_ref=normalized["source_ref"],
                evidence=normalized["evidence"],
                canonical_key=normalized["canonical_key"],
                status=normalized["status"],
                priority=normalized["priority"],
                tags=normalized["tags"],
                event_time=normalized["event_time"],
                last_confirmed_at=normalized["last_confirmed_at"],
            )
            db.add(event)
            existing_by_key[normalized["canonical_key"]] = event
        persisted_events.append(event)
    return persisted_events


def _normalize_knowledge_chunk_payload(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    domain = _normalize_text(str(payload.get("domain") or ""))
    title = _normalize_text(str(payload.get("title") or ""))
    chunk_text = _normalize_text(str(payload.get("chunk_text") or ""))
    source_type = _normalize_text(str(payload.get("source_type") or ""))
    if not domain or not title or not chunk_text or not source_type:
        return None
    confidence_raw = payload.get("confidence")
    try:
        confidence = float(confidence_raw)
    except (TypeError, ValueError):
        confidence = 0.8
    confidence = max(0.0, min(confidence, 1.0))
    return {
        "hospital_id": _normalize_text(str(payload.get("hospital_id") or "")) or None,
        "domain": domain,
        "title": title,
        "chunk_text": chunk_text,
        "source_type": source_type,
        "source_ref": _normalize_text(str(payload.get("source_ref") or "")) or None,
        "version": _normalize_text(str(payload.get("version") or "")) or None,
        "confidence": confidence,
        "tags": _normalize_tags(payload.get("tags")),
        "embedding_key": _normalize_text(str(payload.get("embedding_key") or "")) or None,
        "effective_from": _normalize_event_time(payload.get("effective_from")),
        "expires_at": _normalize_event_time(payload.get("expires_at")),
    }


def upsert_knowledge_chunk(
    db: Session,
    *,
    payload: Dict[str, Any],
) -> Optional[MemoryKnowledgeChunk]:
    normalized = _normalize_knowledge_chunk_payload(payload)
    if not normalized:
        return None

    query = db.query(MemoryKnowledgeChunk).filter(
        MemoryKnowledgeChunk.domain == normalized["domain"],
        MemoryKnowledgeChunk.title == normalized["title"],
        MemoryKnowledgeChunk.source_type == normalized["source_type"],
    )
    if normalized["hospital_id"]:
        query = query.filter(MemoryKnowledgeChunk.hospital_id == normalized["hospital_id"])
    existing = query.first()
    if existing:
        existing.hospital_id = normalized["hospital_id"]
        existing.chunk_text = normalized["chunk_text"]
        existing.source_ref = normalized["source_ref"]
        existing.version = normalized["version"]
        existing.confidence = max(float(existing.confidence or 0.0), normalized["confidence"])
        existing.tags = _merge_unique_text(existing.tags, normalized["tags"], ", ")
        existing.embedding_key = normalized["embedding_key"] or existing.embedding_key
        existing.effective_from = normalized["effective_from"] or existing.effective_from
        existing.expires_at = normalized["expires_at"] or existing.expires_at
        db.commit()
        db.refresh(existing)
        try:
            get_knowledge_retriever().upsert_chunk(existing)
        except Exception:
            pass
        return existing

    chunk = MemoryKnowledgeChunk(**normalized)
    db.add(chunk)
    db.commit()
    db.refresh(chunk)
    try:
        get_knowledge_retriever().upsert_chunk(chunk)
    except Exception:
        pass
    return chunk


def list_knowledge_chunks(
    db: Session,
    *,
    hospital_id: Optional[str] = None,
    domain: Optional[str] = None,
    limit: int = 20,
) -> List[MemoryKnowledgeChunk]:
    query = db.query(MemoryKnowledgeChunk)
    if hospital_id:
        query = query.filter(or_(MemoryKnowledgeChunk.hospital_id == hospital_id, MemoryKnowledgeChunk.hospital_id.is_(None)))
    if domain:
        query = query.filter(MemoryKnowledgeChunk.domain == domain)
    return query.order_by(MemoryKnowledgeChunk.updated_at.desc(), MemoryKnowledgeChunk.created_at.desc()).limit(limit).all()


def search_knowledge_chunks(
    db: Session,
    *,
    query_text: str,
    hospital_id: Optional[str] = None,
    domain: Optional[str] = None,
    limit: int = 5,
) -> List[MemoryKnowledgeChunk]:
    text = _normalize_text(query_text)
    if not text:
        return []
    hits = get_knowledge_retriever().search(
        db,
        query_text=text,
        hospital_id=hospital_id,
        domain=domain,
        limit=limit,
    )
    return [hit.chunk for hit in hits]


def search_knowledge_chunk_hits(
    db: Session,
    *,
    query_text: str,
    hospital_id: Optional[str] = None,
    domain: Optional[str] = None,
    limit: int = 5,
):
    text = _normalize_text(query_text)
    if not text:
        return []
    return get_knowledge_retriever().search(
        db,
        query_text=text,
        hospital_id=hospital_id,
        domain=domain,
        limit=limit,
    )


def build_knowledge_context(
    db: Session,
    *,
    query_text: str,
    hospital_id: Optional[str] = None,
    domain: Optional[str] = None,
    limit: int = 3,
) -> Optional[str]:
    return get_knowledge_retriever().build_context(
        db,
        query_text=query_text,
        hospital_id=hospital_id,
        domain=domain,
        limit=limit,
    )


def _list_patient_key_events(db: Session, patient_id: str) -> List[MemoryKeyEvent]:
    return (
        db.query(MemoryKeyEvent)
        .filter(MemoryKeyEvent.patient_id == patient_id)
        .order_by(MemoryKeyEvent.updated_at.desc(), MemoryKeyEvent.created_at.desc())
        .all()
    )


def extract_business_memory(
    db: Session,
    *,
    patient_id: str,
    hospital_id: Optional[str],
    medical_record_limit: int,
    visit_limit: int,
):
    patient = _validate_patient_context(db, patient_id=patient_id, hospital_id=hospital_id)
    medical_records = list_medical_records(db, patient.id, limit=medical_record_limit)
    visit_records = list_visit_records(db, patient.id, limit=visit_limit)
    extracted = _extract_business_with_llm(patient, medical_records, visit_records)
    fallback_events = _extract_business_events_with_rules(medical_records, visit_records)
    fallback_profile = _build_business_profile_with_rules(patient, medical_records, visit_records)

    event_payloads = extracted.get("key_events") if isinstance(extracted, dict) else None
    if not isinstance(event_payloads, list):
        event_payloads = fallback_events

    profile_payload = extracted.get("user_profile") if isinstance(extracted, dict) else None
    if not isinstance(profile_payload, dict):
        profile_payload = fallback_profile

    persisted_events = _replace_scope_events(
        db,
        patient=patient,
        scope="business",
        event_payloads=event_payloads,
    )
    business_profile = _upsert_business_profile(
        db,
        patient=patient,
        incoming_profile=_normalize_business_profile_payload(profile_payload) or {},
    )
    merged_profile = _rebuild_merged_profile(db, patient=patient)

    db.commit()
    for event in persisted_events:
        db.refresh(event)
    db.refresh(business_profile)
    db.refresh(merged_profile)

    return {
        "patient_id": patient.id,
        "hospital_id": patient.hospital_id,
        "extract_scope": "business",
        "session_id": None,
        "conversation_count": 0,
        "medical_record_count": len(medical_records),
        "visit_count": len(visit_records),
        "key_events": persisted_events,
        "user_profile": merged_profile,
    }


def extract_conversation_memory(
    db: Session,
    *,
    patient_id: str,
    hospital_id: Optional[str],
    session_id: Optional[str],
    message_limit: int,
):
    patient = _validate_patient_context(db, patient_id=patient_id, hospital_id=hospital_id)
    messages = list_conversation_messages(
        db,
        patient_id=patient.id,
        session_id=session_id,
        limit=message_limit,
    )
    preference = db.query(MemoryPreference).filter(MemoryPreference.patient_id == patient.id).first()

    extracted = _extract_conversation_with_llm(patient, preference, messages)
    fallback_events = _extract_conversation_events_with_rules(messages)
    fallback_profile = _build_conversation_profile_with_rules(preference, messages)

    event_payloads = extracted.get("key_events") if isinstance(extracted, dict) else None
    if not isinstance(event_payloads, list):
        event_payloads = fallback_events

    profile_payload = extracted.get("user_profile") if isinstance(extracted, dict) else None
    if not isinstance(profile_payload, dict):
        profile_payload = fallback_profile

    persisted_events = _replace_scope_events(
        db,
        patient=patient,
        scope="conversation",
        event_payloads=event_payloads,
    )
    conversation_profile = _upsert_conversation_profile(
        db,
        patient=patient,
        incoming_profile=_normalize_conversation_profile_payload(profile_payload) or {},
    )
    merged_profile = _rebuild_merged_profile(db, patient=patient)

    db.commit()
    for event in persisted_events:
        db.refresh(event)
    db.refresh(conversation_profile)
    db.refresh(merged_profile)

    return {
        "patient_id": patient.id,
        "hospital_id": patient.hospital_id,
        "extract_scope": "conversation",
        "session_id": session_id,
        "conversation_count": len(messages),
        "medical_record_count": 0,
        "visit_count": 0,
        "key_events": persisted_events,
        "user_profile": merged_profile,
    }


def extract_long_term_memory(
    db: Session,
    *,
    patient_id: str,
    hospital_id: Optional[str],
    session_id: Optional[str],
    message_limit: int,
    medical_record_limit: int,
    visit_limit: int,
):
    business_result = extract_business_memory(
        db,
        patient_id=patient_id,
        hospital_id=hospital_id,
        medical_record_limit=medical_record_limit,
        visit_limit=visit_limit,
    )
    conversation_result = extract_conversation_memory(
        db,
        patient_id=patient_id,
        hospital_id=hospital_id,
        session_id=session_id,
        message_limit=message_limit,
    )
    profile = db.query(MemoryUserProfile).filter(MemoryUserProfile.patient_id == patient_id).first()
    return {
        "patient_id": business_result["patient_id"],
        "hospital_id": business_result["hospital_id"],
        "extract_scope": "combined",
        "session_id": session_id,
        "conversation_count": conversation_result["conversation_count"],
        "medical_record_count": business_result["medical_record_count"],
        "visit_count": business_result["visit_count"],
        "key_events": _list_patient_key_events(db, patient_id),
        "user_profile": profile,
    }
