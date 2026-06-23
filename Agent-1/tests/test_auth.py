"""Tests for auth token issuance and verification."""

import time

import pytest
from fastapi import HTTPException

from app.mcp.auth import issue_auth_token, verify_auth_token
from app.models.patient import Patient
from app.schemas.patient import PatientCreate
from app.services.patient_service import create_patient


@pytest.fixture
def patient(db_session):
    payload = PatientCreate(
        hospital_id="hospital-test",
        patient_code="AUTH001",
        full_name="认证测试患者",
    )
    return create_patient(db_session, payload)


class TestIssueAuthToken:
    def test_issue_token_success(self, patient):
        result = issue_auth_token(
            patient_id=patient.id,
            hospital_id=patient.hospital_id,
        )
        assert "auth_token" in result
        assert result["patient_id"] == patient.id
        assert result["hospital_id"] == patient.hospital_id
        assert result["expires_at"] > int(time.time())

    def test_issue_token_custom_expiry(self, patient):
        result = issue_auth_token(
            patient_id=patient.id,
            hospital_id=patient.hospital_id,
            expires_in_minutes=5,
        )
        expected_expiry = int(time.time()) + 5 * 60
        # Allow 2-second tolerance
        assert abs(result["expires_at"] - expected_expiry) < 2

    def test_issue_token_different_patients(self, db_session):
        p1 = create_patient(db_session, PatientCreate(
            hospital_id="hosp-a", patient_code="T1", full_name="患者1",
        ))
        p2 = create_patient(db_session, PatientCreate(
            hospital_id="hosp-a", patient_code="T2", full_name="患者2",
        ))
        t1 = issue_auth_token(p1.id, p1.hospital_id)
        t2 = issue_auth_token(p2.id, p2.hospital_id)
        assert t1["auth_token"] != t2["auth_token"]


class TestVerifyAuthToken:
    def test_verify_valid_token(self, db_session, patient):
        token_data = issue_auth_token(patient.id, patient.hospital_id)
        result = verify_auth_token(db_session, token_data["auth_token"])

        assert result["authenticated"] is True
        assert result["patient_id"] == patient.id
        assert result["full_name"] == patient.full_name

    def test_verify_invalid_signature(self, db_session, patient):
        token_data = issue_auth_token(patient.id, patient.hospital_id)
        # Create a token with same structure but tampered payload
        import base64
        fake_payload = base64.urlsafe_b64encode(
            b'{"patient_id":"x","hospital_id":"x","iat":0,"exp":9999999999}'
        ).decode().rstrip("=")
        tampered_token = f"{fake_payload}.{token_data['auth_token'].split('.')[1]}"

        with pytest.raises(HTTPException) as exc:
            verify_auth_token(db_session, tampered_token)
        assert exc.value.status_code == 401
        assert "校验失败" in exc.value.detail

    def test_verify_malformed_token(self, db_session):
        with pytest.raises(HTTPException) as exc:
            verify_auth_token(db_session, "not-a-valid-token")
        assert exc.value.status_code == 401

    def test_verify_nonexistent_patient(self, db_session):
        fake_id = "00000000-0000-0000-0000-000000000000"
        token_data = issue_auth_token(fake_id, "hosp-a")

        with pytest.raises(HTTPException) as exc:
            verify_auth_token(db_session, token_data["auth_token"])
        assert exc.value.status_code == 404
        assert "不存在" in exc.value.detail

    def test_verify_inactive_patient(self, db_session):
        patient = create_patient(db_session, PatientCreate(
            hospital_id="hosp-a",
            patient_code="INACTIVE",
            full_name="已失效患者",
        ))
        patient.is_active = False
        db_session.commit()

        token_data = issue_auth_token(patient.id, patient.hospital_id)
        with pytest.raises(HTTPException) as exc:
            verify_auth_token(db_session, token_data["auth_token"])
        assert exc.value.status_code == 404
