"""
Sensitive data masking utilities.

Provides functions to mask sensitive fields (phone, ID number, address)
in Pydantic model responses.
"""

import re
from typing import Any, Dict, Optional


# ── Masking Functions ──

def mask_phone(phone: Optional[str]) -> Optional[str]:
    """Mask middle 4 digits of a phone number: 138****8000"""
    if not phone:
        return phone
    cleaned = re.sub(r"\D", "", phone)
    if len(cleaned) == 11:
        return cleaned[:3] + "****" + cleaned[-4:]
    if len(cleaned) >= 8:
        return cleaned[:3] + "****" + cleaned[-4:]
    return phone


def mask_id_number(id_number: Optional[str]) -> Optional[str]:
    """Mask all but last 4 characters of an ID number."""
    if not id_number or len(id_number) <= 4:
        return id_number
    return "*" * (len(id_number) - 4) + id_number[-4:]


def mask_address(address: Optional[str], max_visible: int = 6) -> Optional[str]:
    """Mask street-level address details, keep first N chars."""
    if not address or len(address) <= max_visible:
        return address
    return address[:max_visible] + "****"


def mask_emergency_contact_phone(phone: Optional[str]) -> Optional[str]:
    """Mask emergency contact phone similarly to phone."""
    return mask_phone(phone)


# ── Response Model Helpers ──

MASK_CONFIG: Dict[str, str] = {
    "phone": "phone",
    "id_number": "id_number",
    "id_number_last4": "id_number_last4",  # already partial, no mask needed
    "address": "address",
    "emergency_contact_name": "emergency_contact",
    "emergency_contact_phone": "phone",
}

SENSITIVE_FIELDS = {"phone", "id_number", "address", "emergency_contact_phone", "emergency_contact_name"}


def mask_sensitive_fields(data: dict) -> dict:
    """Mask sensitive fields in a response dict (in-place)."""
    if "phone" in data and data["phone"]:
        data["phone"] = mask_phone(data["phone"])
    if "address" in data and data["address"]:
        data["address"] = mask_address(data["address"])
    if "emergency_contact_phone" in data and data["emergency_contact_phone"]:
        data["emergency_contact_phone"] = mask_emergency_contact_phone(data["emergency_contact_phone"])
    # id_number_hash is already hashed — safe
    # id_number_last4 is intentionally partial — safe
    return data
