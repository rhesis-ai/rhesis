"""The email imprint is the deployment's EMAIL_IMPRINT, and its absence is reported.

Pure unit tests: Jinja only, nothing is sent.
"""

import logging
from pathlib import Path

import pytest
import yaml

from rhesis.backend.app.config.settings import get_smtp_settings
from rhesis.backend.notifications.email import brand as brand_module
from rhesis.backend.notifications.email.brand import ImprintLine, imprint_lines
from rhesis.backend.notifications.email.template_service import EmailTemplate, TemplateService
from tests.notifications.email_fixtures import FIXTURES, HOSTED_IMPRINT

CHARTS = Path(__file__).resolve().parents[2] / "charts" / "rhesis"


@pytest.fixture
def smtp_env(monkeypatch):
    """Set SMTP environment variables for one test, with a fresh settings cache."""

    def _set(**values: str) -> None:
        for name in ("SMTP_HOST", "EMAIL_IMPRINT"):
            monkeypatch.delenv(name, raising=False)
        for name, value in values.items():
            monkeypatch.setenv(name, value)
        get_smtp_settings.cache_clear()

    yield _set
    get_smtp_settings.cache_clear()


def _render(template: EmailTemplate = EmailTemplate.PASSWORD_RESET) -> str:
    return TemplateService().render_template(template, dict(FIXTURES[template]))


@pytest.mark.unit
class TestImprintLines:
    def test_lines_are_split_and_blank_ones_dropped(self):
        assert imprint_lines("Acme GmbH\n\n  Main St. 1  \n") == (
            ImprintLine("Acme GmbH"),
            ImprintLine("Main St. 1"),
        )

    def test_an_email_address_is_picked_out(self):
        assert imprint_lines("E-Mail: legal@acme.example (legal only)") == (
            ImprintLine("E-Mail: ", "legal@acme.example", " (legal only)"),
        )

    def test_a_literal_backslash_n_is_a_line_break(self):
        assert imprint_lines(r"Acme GmbH\nMain St. 1") == (
            ImprintLine("Acme GmbH"),
            ImprintLine("Main St. 1"),
        )

    def test_unset_is_empty(self):
        assert imprint_lines(None) == ()
        assert imprint_lines("  \n ") == ()


@pytest.mark.unit
class TestRenderedImprint:
    def test_unset_shows_a_notice_in_its_place(self, smtp_env):
        smtp_env()
        html = _render()
        assert "Rhesis AI GmbH" not in html
        assert "No imprint configured" in html
        assert "set EMAIL_IMPRINT" in html

    def test_the_operators_details_are_shown(self, smtp_env):
        smtp_env(EMAIL_IMPRINT="Acme GmbH\nMain St. 1\nE-Mail: legal@acme.example")
        html = _render()
        assert '<span style="font-weight: 700; color: #101011;">Acme GmbH</span>' in html
        assert "Main St. 1" in html
        assert 'href="mailto:legal@acme.example"' in html
        assert "Rhesis AI GmbH" not in html
        assert "No imprint configured" not in html

    def test_imprint_text_is_escaped(self, smtp_env):
        smtp_env(EMAIL_IMPRINT='Acme <script>alert("x")</script> GmbH')
        assert "<script>alert" not in _render()


@pytest.mark.unit
@pytest.mark.parametrize("env", ["dev", "stg", "prd"])
def test_hosted_environments_send_the_rhesis_imprint(env):
    values = yaml.safe_load((CHARTS / f"values-{env}.yaml").read_text())
    assert values["config"]["emailImprint"] == HOSTED_IMPRINT


@pytest.mark.unit
def test_the_chart_default_has_no_imprint():
    values = yaml.safe_load((CHARTS / "values.yaml").read_text())
    assert values["config"]["emailImprint"] == ""


@pytest.mark.unit
class TestMissingImprintWarning:
    @pytest.fixture(autouse=True)
    def _fresh_check(self, monkeypatch):
        monkeypatch.setattr(brand_module, "_imprint_checked", False)

    def test_warns_when_mail_is_configured_without_one(self, smtp_env, caplog):
        smtp_env(SMTP_HOST="smtp.example.com")
        with caplog.at_level(logging.WARNING, logger=brand_module.__name__):
            brand_module.warn_if_imprint_missing()
        assert "EMAIL_IMPRINT is unset" in caplog.text

    def test_quiet_with_an_imprint(self, smtp_env, caplog):
        smtp_env(SMTP_HOST="smtp.example.com", EMAIL_IMPRINT="Acme GmbH")
        with caplog.at_level(logging.WARNING, logger=brand_module.__name__):
            brand_module.warn_if_imprint_missing()
        assert "EMAIL_IMPRINT" not in caplog.text

    def test_quiet_when_no_mail_is_sent(self, smtp_env, caplog):
        smtp_env()
        with caplog.at_level(logging.WARNING, logger=brand_module.__name__):
            brand_module.warn_if_imprint_missing()
        assert "EMAIL_IMPRINT" not in caplog.text
