from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.memory_business_profile import MemoryBusinessProfile
from app.models.memory_conversation_profile import MemoryConversationProfile
from app.models.memory_key_event import MemoryKeyEvent
from app.models.memory_knowledge_chunk import MemoryKnowledgeChunk
from app.models.memory_user_profile import MemoryUserProfile
from app.schemas.memory_extraction import (
    MemoryBusinessExtractRequest,
    MemoryBusinessProfileRead,
    MemoryConversationMessageCreate,
    MemoryConversationMessageRead,
    MemoryConversationPromoteRequest,
    MemoryConversationPromoteResponse,
    MemoryConversationSessionRead,
    MemoryConversationExtractRequest,
    MemoryConversationProfileRead,
    MemoryExtractRequest,
    MemoryExtractResponse,
    MemoryKeyEventRead,
    MemoryKnowledgeChunkCreate,
    MemoryKnowledgeChunkRead,
    MemoryKnowledgeChunkSearchRequest,
    MemoryKnowledgeChunkRetrieveRequest,
    MemoryKnowledgeChunkRetrievalHitRead,
    MemoryUserProfileRead,
)
from app.schemas.memory_preference import MemoryPreferenceRead, MemoryPreferenceUpsert
from app.services.memory_extraction_service import (
    create_conversation_message,
    clear_patient_long_term_memory,
    delete_conversation_messages,
    extract_business_memory,
    extract_conversation_memory,
    extract_long_term_memory,
    list_conversation_messages,
    list_conversation_sessions,
    list_knowledge_chunks,
    promote_session_buffer_to_patient,
    search_knowledge_chunks,
    search_knowledge_chunk_hits,
    upsert_knowledge_chunk,
)
from app.services.memory_preference_service import get_memory_preference, upsert_memory_preference


router = APIRouter(prefix="/api/v1/memory", tags=["memory"])


@router.get(
    "/preferences",
    response_model=MemoryPreferenceRead,
    summary="读取记忆偏好",
    description="读取某位患者已配置的长期记忆偏好与回答风格设置。",
)
def get_memory_preferences(
    patient_id: str = Query(..., description="患者 ID"),
    db: Session = Depends(get_db),
):
    return get_memory_preference(db, patient_id)


@router.put(
    "/preferences",
    response_model=MemoryPreferenceRead,
    status_code=status.HTTP_200_OK,
    summary="保存记忆偏好",
    description="创建或更新某位患者的长期记忆偏好与回答风格设置。",
)
def put_memory_preferences(
    payload: MemoryPreferenceUpsert,
    db: Session = Depends(get_db),
):
    return upsert_memory_preference(
        db,
        patient_id=payload.patient_id,
        hospital_id=payload.hospital_id,
        answer_style=payload.answer_style,
        answer_length=payload.answer_length,
        tone_style=payload.tone_style,
        medical_term_level=payload.medical_term_level,
        risk_alert_level=payload.risk_alert_level,
        preferred_language=payload.preferred_language,
        prefer_summary_first=payload.prefer_summary_first,
        prefer_step_by_step=payload.prefer_step_by_step,
        notes=payload.notes,
    )


@router.post(
    "/conversations/messages",
    response_model=MemoryConversationMessageRead,
    status_code=status.HTTP_201_CREATED,
    summary="写入短期记忆消息",
    description="将一条会话消息写入短期记忆，供后续连续对话复用。",
)
def post_conversation_message(
    payload: MemoryConversationMessageCreate,
    db: Session = Depends(get_db),
):
    return create_conversation_message(
        db,
        session_id=payload.session_id,
        patient_id=payload.patient_id,
        hospital_id=payload.hospital_id,
        role=payload.role,
        content=payload.content,
    )


@router.get(
    "/conversations/messages",
    response_model=list[MemoryConversationMessageRead],
    summary="读取短期记忆消息",
    description="按患者与会话读取已保存的短期记忆消息。",
)
def get_conversation_messages(
    patient_id: str = Query(..., description="患者 ID"),
    session_id: str | None = Query(default=None, description="会话 ID"),
    limit: int = Query(20, ge=1, le=100, description="最大返回消息数量"),
    db: Session = Depends(get_db),
):
    return list_conversation_messages(
        db,
        patient_id=patient_id,
        session_id=session_id,
        limit=limit,
    )


