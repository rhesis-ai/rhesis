"""
URL Utility Tests

Tests for domain validation and redirect URL construction in url_utils.py.
Ensures that open redirect vulnerabilities are prevented and auth codes
are used instead of raw session tokens.
"""

from unittest.mock import Mock, patch

import pytest

from rhesis.backend.app.auth.url_utils import build_redirect_url


def _make_request(original_frontend=None, return_to="/dashboard"):
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
        url = build_redirect_url(request, "token123")
        # Should fall back to FRONTEND_URL / default, not evil domain
        assert "evil-localhost.com" not in url

    @patch(
        "rhesis.backend.app.auth.token_utils.get_secret_key",
        return_value="test-secret",
    )
    def test_rejects_suffix_match_domain(self, _mock_key):
        """app.rhesis.ai.evil.com must NOT match 'app.rhesis.ai'."""
        request = _make_request(original_frontend="https://app.rhesis.ai.evil.com")
        url = build_redirect_url(request, "token123")
        assert "evil.com" not in url

    @patch(
        "rhesis.backend.app.auth.token_utils.get_secret_key",
        return_value="test-secret",
    )
    def test_accepts_exact_localhost(self, _mock_key):
        """localhost:3000 should be accepted."""
        request = _make_request(original_frontend="http://localhost:3000")
        url = build_redirect_url(request, "token123")
        assert url.startswith("http://localhost:3000/")

    @patch(
        "rhesis.backend.app.auth.token_utils.get_secret_key",
        return_value="test-secret",
    )
    def test_accepts_exact_allowed_domain(self, _mock_key):
        """app.rhesis.ai should be accepted."""
        request = _make_request(original_frontend="https://app.rhesis.ai")
        url = build_redirect_url(request, "token123")
        assert url.startswith("https://app.rhesis.ai/")

    @patch(
        "rhesis.backend.app.auth.token_utils.get_secret_key",
        return_value="test-secret",
    )
    def test_rejects_prefix_match_domain(self, _mock_key):
        """evil-app.rhesis.ai must NOT match 'app.rhesis.ai'."""
        request = _make_request(original_frontend="https://evil-app.rhesis.ai")
        url = build_redirect_url(request, "token123")
        assert "evil-app" not in url


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
        url = build_redirect_url(request, "long-lived-session-token")
        assert "session_token=" not in url
        assert "code=" in url

    @patch(
        "rhesis.backend.app.auth.token_utils.get_secret_key",
        return_value="test-secret",
    )
    def test_url_points_to_signin_page(self, _mock_key):
        """Redirect URL should point to /auth/signin."""
        request = _make_request()
        url = build_redirect_url(request, "token123")
        assert "/auth/signin" in url

    @patch(
        "rhesis.backend.app.auth.token_utils.get_secret_key",
        return_value="test-secret",
    )
    def test_return_to_preserved(self, _mock_key):
        """return_to parameter should be preserved in redirect URL."""
        request = _make_request(return_to="/settings")
        url = build_redirect_url(request, "token123")
        assert "return_to=/settings" in url
