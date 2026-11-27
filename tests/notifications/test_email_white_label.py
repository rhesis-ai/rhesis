"""Email to a white-labelled organization carries its brand, not Rhesis's.

Renders every template a member can receive under an organization's branding and
checks what changes, and that the default render is untouched. Pure unit tests:
Jinja only, nothing is sent.
"""

from unittest.mock import patch

import pytest

from rhesis.backend.notifications.email.brand import (
    LOGO_CONTENT_ID,
    OrganizationBrand,
    get_brand,
)
from rhesis.backend.notifications.email.service import EmailService
from rhesis.backend.notifications.email.template_service import EmailTemplate, TemplateService
from tests.notifications.email_fixtures import FIXTURES

# Sent to the Rhesis team, not to an organization's members.
INTERNAL = {EmailTemplate.FEEDBACK, EmailTemplate.POLYPHEMUS_ACCESS_REQUEST}
MEMBER_TEMPLATES = [t for t in FIXTURES if t not in INTERNAL]

ACME = OrganizationBrand(
    product_name="Acme Evals",
    primary_color="#6A1B9A",
    secondary_color="#FFD600",
    logo_png=b"\x89PNG fake",
)


def _render(template: EmailTemplate, organization=None) -> str:
    brand = get_brand(organization) if organization else None
    return TemplateService().render_template(template, dict(FIXTURES[template]), brand=brand)


@pytest.mark.unit
@pytest.mark.parametrize("template", MEMBER_TEMPLATES, ids=lambda t: t.name)
class TestWhiteLabelledTemplates:
    def test_rhesis_appears_only_in_the_imprint(self, template):
        html = _render(template, ACME)
        assert "Acme Evals" in html
        assert html.replace("Rhesis AI GmbH", "").count("Rhesis AI") == 0

    def test_the_header_shows_the_favicon_and_name_instead_of_the_lockup(self, template):
        html = _render(template, ACME)
        assert f"cid:{LOGO_CONTENT_ID}" in html
        assert "logo-lockup" not in html
        assert "header-gradient" not in html

    def test_the_organization_colours_replace_the_accent(self, template):
        html = _render(template, ACME).lower()
        assert "#0080af" not in html

    def test_without_a_favicon_the_name_stands_alone(self, template):
        html = _render(template, OrganizationBrand(product_name="Acme Evals"))
        assert "cid:" not in html
        assert "Acme Evals" in html

    def test_colours_alone_keep_the_rhesis_header(self, template):
        html = _render(template, OrganizationBrand(primary_color="#6A1B9A"))
        assert "logo-lockup" in html
        assert "#6a1b9a" in html.lower()


@pytest.mark.unit
@pytest.mark.parametrize("template", list(FIXTURES), ids=lambda t: t.name)
def test_the_default_render_is_unchanged_by_an_explicit_rhesis_brand(template):
    assert _render(template, OrganizationBrand()) == _render(template)


@pytest.mark.unit
def test_the_invitation_leaves_out_about_rhesis():
    assert "About Rhesis AI" in _render(EmailTemplate.TEAM_INVITATION)
    assert "About Rhesis AI" not in _render(EmailTemplate.TEAM_INVITATION, ACME)


@pytest.mark.unit
def test_button_text_stays_readable_on_a_light_button():
    assert get_brand(OrganizationBrand(secondary_color="#FFD600")).color.inverse == "#101011"
    assert get_brand(OrganizationBrand(secondary_color="#1A237E")).color.inverse == "#ffffff"


def _sent_message(organization):
    with (
        patch("rhesis.backend.notifications.email.service.SendGridClient"),
        patch("rhesis.backend.notifications.email.service.SMTPService"),
    ):
        service = EmailService()
    service.smtp_service.is_configured = True
    service.smtp_service.from_email = "noreply@example.com"
    service.send_verification_email(
        recipient_email="user@example.com",
        recipient_name="User",
        verification_url="https://app.example.com/v",
        organization=organization,
    )
    return service.smtp_service.send_message.call_args.args[0]


@pytest.mark.unit
def test_the_favicon_is_attached_inline():
    message = _sent_message(ACME)
    assert message["Subject"] == "Verify your email - Acme Evals"
    parts = message.get_payload()
    assert [p.get_content_type() for p in parts] == ["text/html", "image/png"]
    assert parts[1]["Content-ID"] == f"<{LOGO_CONTENT_ID}>"
    assert parts[1].get_payload(decode=True) == ACME.logo_png


@pytest.mark.unit
def test_without_branding_the_message_is_plain_html():
    message = _sent_message(None)
    assert message["Subject"] == "Verify your email - Rhesis AI"
    assert message.get_content_type() == "text/html"