@router.get(
    "/conversations/sessions",
    response_model=list[MemoryConversationSessionRead],
    summary="读取最近会话",
    description="读取当前患者已保存短期记忆的最近会话列表。",
)
def get_conversation_sessions(
    patient_id: str = Query(..., description="患者 ID"),
    limit: int = Query(10, ge=1, le=30, description="最大返回会话数量"),
    db: Session = Depends(get_db),
):
    return list_conversation_sessions(
        db,
        patient_id=patient_id,
        limit=limit,
    )


@router.post(
    "/conversations/promote-session",
    response_model=MemoryConversationPromoteResponse,
    summary="绑定匿名会话到患者",
    description="将身份确认前保存在匿名会话缓冲区的消息迁移到指定患者名下，仅在确认身份后调用。",
)
def post_promote_conversation_session(
    payload: MemoryConversationPromoteRequest,
    db: Session = Depends(get_db),
):
    return promote_session_buffer_to_patient(
        db,
        session_id=payload.session_id,
        patient_id=payload.patient_id,
        hospital_id=payload.hospital_id,
    )


@router.delete(
    "/conversations/messages",
    summary="删除短期记忆消息",
    description="删除某位患者的短期记忆消息，可按 session_id 限定到单次会话。",
)
def delete_conversation_messages_endpoint(
    patient_id: str = Query(..., description="患者 ID"),
    session_id: str | None = Query(default=None, description="会话 ID；不传则删除该患者全部短期消息"),
    db: Session = Depends(get_db),
):
    deleted = delete_conversation_messages(db, patient_id=patient_id, session_id=session_id)
    return {
        "patient_id": patient_id,
        "session_id": session_id,
        "deleted_messages": deleted,
    }


@router.post(
    "/extract/business",
    response_model=MemoryExtractResponse,
    summary="抽取业务记忆",
    description="仅基于患者业务数据进行长期记忆抽取，例如病历与就诊记录。",
)
def post_business_memory_extract(
    payload: MemoryBusinessExtractRequest,
    db: Session = Depends(get_db),
):
    return extract_business_memory(
        db,
        patient_id=payload.patient_id,
        hospital_id=payload.hospital_id,
        medical_record_limit=payload.medical_record_limit,
        visit_limit=payload.visit_limit,
    )


@router.post(
    "/extract/conversation",
    response_model=MemoryExtractResponse,
    summary="抽取对话记忆",
    description="仅基于当前会话的短期对话消息进行记忆抽取。",
)
def post_conversation_memory_extract(
    payload: MemoryConversationExtractRequest,
    db: Session = Depends(get_db),
):
    return extract_conversation_memory(
        db,
        patient_id=payload.patient_id,
        hospital_id=payload.hospital_id,
        session_id=payload.session_id,
        message_limit=payload.message_limit,
    )


@router.post(
    "/extract",
    response_model=MemoryExtractResponse,
    summary="抽取长期记忆",
    description="兼容接口：会同时执行业务记忆抽取与对话记忆抽取。",
    deprecated=True,
)
def post_memory_extract(
    payload: MemoryExtractRequest,
    db: Session = Depends(get_db),
):
    return extract_long_term_memory(
        db,
        patient_id=payload.patient_id,
        hospital_id=payload.hospital_id,
        session_id=payload.session_id,
        message_limit=payload.message_limit,
        medical_record_limit=payload.medical_record_limit,
        visit_limit=payload.visit_limit,
    )


@router.get(
    "/key-events",
    response_model=list[MemoryKeyEventRead],
    summary="读取关键事件",
    description="读取某位患者已持久化保存的长期关键事件。",
)
def get_key_events(
    patient_id: str = Query(..., description="患者 ID"),
    db: Session = Depends(get_db),
):
    return (
        db.query(MemoryKeyEvent)
        .filter(MemoryKeyEvent.patient_id == patient_id)
        .order_by(MemoryKeyEvent.updated_at.desc(), MemoryKeyEvent.created_at.desc())
        .all()
    )


@router.get(
    "/user-profile",
    response_model=MemoryUserProfileRead,
    summary="读取用户画像",
    description="读取某位患者已持久化保存的长期用户画像。",
)
def get_user_profile(
    patient_id: str = Query(..., description="患者 ID"),
    db: Session = Depends(get_db),
):
    profile = db.query(MemoryUserProfile).filter(MemoryUserProfile.patient_id == patient_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="No long-term user profile has been extracted for this patient yet")
    return profile


