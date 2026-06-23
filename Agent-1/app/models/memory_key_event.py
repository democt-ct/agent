import uuid
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, String, Text

from app.core.database import Base


class MemoryKeyEvent(Base):
    __tablename__ = "memory_key_events_v2"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String(36), nullable=False, index=True)
    hospital_id = Column(String(64), nullable=False, index=True)
    type = Column(String(64), nullable=False, index=True)
    content = Column(Text, nullable=False)
    impact = Column(Text, nullable=False)
    confidence = Column(Float, nullable=False, default=0.8)
    source_type = Column(String(50), nullable=False, index=True)
    source_ref = Column(String(64), nullable=True, index=True)
    evidence = Column(Text, nullable=True)
    canonical_key = Column(String(255), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="active", index=True)
    priority = Column(String(20), nullable=False, default="medium")
    tags = Column(Text, nullable=True)
    event_time = Column(DateTime, nullable=True)
    last_confirmed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
