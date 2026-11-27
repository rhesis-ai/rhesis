"""
Outgoing mail is sent under the recipient organization's product name.

The address always comes from configuration. Without a product name the configured
value is used as written, so nothing adds a name the operator did not set.
"""

from email.utils import parseaddr
from unittest.mock import create_autospec, patch

import pytest

from rhesis.backend.notifications.email.brand import OrganizationBrand
from rhesis.backend.notifications.email.sender import sender_with_name
from rhesis.backend.notifications.email.sendgrid_client import SendGridClient
from rhesis.backend.notifications.email.service import EmailService
from rhesis.backend.notifications.email.template_service import EmailTemplate


@pytest.mark.unit
class TestSenderWithName:
    def test_without_a_name_the_configured_value_is_used_as_written(self):
        assert sender_with_name("noreply@example.com", None) == "noreply@example.com"
        assert (
            sender_with_name('"Ops" <noreply@example.com>', None) == '"Ops" <noreply@example.com>'
        )

    def test_the_name_replaces_the_configured_one_and_keeps_the_address(self):
        sender = sender_with_name('"Ops" <noreply@example.com>', "Acme Evals")
        assert parseaddr(sender) == ("Acme Evals", "noreply@example.com")

    def test_a_name_with_quotes_and_commas_stays_one_name(self):
        sender = sender_with_name("noreply@example.com", 'Acme "Labs", Inc.')
        assert parseaddr(sender) == ('Acme "Labs", Inc.', "noreply@example.com")

    def test_a_non_ascii_name_is_encoded_for_the_header(self):
        sender = sender_with_name("noreply@example.com", "Zürich AI")
        assert sender.isascii()
        assert SendGridClient._parse_email_address(sender) == ("noreply@example.com", "Zürich AI")


ACME = OrganizationBrand(product_name="Acme Evals")


def _smtp_service() -> EmailService:
    with (
        patch("rhesis.backend.notifications.email.service.SendGridClient"),
        patch("rhesis.backend.notifications.email.service.SMTPService"),
        patch("rhesis.backend.notifications.email.service.TemplateService"),
    ):
        service = EmailService()
    service.smtp_service.is_configured = True
    service.smtp_service.from_email = "noreply@example.com"
    service.template_service.render_template.return_value = "<p>hi</p>"
    return service


def _sent_from(service: EmailService, **kwargs) -> str:
    service.send_email(
        template=EmailTemplate.TASK_ASSIGNMENT,
        recipient_email="user@example.com",
        subject="Subject",
        template_variables={},
        **kwargs,
    )
    message = service.smtp_service.send_message.call_args.args[0]
    return message["From"]


@pytest.mark.unit
class TestSendEmailFromHeader:
    def test_without_an_organization_the_configured_address_goes_out_bare(self):
        assert _sent_from(_smtp_service()) == "noreply@example.com"

    def test_an_organization_without_a_product_name_adds_no_name(self):
        organization = OrganizationBrand(primary_color="#6a1b9a")
        assert _sent_from(_smtp_service(), organization=organization) == "noreply@example.com"

    def test_the_product_name_goes_on_the_configured_address(self):
        assert _sent_from(_smtp_service(), organization=ACME) == (
            "Acme Evals <noreply@example.com>"
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("method", "kwargs"),
    [
        ("send_verification_email", {"verification_url": "https://app.example.com/v"}),
        ("send_password_reset_email", {"reset_url": "https://app.example.com/r"}),
        ("send_magic_link_email", {"magic_link_url": "https://app.example.com/m"}),
        (
            "send_team_invitation_email",
            {
                "organization_name": "Acme",
                "organization_website": None,
                "inviter_name": "Ada",
                "inviter_email": "ada@example.com",
                "frontend_url": "https://app.example.com",
            },
        ),
    ],
)
def test_account_emails_pass_the_organization_on(method, kwargs):
    service = _smtp_service()
    with patch.object(service, "send_email", return_value=True) as send_email:
        getattr(service, method)(
            recipient_email="user@example.com",
            recipient_name="User",
            organization=ACME,
            **kwargs,
        )

    assert send_email.call_args.kwargs["organization"] == ACME


@pytest.mark.unit
class TestWelcomeEmailSender:
    def _service(self):
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
        return service, mock_sg

    def _welcome_from(self, **kwargs) -> str:
        service, mock_sg = self._service()
        env = {
            "SENDGRID_API_KEY": "SG.test-key",
            "SENDGRID_DAY_1_EMAIL_TEMPLATE_ID": "d-day1-template",
            "WELCOME_FROM_EMAIL": '"Nicolai from Rhesis AI" <hello@example.com>',
        }
        with patch.dict("os.environ", env):
            service.send_day_1_email(
                recipient_email="user@example.com", recipient_name="User", **kwargs
            )
        return mock_sg.send_scheduled_dynamic_template.call_args.kwargs["from_email"]

    def test_without_an_organization_the_configured_sender_is_kept(self):
        assert self._welcome_from() == '"Nicolai from Rhesis AI" <hello@example.com>'

    def test_a_branded_organization_gets_its_own_name(self):
        assert parseaddr(self._welcome_from(organization=ACME)) == (
            "Acme Evals",
            "hello@example.com",
        )
