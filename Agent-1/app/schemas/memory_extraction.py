from datetime import datetime
from datetime import datetime
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class MemoryConversationMessageCreate(BaseModel):
    session_id: str = Field(..., description="Session ID")
    patient_id: str = Field(..., description="Patient ID")
    hospital_id: Optional[str] = Field(default=None, description="Hospital ID")
    role: str = Field(..., description="Message role: user/assistant/system")
    content: str = Field(..., description="Message content")


class MemoryConversationMessageRead(MemoryConversationMessageCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    hospital_id: str
    created_at: datetime


class MemoryConversationSessionRead(BaseModel):
    session_id: str
    patient_id: str
    hospital_id: str
    message_count: int
    latest_message_preview: Optional[str] = None
    latest_message_at: datetime


class MemoryConversationBatchCreate(BaseModel):
    messages: List[MemoryConversationMessageCreate]


class MemoryConversationPromoteRequest(BaseModel):
    session_id: str = Field(..., description="Anonymous session ID")
    patient_id: str = Field(..., description="Patient ID")
    hospital_id: Optional[str] = Field(default=None, description="Hospital ID")


class MemoryConversationPromoteResponse(BaseModel):
    session_id: str
    patient_id: str
    hospital_id: str
    promoted_messages: int


class MemoryKeyEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    patient_id: str
    hospital_id: str
    type: str
    content: str
    impact: str
    confidence: float
    source_type: str
    source_ref: Optional[str] = None
    evidence: Optional[str] = None
    canonical_key: str
    status: str
    priority: str
    tags: Optional[str] = None
    event_time: Optional[datetime] = None
    last_confirmed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class MemoryKnowledgeChunkCreate(BaseModel):
    hospital_id: Optional[str] = Field(default=None, description="Hospital ID")
    domain: str = Field(..., description="Knowledge domain")
    title: str = Field(..., description="Chunk title")
    chunk_text: str = Field(..., description="Knowledge chunk text")
    source_type: str = Field(..., description="Source type, e.g. guideline/manual/faq")
    source_ref: Optional[str] = Field(default=None, description="Source reference")
    version: Optional[str] = Field(default=None, description="Version label")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0, description="Confidence")
    tags: Optional[str] = Field(default=None, description="Comma-separated tags")
    embedding_key: Optional[str] = Field(default=None, description="Embedding key or index key")
    effective_from: Optional[datetime] = Field(default=None, description="Effective from time")
    expires_at: Optional[datetime] = Field(default=None, description="Expiration time")


class MemoryKnowledgeChunkRead(MemoryKnowledgeChunkCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime


class MemoryKnowledgeChunkSearchRequest(BaseModel):
    query: str = Field(..., description="Search query")
    hospital_id: Optional[str] = Field(default=None, description="Hospital ID")
    domain: Optional[str] = Field(default=None, description="Optional domain filter")
    limit: int = Field(default=5, ge=1, le=20, description="Maximum returned chunks")


class MemoryKnowledgeChunkRetrievalHitRead(BaseModel):
    chunk: MemoryKnowledgeChunkRead
    vector_score: float
    keyword_score: float
    metadata_score: float
    recency_score: float
    final_score: float
    match_reasons: List[str] = Field(default_factory=list)
    citation: str


class MemoryKnowledgeChunkRetrieveRequest(MemoryKnowledgeChunkSearchRequest):
    pass


class MemoryUserProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    patient_id: str
    hospital_id: str
    profile_summary: str
    communication_preference: Optional[str] = None
    risk_focus: Optional[str] = None
    focus_topics: Optional[str] = None
    care_needs: Optional[str] = None
    source_summary: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class MemoryBusinessProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    patient_id: str
    hospital_id: str
    profile_summary: str
    risk_focus: Optional[str] = None
    focus_topics: Optional[str] = None
    care_needs: Optional[str] = None
    source_summary: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class MemoryConversationProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    patient_id: str
    hospital_id: str
    profile_summary: str
    communication_preference: Optional[str] = None
    focus_topics: Optional[str] = None
    source_summary: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class MemoryConversationExtractRequest(BaseModel):
    patient_id: str = Field(..., description="Patient ID")
    hospital_id: Optional[str] = Field(default=None, description="Hospital ID")
    session_id: Optional[str] = Field(default=None, description="Conversation session ID")
    message_limit: int = Field(default=12, ge=1, le=50, description="Maximum number of recent conversation messages to analyze")


class MemoryBusinessExtractRequest(BaseModel):
    patient_id: str = Field(..., description="Patient ID")
    hospital_id: Optional[str] = Field(default=None, description="Hospital ID")
    medical_record_limit: int = Field(default=10, ge=1, le=50, description="Maximum number of medical records to analyze")
    visit_limit: int = Field(default=10, ge=1, le=50, description="Maximum number of visit records to analyze")


class MemoryExtractRequest(BaseModel):
    patient_id: str = Field(..., description="Patient ID")
    hospital_id: Optional[str] = Field(default=None, description="Hospital ID")
    session_id: Optional[str] = Field(default=None, description="Conversation session ID")
    message_limit: int = Field(default=12, ge=1, le=50, description="Maximum number of recent conversation messages to analyze")
    medical_record_limit: int = Field(default=10, ge=1, le=50, description="Maximum number of medical records to analyze")
    visit_limit: int = Field(default=10, ge=1, le=50, description="Maximum number of visit records to analyze")


class MemoryExtractResponse(BaseModel):
    patient_id: str
    hospital_id: str
    extract_scope: Literal["conversation", "business", "combined"]
    session_id: Optional[str] = None
    conversation_count: int = 0
    medical_record_count: int = 0
    visit_count: int = 0
    key_events: List[MemoryKeyEventRead]
    user_profile: MemoryUserProfileRead
