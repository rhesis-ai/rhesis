"""
URL Utility Tests

Tests for domain validation and redirect URL construction in url_utils.py.
Ensures that open redirect vulnerabilities are prevented and auth codes
are used instead of raw session tokens.
"""

import asyncio
from unittest.mock import Mock, patch

import pytest

from rhesis.backend.app.auth.url_utils import build_redirect_url
from rhesis.backend.app.config.settings import (
    get_application_settings,
    get_frontend_settings,
)


def _build(request, session_token, refresh_token=None):
    """Sync wrapper: build_redirect_url became async when auth codes moved
    to server-side (Redis) storage. Unit tests run without Redis, so code
    creation exercises the documented JWT fallback path."""
    return asyncio.run(build_redirect_url(request, session_token, refresh_token))


@pytest.fixture(autouse=True)
def clean_frontend_settings(monkeypatch):
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:3000")
    # Pin to production so the loopback dev gate is OFF by default; tests
    # that exercise the dev branch override BACKEND_ENV explicitly.
    monkeypatch.setenv("BACKEND_ENV", "production")
    get_frontend_settings.cache_clear()
    get_application_settings.cache_clear()
    yield
    get_frontend_settings.cache_clear()
    get_application_settings.cache_clear()


def _make_request(original_frontend=None, return_to="/architect"):
    """Create a mock Request with session data."""
    session = {}
    if original_frontend:
        session["original_frontend"] = original_frontend
    session["return_to"] = return_to

    request = Mock()
    request.session = session
    return request


@pytest.mark.unit
class TestDomainValidation:
    """Verify domain validation rejects substring/suffix matches."""

    @patch(
        "rhesis.backend.app.auth.token_utils.get_secret_key",
        return_value="test-secret",
    )
    def test_rejects_substring_match_localhost(self, _mock_key):
        """evil-localhost.com must NOT match 'localhost'."""
        request = _make_request(original_frontend="https://evil-localhost.com")
        url = _build(request, "token123")
        # Should fall back to FRONTEND_URL / default, not evil domain
        assert "evil-localhost.com" not in url

    @patch(
        "rhesis.backend.app.auth.token_utils.get_secret_key",
        return_value="test-secret",
    )
    def test_rejects_suffix_match_domain(self, _mock_key):
        """app.rhesis.ai.evil.com must NOT match 'app.rhesis.ai'."""
        request = _make_request(original_frontend="https://app.rhesis.ai.evil.com")
        url = _build(request, "token123")
        assert "evil.com" not in url

    @patch(
        "rhesis.backend.app.auth.token_utils.get_secret_key",
        return_value="test-secret",
    )
    def test_accepts_exact_localhost(self, _mock_key):
        """localhost:3000 should be accepted."""
        request = _make_request(original_frontend="http://localhost:3000")
        url = _build(request, "token123")
        assert url.startswith("http://localhost:3000/")

    @patch(
        "rhesis.backend.app.auth.token_utils.get_secret_key",
        return_value="test-secret",
    )
    def test_accepts_exact_configured_domain(self, _mock_key, monkeypatch):
        """The netloc derived from FRONTEND_URL should be accepted."""
        monkeypatch.setenv("FRONTEND_URL", "https://app.rhesis.ai")
        get_frontend_settings.cache_clear()

        request = _make_request(original_frontend="https://app.rhesis.ai")
        url = _build(request, "token123")
        assert url.startswith("https://app.rhesis.ai/")

    @patch(
        "rhesis.backend.app.auth.token_utils.get_secret_key",
        return_value="test-secret",
    )
    def test_custom_frontend_url_allows_one_deployment_domain(self, _mock_key, monkeypatch):
        """Custom FRONTEND_URL should define the single accepted redirect domain."""
        monkeypatch.setenv("FRONTEND_URL", "https://custom.example.com")
        get_frontend_settings.cache_clear()

        request = _make_request(original_frontend="https://custom.example.com")
        url = _build(request, "token123")
        assert url.startswith("https://custom.example.com/")

    @patch(
        "rhesis.backend.app.auth.token_utils.get_secret_key",
        return_value="test-secret",
    )
    def test_rejects_prefix_match_domain(self, _mock_key):
        """evil-app.rhesis.ai must NOT match 'app.rhesis.ai'."""
        request = _make_request(original_frontend="https://evil-app.rhesis.ai")
        url = _build(request, "token123")
        assert "evil-app" not in url


