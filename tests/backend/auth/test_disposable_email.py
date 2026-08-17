"""
Unit tests for disposable email domain screening.

Covers registrable-domain matching, IDN/punycode normalisation, the custom
in-repo list, the env override, and the three-state mode setting.
"""

import pytest

from rhesis.backend.app.auth.disposable_email import (
    DisposableEmailError,
    get_blocklist,
    match_domain,
    screen_signup_email,
)
from rhesis.backend.app.config.settings import get_auth_settings

# A real entry from the upstream community list, used to prove the package is wired in.
UPSTREAM_DOMAIN = "mailinator.com"


@pytest.fixture(autouse=True)
def _reset_caches():
    """Both caches read env at first call, so clear them around every test."""
    get_auth_settings.cache_clear()
    get_blocklist.cache_clear()
    yield
    get_auth_settings.cache_clear()
    get_blocklist.cache_clear()


@pytest.fixture
def enforce(monkeypatch):
    monkeypatch.setenv("AUTH_BLOCK_DISPOSABLE_EMAILS", "enforce")


class TestDomainMatching:
    """match_domain() — the registrable-domain and IDN rules."""

    @pytest.mark.unit
    def test_upstream_list_is_loaded(self):
        assert UPSTREAM_DOMAIN in get_blocklist()
        assert len(get_blocklist()) > 1000

    @pytest.mark.unit
    def test_exact_domain_matches(self):
        assert match_domain(UPSTREAM_DOMAIN) == UPSTREAM_DOMAIN

    @pytest.mark.unit
    def test_subdomain_matches_registrable_domain(self):
        assert match_domain(f"mail.smtp.{UPSTREAM_DOMAIN}") == UPSTREAM_DOMAIN

    @pytest.mark.unit
    def test_matching_is_case_insensitive(self):
        assert match_domain(UPSTREAM_DOMAIN.upper()) == UPSTREAM_DOMAIN

    @pytest.mark.unit
    def test_legitimate_domain_does_not_match(self):
        assert match_domain("rhesis.ai") is None
        assert match_domain("gmail.com") is None

    @pytest.mark.unit
    def test_suffix_of_a_label_does_not_match(self, monkeypatch):
        """Stripping happens at label boundaries: `nottrash.example` is not `trash.example`."""
        monkeypatch.setenv("AUTH_DISPOSABLE_EMAIL_EXTRA_DOMAINS", "trash.example")
        get_auth_settings.cache_clear()
        get_blocklist.cache_clear()
        assert match_domain("nottrash.example") is None

    @pytest.mark.unit
    def test_bare_tld_is_never_matched(self, monkeypatch):
        """A bare TLD slipping into the list must not block every address under it."""
        monkeypatch.setenv("AUTH_DISPOSABLE_EMAIL_EXTRA_DOMAINS", "com")
        get_auth_settings.cache_clear()
        get_blocklist.cache_clear()
        assert match_domain("rhesis.com") is None


class TestEnvOverride:
    """AUTH_DISPOSABLE_EMAIL_EXTRA_DOMAINS."""

    @pytest.mark.unit
    def test_env_domain_is_blocked(self, monkeypatch):
        monkeypatch.setenv("AUTH_DISPOSABLE_EMAIL_EXTRA_DOMAINS", "trash.example")
        get_auth_settings.cache_clear()
        get_blocklist.cache_clear()
        assert match_domain("trash.example") == "trash.example"

    @pytest.mark.unit
    def test_env_list_is_comma_separated_and_trimmed(self, monkeypatch):
        monkeypatch.setenv(
            "AUTH_DISPOSABLE_EMAIL_EXTRA_DOMAINS", " a.example , B.EXAMPLE ,, c.example "
        )
        get_auth_settings.cache_clear()
        get_blocklist.cache_clear()
        for domain in ("a.example", "b.example", "c.example"):
            assert match_domain(domain) == domain

    @pytest.mark.unit
    def test_env_domain_matches_subdomains_too(self, monkeypatch):
        monkeypatch.setenv("AUTH_DISPOSABLE_EMAIL_EXTRA_DOMAINS", "trash.example")
        get_auth_settings.cache_clear()
        get_blocklist.cache_clear()
        assert match_domain("mx1.trash.example") == "trash.example"


class TestIdnNormalisation:
    """Unicode domains must be compared in punycode form."""

    @pytest.mark.unit
    def test_unicode_email_matches_punycode_entry(self, monkeypatch, enforce):
        # xn--mnchen-3ya.de is the punycode form of münchen.de
        monkeypatch.setenv("AUTH_DISPOSABLE_EMAIL_EXTRA_DOMAINS", "xn--mnchen-3ya.de")
        get_auth_settings.cache_clear()
        get_blocklist.cache_clear()

        with pytest.raises(DisposableEmailError):
            screen_signup_email("user@münchen.de", source="test")

    @pytest.mark.unit
    def test_unicode_subdomain_of_punycode_entry_matches(self, monkeypatch, enforce):
        monkeypatch.setenv("AUTH_DISPOSABLE_EMAIL_EXTRA_DOMAINS", "xn--mnchen-3ya.de")
        get_auth_settings.cache_clear()
        get_blocklist.cache_clear()

        with pytest.raises(DisposableEmailError):
            screen_signup_email("user@mail.münchen.de", source="test")


