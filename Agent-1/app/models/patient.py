import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, Date, DateTime, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base


class Patient(Base):
    __tablename__ = "patients"
    __table_args__ = (
        UniqueConstraint("hospital_id", "patient_code", name="uq_patient_hospital_code"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    hospital_id = Column(String(64), nullable=False, index=True)
    patient_code = Column(String(64), nullable=False, index=True)
    full_name = Column(String(100), nullable=False)
    gender = Column(String(20), nullable=True)
    birth_date = Column(Date, nullable=True)
    phone = Column(String(30), nullable=True, index=True)
    id_number_hash = Column(String(64), nullable=True, index=True)
    id_number_last4 = Column(String(4), nullable=True)
    address = Column(String(255), nullable=True)
    emergency_contact_name = Column(String(100), nullable=True)
    emergency_contact_phone = Column(String(30), nullable=True)
    blood_type = Column(String(10), nullable=True)
    allergy_history = Column(Text, nullable=True)
    family_history = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    medical_records = relationship(
        "MedicalRecord",
        back_populates="patient",
        cascade="all, delete-orphan",
        order_by="desc(MedicalRecord.record_date)",
    )
    visit_records = relationship(
        "VisitRecord",
        back_populates="patient",
        cascade="all, delete-orphan",
        order_by="desc(VisitRecord.visit_date)",
    )