@pytest.mark.unit
class TestLoopbackDevGate:
    """Loopback origins are accepted only on development backends.

    Regression coverage for the local-dev-against-remote-API workflow:
    a frontend running on ``http://localhost:3000`` calling a remote
    dev backend (``FRONTEND_URL=https://dev-app.rhesis.ai``) must end
    up redirected back to localhost, while a production backend with
    the same incoming origin must not.
    """

    @patch(
        "rhesis.backend.app.auth.token_utils.get_secret_key",
        return_value="test-secret",
    )
    def test_rejects_loopback_in_production(self, _mock_key, monkeypatch):
        """BACKEND_ENV=production (autouse default in this file) rejects loopback."""
        monkeypatch.setenv("FRONTEND_URL", "https://app.rhesis.ai")
        get_frontend_settings.cache_clear()
        get_application_settings.cache_clear()

        request = _make_request(original_frontend="http://localhost:3000")
        url = _build(request, "token123")

        assert url.startswith("https://app.rhesis.ai/")
        assert "localhost" not in url

    @patch(
        "rhesis.backend.app.auth.token_utils.get_secret_key",
        return_value="test-secret",
    )
    def test_accepts_loopback_when_only_environment_is_production(self, _mock_key, monkeypatch):
        """ENVIRONMENT=production alone no longer gates loopback; only BACKEND_ENV drives it."""
        monkeypatch.setenv("FRONTEND_URL", "https://app.rhesis.ai")
        monkeypatch.setenv("BACKEND_ENV", "development")
        get_frontend_settings.cache_clear()
        get_application_settings.cache_clear()

        request = _make_request(original_frontend="http://localhost:3000")
        url = _build(request, "token123")

        assert url.startswith("http://localhost:3000/")

    @patch(
        "rhesis.backend.app.auth.token_utils.get_secret_key",
        return_value="test-secret",
    )
    def test_accepts_loopback_when_backend_env_is_development(self, _mock_key, monkeypatch):
        """Localhost frontend against a remote dev backend redirects home.

        This is the exact regression scenario: developing the frontend
        on localhost while pointing the API at dev-api.rhesis.ai (whose
        FRONTEND_URL is dev-app.rhesis.ai) should still bring the user
        back to localhost after OAuth.
        """
        monkeypatch.setenv("FRONTEND_URL", "https://dev-app.rhesis.ai")
        monkeypatch.setenv("BACKEND_ENV", "development")
        get_frontend_settings.cache_clear()
        get_application_settings.cache_clear()

        request = _make_request(original_frontend="http://localhost:3000")
        url = _build(request, "token123")

        assert url.startswith("http://localhost:3000/")

    @patch(
        "rhesis.backend.app.auth.token_utils.get_secret_key",
        return_value="test-secret",
    )
    def test_accepts_loopback_when_backend_env_is_local(self, _mock_key, monkeypatch):
        """BACKEND_ENV=local (Quick Start) is treated as non-production."""
        monkeypatch.setenv("FRONTEND_URL", "https://dev-app.rhesis.ai")
        monkeypatch.setenv("BACKEND_ENV", "local")
        get_frontend_settings.cache_clear()
        get_application_settings.cache_clear()

        request = _make_request(original_frontend="http://localhost:3000")
        url = _build(request, "token123")

        assert url.startswith("http://localhost:3000/")

    @patch(
        "rhesis.backend.app.auth.token_utils.get_secret_key",
        return_value="test-secret",
    )
    def test_accepts_127_in_development(self, _mock_key, monkeypatch):
        """127.0.0.1 with an arbitrary port is accepted in development."""
        monkeypatch.setenv("FRONTEND_URL", "https://dev-app.rhesis.ai")
        monkeypatch.setenv("BACKEND_ENV", "development")
        get_frontend_settings.cache_clear()
        get_application_settings.cache_clear()

        request = _make_request(original_frontend="http://127.0.0.1:5173")
        url = _build(request, "token123")

        assert url.startswith("http://127.0.0.1:5173/")

    @patch(
        "rhesis.backend.app.auth.token_utils.get_secret_key",
        return_value="test-secret",
    )
    def test_dev_mode_does_not_relax_lookalike_check(self, _mock_key, monkeypatch):
        """Even in development, ``evil-localhost.com`` is rejected.

        Dev mode opens an exact-match loopback whitelist; it must never
        accept substring lookalikes that would also be open redirects.
        """
        monkeypatch.setenv("FRONTEND_URL", "https://dev-app.rhesis.ai")
        monkeypatch.setenv("BACKEND_ENV", "development")
        get_frontend_settings.cache_clear()
        get_application_settings.cache_clear()

        request = _make_request(original_frontend="https://evil-localhost.com")
        url = _build(request, "token123")

        assert url.startswith("https://dev-app.rhesis.ai/")
        assert "evil-localhost.com" not in url

    @patch(
        "rhesis.backend.app.auth.token_utils.get_secret_key",
        return_value="test-secret",
    )
    def test_dev_mode_rejects_localhost_subdomain_attack(self, _mock_key, monkeypatch):
        """``localhost.attacker.com`` must not be treated as loopback."""
        monkeypatch.setenv("FRONTEND_URL", "https://dev-app.rhesis.ai")
        monkeypatch.setenv("BACKEND_ENV", "development")
        get_frontend_settings.cache_clear()
        get_application_settings.cache_clear()

        request = _make_request(original_frontend="https://localhost.attacker.com")
        url = _build(request, "token123")

        assert url.startswith("https://dev-app.rhesis.ai/")
        assert "attacker.com" not in url


@pytest.mark.unit
class TestRedirectUrlAuthCode:
    """Verify redirect URL uses auth code, not raw session token."""

    @patch(
        "rhesis.backend.app.auth.token_utils.get_secret_key",
        return_value="test-secret",
    )
    def test_url_contains_code_not_session_token(self, _mock_key):
        """Redirect URL should contain ?code=... not ?session_token=..."""
        request = _make_request()
        url = _build(request, "long-lived-session-token")
        assert "session_token=" not in url
        assert "code=" in url

    @patch(
        "rhesis.backend.app.auth.token_utils.get_secret_key",
        return_value="test-secret",
    )
    def test_url_points_to_signin_page(self, _mock_key):
        """Redirect URL should point to /auth/signin."""
        request = _make_request()
        url = _build(request, "token123")
        assert "/auth/signin" in url

    @patch(
        "rhesis.backend.app.auth.token_utils.get_secret_key",
        return_value="test-secret",
    )
    def test_return_to_preserved(self, _mock_key):
        """return_to parameter should be preserved in redirect URL."""
        request = _make_request(return_to="/settings")
        url = _build(request, "token123")
        assert "return_to=/settings" in url