class TestModes:
    """AUTH_BLOCK_DISPOSABLE_EMAILS: off / log / enforce."""

    @pytest.mark.unit
    def test_default_mode_is_log(self):
        assert get_auth_settings().block_disposable_emails == "log"

    @pytest.mark.unit
    def test_log_mode_does_not_raise(self, monkeypatch):
        monkeypatch.setenv("AUTH_BLOCK_DISPOSABLE_EMAILS", "log")
        get_auth_settings.cache_clear()

        screen_signup_email(f"user@{UPSTREAM_DOMAIN}", source="test")

    @pytest.mark.unit
    def test_log_mode_records_the_match(self, monkeypatch, caplog):
        monkeypatch.setenv("AUTH_BLOCK_DISPOSABLE_EMAILS", "log")
        get_auth_settings.cache_clear()

        with caplog.at_level("WARNING"):
            screen_signup_email(f"user@{UPSTREAM_DOMAIN}", source="magic_link")

        assert UPSTREAM_DOMAIN in caplog.text
        assert "magic_link" in caplog.text
        # The local part must not reach the logs unredacted.
        assert "user@" not in caplog.text

    @pytest.mark.unit
    def test_enforce_mode_raises(self, enforce):
        with pytest.raises(DisposableEmailError):
            screen_signup_email(f"user@{UPSTREAM_DOMAIN}", source="test")

    @pytest.mark.unit
    def test_off_mode_skips_the_check(self, monkeypatch):
        monkeypatch.setenv("AUTH_BLOCK_DISPOSABLE_EMAILS", "off")
        get_auth_settings.cache_clear()

        screen_signup_email(f"user@{UPSTREAM_DOMAIN}", source="test")

    @pytest.mark.unit
    @pytest.mark.parametrize("value", ["false", "False", "0", "no"])
    def test_legacy_boolean_false_disables_the_check(self, monkeypatch, value):
        """The setting shipped as a bool in the original issue; keep those values working."""
        monkeypatch.setenv("AUTH_BLOCK_DISPOSABLE_EMAILS", value)
        get_auth_settings.cache_clear()

        assert get_auth_settings().block_disposable_emails == "off"
        screen_signup_email(f"user@{UPSTREAM_DOMAIN}", source="test")

    @pytest.mark.unit
    @pytest.mark.parametrize("value", ["true", "True", "1", "yes"])
    def test_legacy_boolean_true_enforces(self, monkeypatch, value):
        monkeypatch.setenv("AUTH_BLOCK_DISPOSABLE_EMAILS", value)
        get_auth_settings.cache_clear()

        assert get_auth_settings().block_disposable_emails == "enforce"
        with pytest.raises(DisposableEmailError):
            screen_signup_email(f"user@{UPSTREAM_DOMAIN}", source="test")


class TestScreening:
    """screen_signup_email() behaviour outside the mode matrix."""

    @pytest.mark.unit
    def test_legitimate_address_passes(self, enforce):
        screen_signup_email("nicolai@rhesis.ai", source="test")

    @pytest.mark.unit
    def test_unparseable_address_is_left_to_the_email_validator(self, enforce):
        """Not this function's job to reject bad syntax — it just declines to match."""
        screen_signup_email("not-an-email", source="test")

    @pytest.mark.unit
    def test_error_is_a_valueerror(self, enforce):
        """Call sites that already map ValueError to a 400 need no change."""
        with pytest.raises(ValueError):
            screen_signup_email(f"user@{UPSTREAM_DOMAIN}", source="test")


class TestCustomList:
    """The in-repo supplement file."""

    @pytest.mark.unit
    def test_custom_file_entries_are_merged(self, monkeypatch, tmp_path):
        custom = tmp_path / "custom.txt"
        custom.write_text(
            "# a comment\n\n  Repo-Blocked.example  \ntrailing.example # inline comment\n",
            encoding="utf-8",
        )
        monkeypatch.setattr("rhesis.backend.app.auth.disposable_email.CUSTOM_DOMAINS_FILE", custom)
        get_blocklist.cache_clear()

        assert match_domain("repo-blocked.example") == "repo-blocked.example"
        assert match_domain("trailing.example") == "trailing.example"
        # Upstream entries survive the merge.
        assert match_domain(UPSTREAM_DOMAIN) == UPSTREAM_DOMAIN

    @pytest.mark.unit
    def test_missing_custom_file_is_not_an_error(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "rhesis.backend.app.auth.disposable_email.CUSTOM_DOMAINS_FILE",
            tmp_path / "does-not-exist.txt",
        )
        get_blocklist.cache_clear()

        assert match_domain(UPSTREAM_DOMAIN) == UPSTREAM_DOMAIN
