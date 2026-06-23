import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, String, Text

from app.core.database import Base


class MemoryKnowledgeChunk(Base):
    __tablename__ = "memory_knowledge_chunks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    hospital_id = Column(String(64), nullable=True, index=True)
    domain = Column(String(64), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    chunk_text = Column(Text, nullable=False)
    source_type = Column(String(50), nullable=False, index=True)
    source_ref = Column(String(128), nullable=True, index=True)
    version = Column(String(64), nullable=True)
    confidence = Column(Float, nullable=False, default=0.8)
    tags = Column(Text, nullable=True)
    embedding_key = Column(String(128), nullable=True, index=True)
    effective_from = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
