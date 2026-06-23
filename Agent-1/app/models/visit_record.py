import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class VisitRecord(Base):
    __tablename__ = "visit_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String(36), ForeignKey("patients.id"), nullable=False, index=True)
    hospital_id = Column(String(64), nullable=False, index=True)
    visit_type = Column(String(50), nullable=False, index=True)
    department = Column(String(100), nullable=False)
    doctor_name = Column(String(100), nullable=True)
    campus = Column(String(100), nullable=True)
    chief_complaint = Column(Text, nullable=True)
    visit_status = Column(String(50), nullable=True)
    visit_summary = Column(Text, nullable=True)
    follow_up_plan = Column(Text, nullable=True)
    visit_date = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    patient = relationship("Patient", back_populates="visit_records")
