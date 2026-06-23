import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class MedicalRecord(Base):
    __tablename__ = "medical_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String(36), ForeignKey("patients.id"), nullable=False, index=True)
    hospital_id = Column(String(64), nullable=False, index=True)
    record_type = Column(String(50), nullable=False, index=True)
    title = Column(String(150), nullable=False)
    department = Column(String(100), nullable=True)
    doctor_name = Column(String(100), nullable=True)
    chief_complaint = Column(Text, nullable=True)
    present_illness = Column(Text, nullable=True)
    diagnosis = Column(Text, nullable=True)
    treatment_plan = Column(Text, nullable=True)
    medications = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    record_date = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    patient = relationship("Patient", back_populates="medical_records")
