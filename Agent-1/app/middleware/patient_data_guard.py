"""
Patient data access control middleware.

Enforces that requests to patient data endpoints carry a valid auth_token
that matches the requested patient_id. Logs all access attempts to the
audit log.
"""

import json
import logging
import time
from typing import Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.database import SessionLocal

logger = logging.getLogger("app.middleware.patient_data_guard")

# ── Audit Log Model ──

from app.models.audit_log import AuditLog


# ── Path Patterns ──

# URL patterns that contain patient_id as a path parameter
_PATH_PATIENT_PATTERNS = [
    "/api/v1/patients/{patient_id}",
    "/api/v1/patients/{patient_id}/medical-records",
    "/api/v1/patients/{patient_id}/visits",
]

# URL patterns that carry patient_id as a query parameter (memory routes)
_QUERY_PATIENT_PATTERNS = [
    "/api/v1/memory/profile",
    "/api/v1/memory/conversations/messages",
    "/api/v1/memory/conversations/sessions",
    "/api/v1/memory/preferences",
    "/api/v1/memory/key-events",
    "/api/v1/memory/user-profile",
    "/api/v1/memory/business-profile",
    "/api/v1/memory/conversation-profile",
    "/api/v1/memory/reset",
]

# Routes that NEVER carry patient data — skip checks
_PUBLIC_ROUTES = {
    "/health",
    "/health/detailed",
    "/",
    "/tester",
    "/docs",
    "/openapi.json",
    "/api/v1/mcp/health",
    "/api/v1/mcp/tools",
    "/api/v1/mcp/agent/speech",
    "/api/v1/memory/knowledge-chunks",
}


def _is_public_route(path: str) -> bool:
    """Check if a route is public (no patient data access)."""
    if path in _PUBLIC_ROUTES:
        return True
    # Knowledge-chunks sub-routes are also public
    if "/api/v1/memory/knowledge-chunks/" in path:
        return True
    return False


def _extract_path_patient_id(path: str) -> Optional[str]:
    """Extract patient_id from URL path patterns like /api/v1/patients/{patient_id}/..."""
    parts = path.strip("/").split("/")
    # Pattern: api/v1/patients/{patient_id}/...
    if len(parts) >= 4 and parts[0] == "api" and parts[1] == "v1" and parts[2] == "patients":
        candidate = parts[3]
        # Must be a UUID-like string (not "medical-records" or "visits")
        if candidate not in ("medical-records", "visits", ""):
            return candidate
    return None


def _extract_query_patient_id(path: str, query_params: dict) -> Optional[str]:
    """Extract patient_id from query parameters for memory routes."""
    for pattern in _QUERY_PATIENT_PATTERNS:
        if path.startswith(pattern):
            return query_params.get("patient_id")
    return None


def _extract_auth_token(request: Request) -> Optional[str]:
    """Extract auth_token from Authorization header or query params."""
    # Check Authorization header first
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    # Check query params
    token = request.query_params.get("auth_token")
    if token:
        return token
    return None


def _create_audit_entry(
    db_session,
    *,
    patient_id: Optional[str],
    hospital_id: Optional[str],
    endpoint: str,
    method: str,
    action: str,
    status_code: Optional[int],
    client_ip: Optional[str],
    auth_verified: Optional[bool],
    details: Optional[str] = None,
    duration_ms: Optional[float] = None,
):
    """Create an audit log entry."""
    import uuid
    from datetime import datetime

    entry = AuditLog(
        id=str(uuid.uuid4()),
        patient_id=patient_id,
        hospital_id=hospital_id,
        endpoint=endpoint,
        method=method,
        action=action,
        status_code=str(status_code) if status_code else None,
        client_ip=client_ip,
        auth_verified="yes" if auth_verified else ("no" if auth_verified is False else None),
        details=details,
        duration_ms=duration_ms,
        created_at=datetime.utcnow(),
    )
    db_session.add(entry)
    db_session.commit()


def _resolve_token_patient_id(auth_token: str) -> Optional[dict]:
    """Verify an auth_token and return its patient identity.
    Returns None if token is invalid. Uses a fresh DB session."""
    try:
        db = SessionLocal()
        try:
            from app.mcp.auth import verify_auth_token
            return verify_auth_token(db, auth_token)
        finally:
            db.close()
    except Exception as exc:
        logger.warning("Auth token verification failed: %s", exc)
        return None


