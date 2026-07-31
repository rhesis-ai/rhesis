"""Tests for SSO-aware team invitation emails.

An invited user in an SSO org has no Rhesis password, so the generic
"sign in with your email address" instructions send them somewhere that
cannot work. The invitation must instead point at the org's sign-in page
with `?org=<slug>`, which is what AuthForm reads to resolve the org's
identity provider.
"""

from unittest.mock import MagicMock, create_autospec, patch

import pytest

from rhesis.backend.notifications.email.sendgrid_client import SendGridClient
from rhesis.backend.notifications.email.service import EmailService
from rhesis.backend.notifications.email.template_service import (
    EmailTemplate,
    TemplateService,
)

BASE_KWARGS = {
    "recipient_email": "new.hire@example.com",
    "recipient_name": "New Hire",
    "organization_name": "Example Org",
    "organization_website": None,
    "inviter_name": "Admin",
    "inviter_email": "admin@example.com",
    "frontend_url": "https://app.example.com",
}


def _service():
    """EmailService with transports patched out, capturing send_email calls."""
    mock_sg = create_autospec(SendGridClient, instance=True)
    mock_sg.is_configured = True

    with (
        patch(
            "rhesis.backend.notifications.email.service.SendGridClient",
            return_value=mock_sg,
        ),
        patch("rhesis.backend.notifications.email.service.SMTPService"),
        patch("rhesis.backend.notifications.email.service.TemplateService"),
    ):
        service = EmailService()

    service.send_email = MagicMock(return_value=True)
    return service


def _sent_vars(service):
    """The template_variables passed to send_email."""
    return service.send_email.call_args.kwargs["template_variables"]


@pytest.mark.unit
class TestInvitationSSOLink:
    def test_sso_org_gets_org_scoped_signin_link(self):
        service = _service()

        service.send_team_invitation_email(
            **BASE_KWARGS, organization_slug="example-org", sso_enabled=True
        )

        sent = _sent_vars(service)
        assert sent["sso_enabled"] is True
        assert sent["sso_login_url"] == "https://app.example.com/?org=example-org"

    # Regression: /auth/signin looks like the login form but is the auth-code
    # callback. With no `code` it redirects to `/` forwarding only `return_to`,
    # so `org` is dropped and the org's provider is never resolved. AuthForm is
    # mounted at `/` via LoginSection.
    def test_link_does_not_target_the_auth_code_callback(self):
        service = _service()

        service.send_team_invitation_email(
            **BASE_KWARGS, organization_slug="example-org", sso_enabled=True
        )

        assert "/auth/signin" not in _sent_vars(service)["sso_login_url"]

    def test_non_sso_org_gets_no_sso_messaging(self):
        service = _service()

        service.send_team_invitation_email(
            **BASE_KWARGS, organization_slug="example-org", sso_enabled=False
        )

        sent = _sent_vars(service)
        assert sent["sso_enabled"] is False
        assert sent["sso_login_url"] == ""

    def test_defaults_to_non_sso_when_caller_omits_the_flags(self):
        service = _service()

        service.send_team_invitation_email(**BASE_KWARGS)

        sent = _sent_vars(service)
        assert sent["sso_enabled"] is False

    # Without a slug the ?org= param cannot be built, and a bare /auth/signin
    # link would not surface the org's provider. Fall back rather than emit a
    # link that silently drops the caller on the generic page.
    def test_sso_without_a_slug_falls_back(self):
        service = _service()

        service.send_team_invitation_email(**BASE_KWARGS, organization_slug=None, sso_enabled=True)

        sent = _sent_vars(service)
        assert sent["sso_enabled"] is False
        assert sent["sso_login_url"] == ""

    def test_slug_is_url_encoded(self):
        service = _service()

        service.send_team_invitation_email(
            **{**BASE_KWARGS, "frontend_url": "https://app.example.com/"},
            organization_slug="acme corp&co",
            sso_enabled=True,
        )

        sent = _sent_vars(service)
        # Single slash after the host, and the slug escaped.
        assert sent["sso_login_url"] == "https://app.example.com/?org=acme%20corp%26co"


@pytest.mark.unit
class TestInvitationTemplateRendering:
    """The real Jinja template, so the copy and href actually change."""

    def _render(self, **overrides):
        variables = {
            "recipient_email": "new.hire@example.com",
            "recipient_name": "New Hire",
            "organization_name": "Example Org",
            "organization_website": "",
            "inviter_name": "Admin",
            "inviter_email": "admin@example.com",
            "frontend_url": "https://app.example.com",
        }
        variables.update(overrides)
        return TemplateService().render_template(EmailTemplate.TEAM_INVITATION, variables)

    def test_sso_variant_links_to_the_org_signin_page(self):
        html = self._render(
            sso_enabled=True,
            sso_login_url="https://app.example.com/?org=example-org",
        )

        assert "https://app.example.com/?org=example-org" in html
        assert "single sign-on" in html.lower()
        # The email-address instruction is what misleads SSO users.
        assert "Sign in with your email address" not in html

    def test_default_variant_is_unchanged(self):
        html = self._render()

        assert "Sign in with your email address" in html
        assert "single sign-on" not in html.lower()
        assert "?org=" not in html

    # Missing required vars are filled with the string "N/A", which is truthy.
    # sso_enabled must therefore never be a declared required var, or every org
    # would get the SSO copy.
    def test_sso_enabled_is_not_a_declared_required_variable(self):
        required = TemplateService().get_template_variables(EmailTemplate.TEAM_INVITATION)

        assert "sso_enabled" not in required
        assert "sso_login_url" not in required

    def test_undefined_sso_flag_renders_the_default_variant(self):
        # sso_enabled absent entirely, mimicking any other caller of this template.
        html = self._render()

        assert "Sign in with your email address" in html
