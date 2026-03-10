"""
RenewAI – PII Masking Utility
================================
Masks personal identifiable information before it reaches external channels
or audit logs, in compliance with DPDPA / IRDAI data-protection norms.
"""

import re
from typing import Any, Dict


def mask_phone(phone: str) -> str:
    """'+919876543210' → '+91****543210'"""
    if not phone:
        return phone
    digits = re.sub(r"\D", "", phone)
    if len(digits) <= 4:
        return "****"
    return phone[: len(phone) - len(digits)] + digits[:2] + "****" + digits[-4:]


def mask_email(email: str) -> str:
    """'rajesh.kumar@example.com' → 'ra****@example.com'"""
    if not email or "@" not in email:
        return email
    local, domain = email.split("@", 1)
    visible = min(2, len(local))
    return local[:visible] + "****@" + domain


def mask_name(name: str) -> str:
    """'Rajesh Kumar' → 'R**** K****'"""
    if not name:
        return name
    parts = name.split()
    return " ".join(p[0] + "****" for p in parts if p)


def mask_policy_id(pid: str) -> str:
    """'POL-1001' → 'POL-****01'"""
    if not pid or len(pid) < 4:
        return pid
    return pid[:4] + "****" + pid[-2:]


def mask_dict(data: dict, fields_to_mask: set = None) -> dict:
    """
    Return a shallow copy of *data* with sensitive fields masked.
    Default fields: phone, email, full_name, customer_id.
    """
    if fields_to_mask is None:
        fields_to_mask = {"phone", "email", "full_name", "customer_id"}

    maskers = {
        "phone": mask_phone,
        "email": mask_email,
        "full_name": mask_name,
        "customer_id": lambda x: x[:5] + "****" if x and len(x) > 5 else x,
    }

    masked = dict(data)
    for field in fields_to_mask:
        if field in masked and masked[field]:
            fn = maskers.get(field, lambda x: "****")
            masked[field] = fn(masked[field])
    return masked


def mask_for_audit(payload: Any) -> Any:
    """Recursively mask PII in nested dicts / lists for audit logging."""
    if isinstance(payload, dict):
        return {k: mask_for_audit(v) for k, v in payload.items()}
    if isinstance(payload, list):
        return [mask_for_audit(item) for item in payload]
    if isinstance(payload, str):
        # Phone pattern
        payload = re.sub(r"\+\d{2}\d{10}", lambda m: mask_phone(m.group()), payload)
        # Email pattern
        payload = re.sub(
            r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
            lambda m: mask_email(m.group()),
            payload,
        )
    return payload
