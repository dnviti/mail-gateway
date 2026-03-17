"""Tests for app.utils.pii_redactor."""

from unittest.mock import patch

import pytest

from app.utils.pii_redactor import (
    DEFAULT_SENSITIVE_FIELDS,
    pii_hash,
    redact_email,
    redact_error_message,
    redact_name,
    redact_payload,
)


# ---------------------------------------------------------------------------
# redact_email
# ---------------------------------------------------------------------------


class TestRedactEmail:
    def test_standard_email(self):
        assert redact_email("daniele@example.com") == "d***@example.com"

    def test_single_char_local(self):
        assert redact_email("d@example.com") == "*@example.com"

    def test_empty_string(self):
        assert redact_email("") == ""

    def test_no_at_sign(self):
        assert redact_email("not-an-email") == "not-an-email"

    def test_multi_at(self):
        # Edge case: only split on last @
        result = redact_email("user@sub@example.com")
        assert result.endswith("@example.com")

    def test_disabled(self):
        with patch("app.utils.pii_redactor.settings") as mock_settings:
            mock_settings.PII_REDACTION_ENABLED = False
            assert redact_email("daniele@example.com") == "daniele@example.com"


# ---------------------------------------------------------------------------
# redact_name
# ---------------------------------------------------------------------------


class TestRedactName:
    def test_full_name(self):
        assert redact_name("Daniele Viti") == "D*** V***"

    def test_single_name(self):
        assert redact_name("Daniele") == "D***"

    def test_single_char_name(self):
        assert redact_name("D") == "*"

    def test_empty_string(self):
        assert redact_name("") == ""

    def test_disabled(self):
        with patch("app.utils.pii_redactor.settings") as mock_settings:
            mock_settings.PII_REDACTION_ENABLED = False
            assert redact_name("Daniele Viti") == "Daniele Viti"


# ---------------------------------------------------------------------------
# redact_error_message
# ---------------------------------------------------------------------------


class TestRedactErrorMessage:
    def test_email_in_error(self):
        msg = "Delivery failed for user@example.com: mailbox full"
        assert redact_error_message(msg) == "Delivery failed for u***@example.com: mailbox full"

    def test_multiple_emails_in_error(self):
        msg = "Rejected: from alice@a.com to bob@b.com"
        result = redact_error_message(msg)
        assert "a***@a.com" in result
        assert "b***@b.com" in result

    def test_no_email_in_error(self):
        msg = "Connection timed out after 30s"
        assert redact_error_message(msg) == msg

    def test_empty_string(self):
        assert redact_error_message("") == ""

    def test_disabled(self):
        with patch("app.utils.pii_redactor.settings") as mock_settings:
            mock_settings.PII_REDACTION_ENABLED = False
            msg = "Failed for user@example.com"
            assert redact_error_message(msg) == msg


# ---------------------------------------------------------------------------
# pii_hash
# ---------------------------------------------------------------------------


class TestPiiHash:
    def test_deterministic(self):
        h1 = pii_hash("test@example.com")
        h2 = pii_hash("test@example.com")
        assert h1 == h2

    def test_different_inputs_differ(self):
        assert pii_hash("a@b.com") != pii_hash("c@d.com")

    def test_hex_string(self):
        result = pii_hash("test")
        assert len(result) == 64  # SHA-256 hex digest length

    def test_salted_hash_differs(self):
        unsalted = pii_hash("test@example.com")
        with patch("app.utils.pii_redactor.settings") as mock_settings:
            mock_settings.PII_HASH_SALT = "my-secret-salt"
            mock_settings.PII_REDACTION_ENABLED = True
            salted = pii_hash("test@example.com")
        assert unsalted != salted


# ---------------------------------------------------------------------------
# redact_payload
# ---------------------------------------------------------------------------


class TestRedactPayload:
    def test_none_input(self):
        assert redact_payload(None) is None

    def test_empty_dict(self):
        result = redact_payload({})
        assert "_pii_hash" in result

    def test_no_mutation_of_original(self):
        original = {"email": "test@example.com", "type": "event"}
        redact_payload(original)
        assert original["email"] == "test@example.com"

    def test_email_field_redacted(self):
        payload = {"email": "test@example.com", "type": "invoice.paid"}
        result = redact_payload(payload)
        assert result["email"] == "t***@example.com"
        assert result["type"] == "invoice.paid"

    def test_name_field_redacted(self):
        payload = {"name": "John Doe", "id": "123"}
        result = redact_payload(payload)
        assert result["name"] == "[REDACTED]"
        assert result["id"] == "123"

    def test_nested_dict(self):
        payload = {
            "data": {
                "object": {
                    "email": "user@domain.org",
                    "status": "active",
                }
            }
        }
        result = redact_payload(payload)
        assert result["data"]["object"]["email"] == "u***@domain.org"
        assert result["data"]["object"]["status"] == "active"

    def test_list_of_dicts(self):
        payload = {
            "to": [
                {"email": "alice@b.com", "name": "Alice"},
                {"email": "carol@d.com", "name": "Bob"},
            ]
        }
        result = redact_payload(payload)
        assert result["to"][0]["email"] == "a***@b.com"
        assert result["to"][0]["name"] == "[REDACTED]"
        assert result["to"][1]["email"] == "c***@d.com"

    def test_pii_hash_present(self):
        payload = {"email": "test@example.com"}
        result = redact_payload(payload)
        assert "_pii_hash" in result
        assert len(result["_pii_hash"]) == 64

    def test_custom_sensitive_fields(self):
        payload = {"custom_field": "secret", "safe_field": "ok"}
        result = redact_payload(payload, sensitive_fields=frozenset({"custom_field"}))
        assert result["custom_field"] == "[REDACTED]"
        assert result["safe_field"] == "ok"

    def test_case_insensitive_keys(self):
        payload = {"Email": "test@example.com", "NAME": "Test"}
        result = redact_payload(payload)
        assert result["Email"] == "t***@example.com"
        assert result["NAME"] == "[REDACTED]"

    def test_billing_details_redacted(self):
        payload = {
            "billing_details": {"address": {"city": "Rome"}, "name": "Test"},
            "amount": 1000,
        }
        result = redact_payload(payload)
        assert result["billing_details"] == "[REDACTED]"
        assert result["amount"] == 1000

    def test_disabled(self):
        with patch("app.utils.pii_redactor.settings") as mock_settings:
            mock_settings.PII_REDACTION_ENABLED = False
            payload = {"email": "test@example.com"}
            result = redact_payload(payload)
            assert result["email"] == "test@example.com"

    def test_recipient_email_field(self):
        payload = {"recipient_email": "user@test.com", "template_id": "welcome"}
        result = redact_payload(payload)
        assert result["recipient_email"] == "u***@test.com"
        assert result["template_id"] == "welcome"
