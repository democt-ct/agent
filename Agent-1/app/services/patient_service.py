import hashlib
from datetime import datetime
import re
from typing import List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import MedicalRecord, Patient, VisitRecord
from app.schemas.medical_record import MedicalRecordCreate, MedicalRecordUpdate
from app.schemas.patient import PatientCreate, PatientUpdate
from app.schemas.visit_record import VisitRecordCreate, VisitRecordUpdate


def _hash_id_number(id_number: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    if not id_number:
        return None, None

    normalized = id_number.strip().upper()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest(), normalized[-4:]


def create_patient(db: Session, payload: PatientCreate) -> Patient:
    existing = (
        db.query(Patient)
        .filter(
            Patient.hospital_id == payload.hospital_id,
            Patient.patient_code == payload.patient_code,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="当前院区下该患者编号已存在",
        )

    id_number_hash, id_number_last4 = _hash_id_number(payload.id_number)
    patient = Patient(
        hospital_id=payload.hospital_id,
        patient_code=payload.patient_code,
        full_name=payload.full_name,
        gender=payload.gender,
        birth_date=payload.birth_date,
        phone=payload.phone,
        id_number_hash=id_number_hash,
        id_number_last4=id_number_last4,
        address=payload.address,
        emergency_contact_name=payload.emergency_contact_name,
        emergency_contact_phone=payload.emergency_contact_phone,
        blood_type=payload.blood_type,
        allergy_history=payload.allergy_history,
        family_history=payload.family_history,
        notes=payload.notes,
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


def get_patient(db: Session, patient_id: str) -> Patient:
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="患者不存在",
        )
    return patient


def delete_patient(db: Session, patient_id: str) -> Patient:
    patient = get_patient(db, patient_id)
    db.delete(patient)
    db.commit()
    return patient


def update_patient(db: Session, patient_id: str, payload: PatientUpdate) -> Patient:
    patient = get_patient(db, patient_id)
    update_data = payload.model_dump(exclude_unset=True)

    # 如果传入了身份证号，重新哈希
    if "id_number" in update_data:
        id_number = update_data.pop("id_number")
        id_number_hash, id_number_last4 = _hash_id_number(id_number)
        if id_number_hash is not None:
            update_data["id_number_hash"] = id_number_hash
            update_data["id_number_last4"] = id_number_last4

    for field, value in update_data.items():
        if value is not None:
            setattr(patient, field, value)
    db.commit()
    db.refresh(patient)
    return patient


def list_patients(
    db: Session,
    hospital_id: Optional[str] = None,
    patient_code: Optional[str] = None,
    phone: Optional[str] = None,
    name: Optional[str] = None,
) -> List[Patient]:
    query = db.query(Patient)
    if hospital_id:
        query = query.filter(Patient.hospital_id == hospital_id)
    if patient_code:
        query = query.filter(Patient.patient_code == patient_code)
    if phone:
        query = query.filter(Patient.phone.ilike(f"%{phone}%"))
    if name:
        query = query.filter(Patient.full_name.ilike(f"%{name}%"))
    return query.order_by(Patient.created_at.desc()).all()


def _normalize_identity_name(value: Optional[str]) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    text = re.sub(r"[，。,.!！？?、\s]+", "", text)
    text = re.sub(r"^(我是|叫|我叫|本人|家属|患者)", "", text)
    text = re.sub(r"(阿姨|叔叔|大爷|大妈|阿伯|伯伯|姐姐|哥哥|妹妹|弟弟|老师|女士|先生|家属)$", "", text)
    return text.strip()


def _extract_birth_year_from_patient(patient: Patient) -> Optional[int]:
    if patient.birth_date:
        return patient.birth_date.year
    return None


def find_patients_by_identity_hint(
    db: Session,
    *,
    hospital_id: str,
    name_hint: Optional[str] = None,
    birth_year: Optional[int] = None,
    limit: int = 5,
) -> List[Patient]:
    patients = (
        db.query(Patient)
        .filter(Patient.hospital_id == hospital_id, Patient.is_active.is_(True))
        .order_by(Patient.created_at.desc())
        .all()
    )
    normalized_hint = _normalize_identity_name(name_hint)
    candidates: List[Patient] = []
    for patient in patients:
        stored_name = _normalize_identity_name(patient.full_name)
        if normalized_hint:
            if stored_name != normalized_hint and normalized_hint not in stored_name and stored_name not in normalized_hint:
                continue
        if birth_year is not None:
            patient_birth_year = _extract_birth_year_from_patient(patient)
            if patient_birth_year is None or patient_birth_year != birth_year:
                continue
        candidates.append(patient)
        if len(candidates) >= limit:
            break
    return candidates


def create_medical_record(
    db: Session,
    patient_id: str,
    payload: MedicalRecordCreate,
) -> MedicalRecord:
    patient = get_patient(db, patient_id)
    record = MedicalRecord(
        patient_id=patient.id,
        hospital_id=patient.hospital_id,
        record_type=payload.record_type,
        title=payload.title,
        department=payload.department,
        doctor_name=payload.doctor_name,
        chief_complaint=payload.chief_complaint,
        present_illness=payload.present_illness,
        diagnosis=payload.diagnosis,
        treatment_plan=payload.treatment_plan,
        medications=payload.medications,
        notes=payload.notes,
        record_date=payload.record_date or datetime.utcnow(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def list_medical_records(
    db: Session,
    patient_id: str,
    record_type: Optional[str] = None,
    limit: int = 20,
) -> List[MedicalRecord]:
    get_patient(db, patient_id)
    query = db.query(MedicalRecord).filter(MedicalRecord.patient_id == patient_id)
    if record_type:
        query = query.filter(MedicalRecord.record_type == record_type)
    return query.order_by(MedicalRecord.record_date.desc()).limit(limit).all()


def get_medical_record(db: Session, patient_id: str, record_id: str) -> MedicalRecord:
    get_patient(db, patient_id)
    record = (
        db.query(MedicalRecord)
        .filter(MedicalRecord.id == record_id, MedicalRecord.patient_id == patient_id)
        .first()
    )
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="病历不存在",
        )
    return record


def update_medical_record(
    db: Session, patient_id: str, record_id: str, payload: MedicalRecordUpdate
) -> MedicalRecord:
    record = get_medical_record(db, patient_id, record_id)
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None:
            setattr(record, field, value)
    db.commit()
    db.refresh(record)
    return record


def delete_medical_record(db: Session, patient_id: str, record_id: str) -> MedicalRecord:
    record = get_medical_record(db, patient_id, record_id)
    db.delete(record)
    db.commit()
    return record


def create_visit_record(
    db: Session,
    patient_id: str,
    payload: VisitRecordCreate,
) -> VisitRecord:
    patient = get_patient(db, patient_id)
    visit = VisitRecord(
        patient_id=patient.id,
        hospital_id=patient.hospital_id,
        visit_type=payload.visit_type,
        department=payload.department,
        doctor_name=payload.doctor_name,
        campus=payload.campus,
        chief_complaint=payload.chief_complaint,
        visit_status=payload.visit_status,
        visit_summary=payload.visit_summary,
        follow_up_plan=payload.follow_up_plan,
        visit_date=payload.visit_date or datetime.utcnow(),
    )
    db.add(visit)
    db.commit()
    db.refresh(visit)
    return visit


def list_visit_records(
    db: Session,
    patient_id: str,
    visit_type: Optional[str] = None,
    limit: int = 20,
) -> List[VisitRecord]:
    get_patient(db, patient_id)
    query = db.query(VisitRecord).filter(VisitRecord.patient_id == patient_id)
    if visit_type:
        query = query.filter(VisitRecord.visit_type == visit_type)
    return query.order_by(VisitRecord.visit_date.desc()).limit(limit).all()


def get_visit_record(db: Session, patient_id: str, visit_id: str) -> VisitRecord:
    get_patient(db, patient_id)
    record = (
        db.query(VisitRecord)
        .filter(VisitRecord.id == visit_id, VisitRecord.patient_id == patient_id)
        .first()
    )
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="就诊记录不存在",
        )
    return record


def update_visit_record(
    db: Session, patient_id: str, visit_id: str, payload: VisitRecordUpdate
) -> VisitRecord:
    record = get_visit_record(db, patient_id, visit_id)
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None:
            setattr(record, field, value)
    db.commit()
    db.refresh(record)
    return record


def delete_visit_record(db: Session, patient_id: str, visit_id: str) -> VisitRecord:
    record = get_visit_record(db, patient_id, visit_id)
    db.delete(record)
    db.commit()
    return record
