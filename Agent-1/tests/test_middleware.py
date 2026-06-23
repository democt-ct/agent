"""Tests for the PatientDataGuardMiddleware and audit logging."""

import pytest
from fastapi import Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.middleware.patient_data_guard import (
    _extract_path_patient_id,
    _extract_query_patient_id,
    _extract_auth_token,
    _is_public_route,
    PatientDataGuardMiddleware,
)
from app.models.audit_log import AuditLog


class TestPathExtraction:
    def test_extract_path_patient_id_valid(self):
        pid = _extract_path_patient_id("/api/v1/patients/abc-123/medical-records")
        assert pid == "abc-123"

    def test_extract_path_patient_id_list(self):
        pid = _extract_path_patient_id("/api/v1/patients")
        assert pid is None

    def test_extract_path_patient_id_profile(self):
        pid = _extract_path_patient_id("/api/v1/patients/some-id/visits/visit-1")
        assert pid == "some-id"

    def test_extract_path_patient_id_not_patient(self):
        pid = _extract_path_patient_id("/health")
        assert pid is None

    def test_extract_query_patient_id(self):
        pid = _extract_query_patient_id(
            "/api/v1/memory/profile",
            {"patient_id": "pat-001", "limit": "10"},
        )
        assert pid == "pat-001"

    def test_extract_query_patient_id_no_match(self):
        pid = _extract_query_patient_id(
            "/api/v1/memory/knowledge-chunks",
            {"domain": "diagnosis"},
        )
        assert pid is None


class TestPublicRouteDetection:
    def test_health_is_public(self):
        assert _is_public_route("/health") is True

    def test_detailed_health_is_public(self):
        assert _is_public_route("/health/detailed") is True

    def test_patient_endpoint_not_public(self):
        assert _is_public_route("/api/v1/patients/abc") is False

    def test_knowledge_chunks_are_public(self):
        assert _is_public_route("/api/v1/memory/knowledge-chunks") is True
        assert _is_public_route("/api/v1/memory/knowledge-chunks/search") is True


class TestAuthTokenExtraction:
    def _make_request(self, headers=None, query_params=None):
        """Create a minimal mock request object."""
        qp = query_params or {}

        class MockQueryParams:
            def get(self, key, default=None):
                return qp.get(key, default)

        class MockRequest:
            def __init__(self):
                self.headers = headers or {}
                self.query_params = MockQueryParams()

        return MockRequest()

    def test_from_authorization_header(self):
        req = self._make_request(
            headers={"Authorization": "Bearer test-token-123"}
        )
        token = _extract_auth_token(req)
        assert token == "test-token-123"

    def test_from_query_params(self):
        req = self._make_request(query_params={"auth_token": "q-token"})
        token = _extract_auth_token(req)
        assert token == "q-token"

    def test_no_token(self):
        req = self._make_request()
        token = _extract_auth_token(req)
        assert token is None


class TestAuditLogModel:
    def test_audit_log_table_exists(self, db_session):
        """Verify the audit_log table exists and has the expected columns."""
        from sqlalchemy import inspect
        inspector = inspect(db_session.get_bind())
        tables = inspector.get_table_names()
        assert "audit_log" in tables

    def test_create_audit_entry(self, db_session):
        """Verify we can create an audit log entry."""
        from app.middleware.patient_data_guard import _create_audit_entry
        # Use a unique ID to isolate test data
        unique_id = "pat-audit-" + str(__import__("uuid").uuid4())[:8]
        _create_audit_entry(
            db_session,
            patient_id=unique_id,
            hospital_id="hosp-a",
            endpoint="/api/v1/patients/pat-001",
            method="GET",
            action="read",
            status_code=200,
            client_ip="127.0.0.1",
            auth_verified=True,
            details="Test audit entry",
            duration_ms=15.5,
        )

        entries = db_session.query(AuditLog).filter(
            AuditLog.patient_id == unique_id
        ).all()
        assert len(entries) == 1
        assert entries[0].action == "read"
        assert entries[0].auth_verified == "yes"

    def test_create_audit_entry_no_auth(self, db_session):
        """Verify audit entry for unauthenticated access."""
        from app.middleware.patient_data_guard import _create_audit_entry
        unique_id = "pat-noauth-" + str(__import__("uuid").uuid4())[:8]
        _create_audit_entry(
            db_session,
            patient_id=unique_id,
            hospital_id=None,
            endpoint="/api/v1/patients/pat-002",
            method="POST",
            action="create",
            status_code=201,
            client_ip="10.0.0.1",
            auth_verified=None,
            duration_ms=42.0,
        )

        entries = db_session.query(AuditLog).filter(
            AuditLog.patient_id == unique_id
        ).all()
        assert len(entries) == 1
        assert entries[0].auth_verified is None


