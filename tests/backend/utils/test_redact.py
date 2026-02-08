"""
Unit tests for PII redaction helpers.
"""

import pytest

from rhesis.backend.app.utils.redact import redact_email


@pytest.mark.unit
class TestRedactEmail:
    """Tests for redact_email."""

    def test_redact_email_normal(self):
        """Normal email: first two chars + domain visible."""
        assert redact_email("alice@example.com") == "al***@example.com"

    def test_redact_email_short_local(self):
        """Short local part: whole local + domain."""
        assert redact_email("ab@example.com") == "ab***@example.com"

    def test_redact_email_single_char_local(self):
        """Single character local part."""
        assert redact_email("a@example.com") == "a***@example.com"

    def test_redact_email_empty_returns_asterisks(self):
        """Empty string returns ***."""
        assert redact_email("") == "***"

    def test_redact_email_none_like_returns_asterisks(self):
        """Falsy or no @ returns ***."""
        assert redact_email("no-at-sign") == "***"

    def test_redact_email_subdomain(self):
        """Domain with subdomain preserved."""
        assert redact_email("user@mail.example.com") == "us***@mail.example.com"
