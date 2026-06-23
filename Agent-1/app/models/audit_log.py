import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, String, Text

from app.core.database import Base


class AuditLog(Base):
    """Audit log for patient data access tracking."""

    __tablename__ = "audit_log"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String(36), nullable=True, index=True)
    hospital_id = Column(String(64), nullable=True)
    endpoint = Column(String(255), nullable=False)
    method = Column(String(10), nullable=False)
    action = Column(String(50), nullable=False, index=True)
    status_code = Column(String(10), nullable=True)
    client_ip = Column(String(50), nullable=True)
    auth_verified = Column(String(10), nullable=True)
    details = Column(Text, nullable=True)
    duration_ms = Column(Float, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
