from typing import List

from pydantic import BaseModel

from app.schemas.medical_record import MedicalRecordRead
from app.schemas.patient import PatientRead
from app.schemas.visit_record import VisitRecordRead


class PatientProfileRead(BaseModel):
    patient: PatientRead
    medical_records: List[MedicalRecordRead]
    visit_records: List[VisitRecordRead]
