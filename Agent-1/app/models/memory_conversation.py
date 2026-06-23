import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, String, Text

from app.core.database import Base


class MemoryConversationMessage(Base):
    __tablename__ = "memory_conversation_messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(64), nullable=False, index=True)
    patient_id = Column(String(36), nullable=False, index=True)
    hospital_id = Column(String(64), nullable=False, index=True)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
