from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, String, Text

from app.core.database import Base


class MemoryPreference(Base):
    __tablename__ = "memory_preferences"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid4()))
    patient_id = Column(String(64), nullable=False, unique=True, index=True)
    hospital_id = Column(String(64), nullable=False, index=True)
    answer_style = Column(String(32), nullable=False, default="standard")
    answer_length = Column(String(32), nullable=False, default="standard")
    tone_style = Column(String(32), nullable=False, default="warm")
    medical_term_level = Column(String(32), nullable=False, default="plain")
    risk_alert_level = Column(String(32), nullable=False, default="medium")
    preferred_language = Column(String(32), nullable=False, default="zh-CN")
    prefer_summary_first = Column(Boolean, nullable=False, default=True)
    prefer_step_by_step = Column(Boolean, nullable=False, default=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
