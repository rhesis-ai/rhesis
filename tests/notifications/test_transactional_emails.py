"""
The account emails sent over SMTP must reach send_email() with a subject.

send_email() takes subject as a required argument, so a sender that drops it only
fails at runtime, when a real user asks for a verification or reset link.
"""

from unittest.mock import patch

import pytest

from rhesis.backend.notifications.email.service import EmailService
from rhesis.backend.notifications.email.template_service import EmailTemplate


def _service() -> EmailService:
    with (
        patch("rhesis.backend.notifications.email.service.SendGridClient"),
        patch("rhesis.backend.notifications.email.service.SMTPService"),
        patch("rhesis.backend.notifications.email.service.TemplateService"),
    ):
        service = EmailService()
    service.smtp_service.is_configured = True
    return service


@pytest.mark.unit
@pytest.mark.parametrize(
    ("method", "kwargs", "template", "subject"),
    [
        (
            "send_verification_email",
            {"verification_url": "https://app.rhesis.ai/auth/verify-email?token=t"},
            EmailTemplate.EMAIL_VERIFICATION,
            "Verify your email - Rhesis AI",
        ),
        (
            "send_password_reset_email",
            {"reset_url": "https://app.rhesis.ai/auth/reset-password?token=t"},
            EmailTemplate.PASSWORD_RESET,
            "Reset your password - Rhesis AI",
        ),
        (
            "send_migration_reset_email",
            {"reset_url": "https://app.rhesis.ai/auth/reset-password?token=t"},
            EmailTemplate.MIGRATION_PASSWORD_SETUP,
            "Set up your new password - Rhesis AI",
        ),
    ],
)
def test_account_emails_pass_template_and_subject(method, kwargs, template, subject):
    service = _service()
    with patch.object(service, "send_email", return_value=True) as send_email:
        assert getattr(service, method)(
            recipient_email="user@example.com", recipient_name="User", **kwargs
        )

    call = send_email.call_args.kwargs
    assert call["template"] == template
    assert call["subject"] == subject