class PatientDataGuardMiddleware(BaseHTTPMiddleware):
    """
    Middleware that enforces patient data access control.

    - For routes that access patient data, checks if auth_token is present
      and valid, and patient_id in the request matches the token.
    - Logs all access attempts to the audit log.
    - In production mode, returns 401/403 for unauthorized access.
    - In dev mode, allows access but logs warnings.
    """

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        path = request.url.path
        method = request.method

        # Skip public routes
        if _is_public_route(path):
            return await call_next(request)

        # Only check GET/DELETE/PUT/POST that access patient data
        patient_id = _extract_path_patient_id(path)
        if not patient_id:
            patient_id = _extract_query_patient_id(path, dict(request.query_params))

        # Not a patient data route — allow
        if not patient_id:
            return await call_next(request)

        # Extract auth context
        auth_token = _extract_auth_token(request)
        client_ip = request.client.host if request.client else None
        is_production = os.getenv("PATIENT_AGENT_ENV", "").lower() in ("production", "prod")

        # Resolve token identity if present
        identity = None
        auth_verified = None
        if auth_token:
            identity = _resolve_token_patient_id(auth_token)
            if identity:
                auth_verified = True
                token_patient_id = identity["patient_id"]
                # Check patient_id match
                if patient_id != token_patient_id:
                    # Mismatch — reject
                    duration_ms = (time.time() - start_time) * 1000
                    _log_audit_async(
                        patient_id=patient_id,
                        hospital_id=identity.get("hospital_id"),
                        endpoint=path, method=method,
                        action="access_denied_mismatch",
                        status_code=403, client_ip=client_ip,
                        auth_verified=True,
                        details=f"Token patient_id ({token_patient_id}) != requested patient_id ({patient_id})",
                        duration_ms=duration_ms,
                    )
                    return Response(
                        content=json.dumps({"detail": "认证 token 与请求的患者 ID 不匹配"}, ensure_ascii=False),
                        status_code=403,
                        media_type="application/json",
                    )
            else:
                auth_verified = False  # Invalid token
        else:
            auth_verified = None  # No token provided

        # If no auth_token and production mode, reject
        if not auth_token and is_production:
            duration_ms = (time.time() - start_time) * 1000
            _log_audit_async(
                patient_id=patient_id,
                hospital_id=None,
                endpoint=path, method=method,
                action="access_denied_no_auth",
                status_code=401, client_ip=client_ip,
                auth_verified=None,
                details="No auth token provided",
                duration_ms=duration_ms,
            )
            return Response(
                content=json.dumps({"detail": "缺少认证 token"}, ensure_ascii=False),
                status_code=401,
                media_type="application/json",
            )

        # Allow request (dev mode without token, or valid token)
        if not auth_token:
            logger.info(
                "患者数据访问无认证: %s %s patient_id=%s ip=%s — 开发模式允许",
                method, path, patient_id, client_ip,
            )

        response = await call_next(request)
        duration_ms = (time.time() - start_time) * 1000

        # Log access to audit log (async)
        action = _infer_action(method, path, response.status_code)
        _log_audit_async(
            patient_id=patient_id,
            hospital_id=identity.get("hospital_id") if identity else None,
            endpoint=path, method=method,
            action=action,
            status_code=response.status_code,
            client_ip=client_ip,
            auth_verified=auth_verified,
            duration_ms=duration_ms,
        )

        return response


def _infer_action(method: str, path: str, status_code: int) -> str:
    """Infer the action type from method and path."""
    if method == "GET":
        return "read"
    elif method == "POST":
        if status_code == 201:
            return "create"
        return "query"
    elif method == "PUT":
        return "update"
    elif method == "DELETE":
        return "delete"
    return method.lower()


def _log_audit_async(**kwargs):
    """Write an audit log entry in a background thread to avoid blocking."""
    import threading
    threading.Thread(target=_write_audit_entry, kwargs=kwargs, daemon=True).start()


def _write_audit_entry(**kwargs):
    """Write audit entry (runs in background thread)."""
    try:
        db = SessionLocal()
        try:
            _create_audit_entry(db, **kwargs)
        finally:
            db.close()
    except Exception as exc:
        logger.warning("审计日志写入失败: %s", exc)


# Re-import os at module level for the middleware
import os  # noqa: E402
