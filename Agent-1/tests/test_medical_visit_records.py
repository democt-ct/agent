"""Tests for medical record and visit record CRUD via patient_service."""

import pytest
from fastapi import HTTPException

from app.models.patient import Patient
from app.schemas.medical_record import MedicalRecordCreate, MedicalRecordUpdate
from app.schemas.patient import PatientCreate
from app.schemas.visit_record import VisitRecordCreate, VisitRecordUpdate
from app.services.patient_service import (
    create_medical_record,
    create_patient,
    create_visit_record,
    delete_medical_record,
    delete_visit_record,
    get_medical_record,
    get_visit_record,
    list_medical_records,
    list_visit_records,
    update_medical_record,
    update_visit_record,
)


@pytest.fixture
def patient(db_session, sample_patient_data):
    payload = PatientCreate(**sample_patient_data)
    return create_patient(db_session, payload)


# ── Medical Records ──


class TestCreateMedicalRecord:
    def test_create_success(self, db_session, patient, sample_medical_record_data):
        payload = MedicalRecordCreate(**sample_medical_record_data)
        record = create_medical_record(db_session, patient.id, payload)

        assert record.patient_id == patient.id
        assert record.hospital_id == patient.hospital_id
        assert record.title == sample_medical_record_data["title"]
        assert record.diagnosis == sample_medical_record_data["diagnosis"]

    def test_create_nonexistent_patient(self, db_session, sample_medical_record_data):
        payload = MedicalRecordCreate(**sample_medical_record_data)
        with pytest.raises(HTTPException) as exc:
            create_medical_record(db_session, "nonexistent", payload)
        assert exc.value.status_code == 404


class TestGetMedicalRecord:
    def test_get_success(self, db_session, patient, sample_medical_record_data):
        payload = MedicalRecordCreate(**sample_medical_record_data)
        created = create_medical_record(db_session, patient.id, payload)

        fetched = get_medical_record(db_session, patient.id, created.id)
        assert fetched.id == created.id
        assert fetched.title == created.title

    def test_get_not_found(self, db_session, patient):
        with pytest.raises(HTTPException) as exc:
            get_medical_record(db_session, patient.id, "nonexistent")
        assert exc.value.status_code == 404


class TestListMedicalRecords:
    def test_list_empty(self, db_session, patient):
        records = list_medical_records(db_session, patient.id)
        assert records == []

    def test_list_multiple(self, db_session, patient):
        for i in range(3):
            payload = MedicalRecordCreate(
                record_type="outpatient",
                title=f"测试病历{i}",
                department="心内科",
                diagnosis=f"诊断{i}",
            )
            create_medical_record(db_session, patient.id, payload)

        records = list_medical_records(db_session, patient.id)
        assert len(records) == 3

    def test_list_filter_by_type(self, db_session, patient):
        create_medical_record(
            db_session, patient.id,
            MedicalRecordCreate(record_type="outpatient", title="门诊病历"),
        )
        create_medical_record(
            db_session, patient.id,
            MedicalRecordCreate(record_type="report", title="检查报告"),
        )

        records = list_medical_records(db_session, patient.id, record_type="outpatient")
        assert len(records) == 1
        assert records[0].record_type == "outpatient"


class TestUpdateMedicalRecord:
    def test_update_success(self, db_session, patient, sample_medical_record_data):
        payload = MedicalRecordCreate(**sample_medical_record_data)
        created = create_medical_record(db_session, patient.id, payload)

        updated = update_medical_record(
            db_session, patient.id, created.id,
            MedicalRecordUpdate(diagnosis="新诊断"),
        )
        assert updated.diagnosis == "新诊断"
        assert updated.title == created.title  # unchanged


class TestDeleteMedicalRecord:
    def test_delete_success(self, db_session, patient, sample_medical_record_data):
        payload = MedicalRecordCreate(**sample_medical_record_data)
        created = create_medical_record(db_session, patient.id, payload)

        deleted = delete_medical_record(db_session, patient.id, created.id)
        assert deleted.id == created.id

        records = list_medical_records(db_session, patient.id)
        assert len(records) == 0


# ── Visit Records ──


class TestCreateVisitRecord:
    def test_create_success(self, db_session, patient, sample_visit_record_data):
        payload = VisitRecordCreate(**sample_visit_record_data)
        record = create_visit_record(db_session, patient.id, payload)

        assert record.patient_id == patient.id
        assert record.hospital_id == patient.hospital_id
        assert record.department == sample_visit_record_data["department"]

    def test_create_nonexistent_patient(self, db_session, sample_visit_record_data):
        payload = VisitRecordCreate(**sample_visit_record_data)
        with pytest.raises(HTTPException) as exc:
            create_visit_record(db_session, "nonexistent", payload)
        assert exc.value.status_code == 404


class TestListVisitRecords:
    def test_list_empty(self, db_session, patient):
        records = list_visit_records(db_session, patient.id)
        assert records == []

    def test_list_multiple(self, db_session, patient):
        for i in range(2):
            payload = VisitRecordCreate(
                visit_type="outpatient",
                department="心内科",
                doctor_name=f"医生{i}",
            )
            create_visit_record(db_session, patient.id, payload)

        records = list_visit_records(db_session, patient.id)
        assert len(records) == 2


class TestUpdateVisitRecord:
    def test_update_success(self, db_session, patient, sample_visit_record_data):
        payload = VisitRecordCreate(**sample_visit_record_data)
        created = create_visit_record(db_session, patient.id, payload)

        updated = update_visit_record(
            db_session, patient.id, created.id,
            VisitRecordUpdate(visit_summary="新摘要"),
        )
        assert updated.visit_summary == "新摘要"
        assert updated.department == created.department  # unchanged


class TestDeleteVisitRecord:
    def test_delete_success(self, db_session, patient, sample_visit_record_data):
        payload = VisitRecordCreate(**sample_visit_record_data)
        created = create_visit_record(db_session, patient.id, payload)

        deleted = delete_visit_record(db_session, patient.id, created.id)
        assert deleted.id == created.id

        records = list_visit_records(db_session, patient.id)
        assert len(records) == 0
