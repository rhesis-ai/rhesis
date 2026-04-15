"""Tests for SSO audit logging."""

import logging

from rhesis.backend.app.auth.sso_audit import SSOAuditEvent, audit_log


class TestSSOAuditLog:
    """Test structured audit log emission."""

    def test_emits_log_with_all_fields(self, caplog):
        with caplog.at_level(logging.INFO, logger="rhesis.sso.audit"):
            audit_log(
                SSOAuditEvent.LOGIN_SUCCESS,
                "org-123",
                email="user@example.com",
                actor_id="user-456",
                reason_code="success",
                details={"ip": "1.2.3.4"},
            )

        assert "SSO_AUDIT" in caplog.text
        assert "sso.login.success" in caplog.text
        assert "org-123" in caplog.text
        assert "user@example.com" in caplog.text

    def test_emits_minimal_log(self, caplog):
        with caplog.at_level(logging.INFO, logger="rhesis.sso.audit"):
            audit_log(SSOAuditEvent.LOGIN_INITIATED, "org-789")

        assert "sso.login.initiated" in caplog.text
        assert "org-789" in caplog.text

    def test_all_event_types_are_valid_strings(self):
        for event in SSOAuditEvent:
            assert event.value.startswith("sso.")