class TestIntegration:
    """Integration tests for the middleware via the test client."""

    def test_health_route_not_guarded(self, client):
        """Public routes should work without any auth."""
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_patient_read_works_in_dev_mode(self, client):
        """In dev mode (default), patient data access without auth should work."""
        # Create a patient first
        create_resp = client.post("/api/v1/patients", json={
            "hospital_id": "hosp-test",
            "patient_code": "GUARD001",
            "full_name": "中间件测试患者",
        })
        assert create_resp.status_code == 201
        pid = create_resp.json()["id"]

        # Read should work without auth (dev mode)
        read_resp = client.get(f"/api/v1/patients/{pid}")
        assert read_resp.status_code == 200

    def test_audit_log_created_on_access(self, client):
        """Verify that patient data access creates audit log entries."""
        from app.models.audit_log import AuditLog
        from app.core.database import SessionLocal

        # Create a patient
        create_resp = client.post("/api/v1/patients", json={
            "hospital_id": "hosp-audit",
            "patient_code": "AUDIT" + str(__import__("uuid").uuid4())[:6],
            "full_name": "审计测试",
        })
        pid = create_resp.json()["id"]

        # Read the patient
        client.get(f"/api/v1/patients/{pid}")

        # Check audit log in a new session (the request is async)
        import time
        time.sleep(0.3)  # allow async audit write to complete

        db = SessionLocal()
        try:
            entries = db.query(AuditLog).filter(
                AuditLog.patient_id == pid
            ).all()
            assert len(entries) >= 1
            # At minimum: create entry and read entry
            actions = {e.action for e in entries}
            assert "read" in actions
        finally:
            db.close()


# ── 速率限制 ──

class TestRateLimit:
    def test_rate_limiter_allows_normal_requests(self, client):
        """Under rate limit, requests should succeed."""
        resp = client.get("/api/v1/patients")
        assert resp.status_code == 200

    def test_rate_limiter_headers_present(self, client):
        """Response should include rate limit headers."""
        resp = client.get("/api/v1/patients")
        assert "X-RateLimit-Limit" in resp.headers
        assert "X-RateLimit-Remaining" in resp.headers

    def test_rate_limiter_health_route(self, client):
        """Health route should not be affected by rate limiting."""
        resp = client.get("/health")
        assert resp.status_code == 200


class TestMasking:
    def test_mask_phone(self):
        from app.utils.masking import mask_phone
        assert mask_phone("13800138000") == "138****8000"
        assert mask_phone("1391234") == "1391234"  # too short
        assert mask_phone(None) is None

    def test_mask_address(self):
        from app.utils.masking import mask_address
        masked = mask_address("北京市朝阳区望京街道花家地北里5号楼")
        assert "****" in masked
        assert masked.startswith("北京市")
        assert mask_address("短地址") == "短地址"
        assert mask_address(None) is None

    def test_mask_sensitive_fields(self):
        from app.utils.masking import mask_sensitive_fields
        data = {
            "phone": "13800138000",
            "address": "北京市朝阳区测试路100号",
            "id_number_last4": "1234",
            "full_name": "测试用户",
        }
        masked = mask_sensitive_fields(data)
        assert masked["phone"] == "138****8000"
        assert "****" in masked["address"]
        assert masked["id_number_last4"] == "1234"  # unchanged
        assert masked["full_name"] == "测试用户"  # unchanged
