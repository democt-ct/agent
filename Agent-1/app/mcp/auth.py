import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any, Dict

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Patient


AUTH_SECRET = os.getenv("PATIENT_AGENT_AUTH_SECRET", "patient-agent-dev-secret")


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("utf-8").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("utf-8"))


def _sign(payload_text: str) -> str:
    return hmac.new(
        AUTH_SECRET.encode("utf-8"),
        payload_text.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def issue_auth_token(
    patient_id: str,
    hospital_id: str,
    expires_in_minutes: int = 120,
) -> Dict[str, Any]:
    now = int(time.time())
    expires_at = now + expires_in_minutes * 60
    payload = {
        "patient_id": patient_id,
        "hospital_id": hospital_id,
        "iat": now,
        "exp": expires_at,
    }
    payload_text = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    token = "{}.{}".format(
        _b64url_encode(payload_text.encode("utf-8")),
        _sign(payload_text),
    )
    return {
        "auth_token": token,
        "patient_id": patient_id,
        "hospital_id": hospital_id,
        "expires_at": expires_at,
    }


def verify_auth_token(db: Session, auth_token: str) -> Dict[str, Any]:
    try:
        encoded_payload, signature = auth_token.split(".", 1)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="认证 token 格式错误",
        ) from exc

    payload_text = _b64url_decode(encoded_payload).decode("utf-8")
    expected_signature = _sign(payload_text)
    if not hmac.compare_digest(signature, expected_signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="认证 token 校验失败",
        )

    payload = json.loads(payload_text)
    if payload["exp"] < int(time.time()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="认证 token 已过期",
        )

    patient = (
        db.query(Patient)
        .filter(
            Patient.id == payload["patient_id"],
            Patient.hospital_id == payload["hospital_id"],
            Patient.is_active.is_(True),
        )
        .first()
    )
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="认证对应的患者不存在或已失效",
        )

    return {
        "authenticated": True,
        "patient_id": patient.id,
        "hospital_id": patient.hospital_id,
        "patient_code": patient.patient_code,
        "full_name": patient.full_name,
        "expires_at": payload["exp"],
    }
