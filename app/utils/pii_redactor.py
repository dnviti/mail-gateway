"""PII redaction utilities for GDPR-compliant logging and storage.

Provides functions to mask email addresses, names, and other personally
identifiable information before it reaches log output or persistent storage
(audit logs, dead-letter table).

Controlled by the ``PII_REDACTION_ENABLED`` setting — when disabled, all
functions return their inputs unchanged so that debugging in non-production
environments remains straightforward.
"""

from __future__ import annotations

import copy
import hashlib
from typing import Any

from app.config import settings

# Fields considered PII in webhook / email payloads.
# Keys are matched case-insensitively; nested dicts are traversed recursively.
DEFAULT_SENSITIVE_FIELDS: frozenset[str] = frozenset(
    {
        "email",
        "name",
        "customer_name",
        "recipient_email",
        "to_email",
        "to_name",
        # Stripe-specific nested paths
        "customer_email",
        "receipt_email",
        "billing_details",
    }
)

_REDACTED = "[REDACTED]"


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def redact_email(email: str) -> str:
    """Mask an email address for safe logging.

    Examples
    --------
    >>> redact_email("daniele@example.com")
    'd***@example.com'
    >>> redact_email("")
    ''
    """
    if not settings.PII_REDACTION_ENABLED:
        return email

    if not email or "@" not in email:
        return email

    local, domain = email.rsplit("@", 1)
    if len(local) <= 1:
        masked_local = "*"
    else:
        masked_local = local[0] + "***"
    return f"{masked_local}@{domain}"


def redact_name(name: str) -> str:
    """Mask a person's name for safe logging.

    Examples
    --------
    >>> redact_name("Daniele Viti")
    'D*** V***'
    >>> redact_name("")
    ''
    """
    if not settings.PII_REDACTION_ENABLED:
        return name

    if not name:
        return name

    parts = name.split()
    masked_parts = []
    for part in parts:
        if len(part) <= 1:
            masked_parts.append("*")
        else:
            masked_parts.append(part[0] + "***")
    return " ".join(masked_parts)


def pii_hash(value: str) -> str:
    """Return a SHA-256 hex digest of *value* for correlation without exposing PII."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def redact_payload(
    payload: dict[str, Any] | None,
    sensitive_fields: frozenset[str] | None = None,
) -> dict[str, Any] | None:
    """Return a deep copy of *payload* with sensitive fields replaced.

    The original dict is never mutated.  Nested dicts and lists of dicts
    are traversed recursively.  Email-shaped values get ``redact_email``;
    other sensitive values are replaced with ``[REDACTED]``.

    A ``_pii_hash`` key is added at the top level so the redacted record
    can still be correlated with the original if needed for incident
    response.

    Parameters
    ----------
    payload:
        The dict to redact.  ``None`` is returned unchanged.
    sensitive_fields:
        Field names to redact.  Defaults to ``DEFAULT_SENSITIVE_FIELDS``.
    """
    if not settings.PII_REDACTION_ENABLED:
        return payload

    if payload is None:
        return None

    if sensitive_fields is None:
        sensitive_fields = DEFAULT_SENSITIVE_FIELDS

    redacted = _redact_dict(copy.deepcopy(payload), sensitive_fields)

    # Attach a correlation hash (based on the original payload repr) so that
    # a redacted audit row can later be linked to the original event if an
    # authorised data-access request is made.
    redacted["_pii_hash"] = pii_hash(repr(payload))

    return redacted


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _is_email(value: str) -> bool:
    """Cheap heuristic — not a full RFC 5322 check."""
    return isinstance(value, str) and "@" in value and "." in value


def _redact_dict(
    d: dict[str, Any],
    sensitive_fields: frozenset[str],
) -> dict[str, Any]:
    for key in list(d.keys()):
        lower_key = key.lower()
        value = d[key]

        if lower_key in sensitive_fields:
            if isinstance(value, str):
                d[key] = redact_email(value) if _is_email(value) else _REDACTED
            elif isinstance(value, dict):
                # Replace entire nested PII object (e.g. billing_details)
                d[key] = _REDACTED
            elif isinstance(value, list):
                d[key] = _redact_list(value, sensitive_fields)
            else:
                d[key] = _REDACTED
        elif isinstance(value, dict):
            d[key] = _redact_dict(value, sensitive_fields)
        elif isinstance(value, list):
            d[key] = _redact_list(value, sensitive_fields)

    return d


def _redact_list(
    items: list[Any],
    sensitive_fields: frozenset[str],
) -> list[Any]:
    result = []
    for item in items:
        if isinstance(item, dict):
            result.append(_redact_dict(item, sensitive_fields))
        else:
            result.append(item)
    return result