@router.get(
    "/business-profile",
    response_model=MemoryBusinessProfileRead,
    summary="读取业务画像",
    description="读取仅由病历和就诊记录生成的业务画像。",
)
def get_business_profile(
    patient_id: str = Query(..., description="患者 ID"),
    db: Session = Depends(get_db),
):
    profile = db.query(MemoryBusinessProfile).filter(MemoryBusinessProfile.patient_id == patient_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="No business profile has been extracted for this patient yet")
    return profile


@router.get(
    "/conversation-profile",
    response_model=MemoryConversationProfileRead,
    summary="读取对话画像",
    description="读取仅由连续对话抽取的对话画像。",
)
def get_conversation_profile(
    patient_id: str = Query(..., description="患者 ID"),
    db: Session = Depends(get_db),
):
    profile = db.query(MemoryConversationProfile).filter(MemoryConversationProfile.patient_id == patient_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="No conversation profile has been extracted for this patient yet")
    return profile


@router.delete(
    "/reset",
    summary="重置患者记忆",
    description="清空患者短期消息，并可选择同时清空长期关键事件、画像和偏好。仅用于测试环境。",
)
def reset_patient_memory(
    patient_id: str = Query(..., description="患者 ID"),
    include_preferences: bool = Query(default=False, description="是否同时删除长期偏好"),
    db: Session = Depends(get_db),
):
    deleted_counts = clear_patient_long_term_memory(
        db,
        patient_id=patient_id,
        include_preferences=include_preferences,
    )
    return {
        "patient_id": patient_id,
        "deleted_counts": deleted_counts,
    }


@router.post(
    "/knowledge-chunks",
    response_model=MemoryKnowledgeChunkRead,
    status_code=status.HTTP_201_CREATED,
    summary="写入知识块",
    description="写入一条可检索的医学知识块，用于 RAG 层。",
)
def post_knowledge_chunk(
    payload: MemoryKnowledgeChunkCreate,
    db: Session = Depends(get_db),
):
    chunk = upsert_knowledge_chunk(db, payload=payload.model_dump())
    if not chunk:
        raise HTTPException(status_code=400, detail="Invalid knowledge chunk payload")
    return chunk


@router.get(
    "/knowledge-chunks",
    response_model=list[MemoryKnowledgeChunkRead],
    summary="读取知识块",
    description="按医院和领域读取可检索知识块。",
)
def get_knowledge_chunks(
    hospital_id: str | None = Query(default=None, description="Hospital ID"),
    domain: str | None = Query(default=None, description="Knowledge domain"),
    limit: int = Query(20, ge=1, le=100, description="Maximum count"),
    db: Session = Depends(get_db),
):
    return list_knowledge_chunks(db, hospital_id=hospital_id, domain=domain, limit=limit)


@router.post(
    "/knowledge-chunks/search",
    response_model=list[MemoryKnowledgeChunkRead],
    summary="搜索知识块",
    description="按自然语言查询检索相关知识块。",
)
def post_knowledge_chunk_search(
    payload: MemoryKnowledgeChunkSearchRequest,
    db: Session = Depends(get_db),
):
    return search_knowledge_chunks(
        db,
        query_text=payload.query,
        hospital_id=payload.hospital_id,
        domain=payload.domain,
        limit=payload.limit,
    )


@router.post(
    "/knowledge-chunks/retrieve",
    response_model=list[MemoryKnowledgeChunkRetrievalHitRead],
    summary="检索知识块",
    description="返回带向量分数、关键词分数和元数据分数的混合检索结果，便于调试 RAG。",
)
def post_knowledge_chunk_retrieve(
    payload: MemoryKnowledgeChunkRetrieveRequest,
    db: Session = Depends(get_db),
):
    hits = search_knowledge_chunk_hits(
        db,
        query_text=payload.query,
        hospital_id=payload.hospital_id,
        domain=payload.domain,
        limit=payload.limit,
    )
    return [
        {
            "chunk": hit.chunk,
            "vector_score": hit.vector_score,
            "keyword_score": hit.keyword_score,
            "metadata_score": hit.metadata_score,
            "recency_score": hit.recency_score,
            "final_score": hit.final_score,
            "match_reasons": hit.match_reasons,
            "citation": hit.citation,
        }
        for hit in hits
    ]
