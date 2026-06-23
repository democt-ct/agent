"""Tests for patient_service CRUD operations."""

from datetime import date

import pytest
from fastapi import HTTPException

from app.models.patient import Patient
from app.schemas.patient import PatientCreate, PatientUpdate
from app.services.patient_service import (
    create_patient,
    delete_patient,
    get_patient,
    list_patients,
    update_patient,
)


class TestCreatePatient:
    def test_create_patient_success(self, db_session, sample_patient_data):
        payload = PatientCreate(**sample_patient_data)
        patient = create_patient(db_session, payload)

        assert patient.full_name == sample_patient_data["full_name"]
        assert patient.hospital_id == sample_patient_data["hospital_id"]
        assert patient.patient_code == sample_patient_data["patient_code"]
        assert patient.phone == sample_patient_data["phone"]
        assert patient.is_active is True
        assert patient.id is not None

    def test_create_patient_duplicate_code(self, db_session, sample_patient_data):
        payload = PatientCreate(**sample_patient_data)
        create_patient(db_session, payload)

        with pytest.raises(HTTPException) as exc:
            create_patient(db_session, payload)
        assert exc.value.status_code == 409

    def test_create_patient_with_id_number(self, db_session):
        payload = PatientCreate(
            hospital_id="hospital-a",
            patient_code="ID001",
            full_name="身份证测试",
            id_number="110101199001011234",
        )
        patient = create_patient(db_session, payload)
        assert patient.id_number_hash is not None
        assert patient.id_number_last4 == "1234"

    def test_create_patient_minimal_fields(self, db_session):
        payload = PatientCreate(
            hospital_id="hospital-a",
            patient_code="MIN001",
            full_name="最小字段",
        )
        patient = create_patient(db_session, payload)
        assert patient.full_name == "最小字段"
        assert patient.gender is None


class TestGetPatient:
    def test_get_patient_success(self, db_session, sample_patient_data):
        payload = PatientCreate(**sample_patient_data)
        created = create_patient(db_session, payload)

        fetched = get_patient(db_session, created.id)
        assert fetched.id == created.id
        assert fetched.full_name == created.full_name

    def test_get_patient_not_found(self, db_session):
        with pytest.raises(HTTPException) as exc:
            get_patient(db_session, "nonexistent-id")
        assert exc.value.status_code == 404


class TestUpdatePatient:
    def test_update_patient_name(self, db_session, sample_patient_data):
        payload = PatientCreate(**sample_patient_data)
        created = create_patient(db_session, payload)

        update_payload = PatientUpdate(full_name="新名字")
        updated = update_patient(db_session, created.id, update_payload)
        assert updated.full_name == "新名字"
        assert updated.phone == created.phone  # unchanged

    def test_update_patient_id_number_rehash(self, db_session, sample_patient_data):
        payload = PatientCreate(**sample_patient_data)
        created = create_patient(db_session, payload)

        update_payload = PatientUpdate(id_number="220101199501011234")
        updated = update_patient(db_session, created.id, update_payload)
        assert updated.id_number_last4 == "1234"
        assert updated.id_number_hash is not None

    def test_update_patient_not_found(self, db_session):
        with pytest.raises(HTTPException) as exc:
            update_patient(db_session, "nonexistent", PatientUpdate(full_name="x"))
        assert exc.value.status_code == 404


class TestDeletePatient:
    def test_delete_patient_success(self, db_session, sample_patient_data):
        payload = PatientCreate(**sample_patient_data)
        created = create_patient(db_session, payload)

        deleted = delete_patient(db_session, created.id)
        assert deleted.id == created.id

        with pytest.raises(HTTPException) as exc:
            get_patient(db_session, created.id)
        assert exc.value.status_code == 404

    def test_delete_patient_not_found(self, db_session):
        with pytest.raises(HTTPException) as exc:
            delete_patient(db_session, "nonexistent")
        assert exc.value.status_code == 404


class TestListPatients:
    _UNIQUE_HOSP = "utest-list-isolated"

    def test_list_patients_empty(self, db_session):
        patients = list_patients(db_session, hospital_id=self._UNIQUE_HOSP)
        assert patients == []

    def test_list_patients_all(self, db_session):
        for i in range(3):
            payload = PatientCreate(
                hospital_id=self._UNIQUE_HOSP,
                patient_code=f"LST00{i}",
                full_name=f"患者{i}",
            )
            create_patient(db_session, payload)

        patients = list_patients(db_session, hospital_id=self._UNIQUE_HOSP)
        assert len(patients) == 3

    def test_list_patients_filter_by_hospital(self, db_session):
        for hid in ["hosp-a", "hosp-b"]:
            payload = PatientCreate(
                hospital_id=hid,
                patient_code=f"FILTER-{hid}",
                full_name=f"{hid}患者",
            )
            create_patient(db_session, payload)

        result = list_patients(db_session, hospital_id="hosp-a")
        assert len(result) == 1
        assert result[0].hospital_id == "hosp-a"

    def test_list_patients_filter_by_phone(self, db_session):
        payload = PatientCreate(
            hospital_id="hosp-a",
            patient_code="PH001",
            full_name="电话测试",
            phone="13912345678",
        )
        create_patient(db_session, payload)

        result = list_patients(db_session, phone="1391234")
        assert len(result) == 1
        assert result[0].phone == "13912345678"

    def test_list_patients_filter_by_name(self, db_session):
        payload = PatientCreate(
            hospital_id="hosp-a",
            patient_code="NM001",
            full_name="王测试",
        )
        create_patient(db_session, payload)

        result = list_patients(db_session, name="王测试")
        assert len(result) == 1
        assert result[0].full_name == "王测试"

        result = list_patients(db_session, name="不存在")
        assert len(result) == 0
