"""Tests to verify that sensitive information is not logged."""

from rhesis.backend.app.services.invokers.common.headers import HeaderManager


class TestHeaderSanitization:
    """Test that sensitive headers are properly redacted."""

    def test_sanitize_authorization_header(self):
        """Authorization header should be redacted."""
        headers = {"Authorization": "Bearer rh-secret-api-key-12345"}
        sanitized = HeaderManager.sanitize_headers(headers)
        assert sanitized["Authorization"] == "***REDACTED***"

    def test_sanitize_api_key_header(self):
        """API key headers should be redacted."""
        headers = {
            "X-API-Key": "secret-key-abc",
            "api-key": "another-secret",
        }
        sanitized = HeaderManager.sanitize_headers(headers)
        assert sanitized["X-API-Key"] == "***REDACTED***"
        assert sanitized["api-key"] == "***REDACTED***"

    def test_sanitize_auth_token_header(self):
        """Auth token headers should be redacted."""
        headers = {"X-Auth-Token": "token-xyz-789"}
        sanitized = HeaderManager.sanitize_headers(headers)
        assert sanitized["X-Auth-Token"] == "***REDACTED***"

    def test_sanitize_bearer_header(self):
        """Bearer token headers should be redacted."""
        headers = {"Bearer": "jwt-token-here"}
        sanitized = HeaderManager.sanitize_headers(headers)
        assert sanitized["Bearer"] == "***REDACTED***"

    def test_sanitize_multiple_sensitive_headers(self):
        """Multiple sensitive headers should all be redacted."""
        headers = {
            "Authorization": "Bearer secret-123",
            "X-API-Key": "api-key-456",
            "X-Auth-Token": "token-789",
            "Cookie": "session=abc123",
        }
        sanitized = HeaderManager.sanitize_headers(headers)
        assert sanitized["Authorization"] == "***REDACTED***"
        assert sanitized["X-API-Key"] == "***REDACTED***"
        assert sanitized["X-Auth-Token"] == "***REDACTED***"
        assert sanitized["Cookie"] == "***REDACTED***"

    def test_preserve_non_sensitive_headers(self):
        """Non-sensitive headers should be preserved."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "MyApp/1.0",
            "X-Request-ID": "req-123",
        }
        sanitized = HeaderManager.sanitize_headers(headers)
        assert sanitized["Content-Type"] == "application/json"
        assert sanitized["Accept"] == "application/json"
        assert sanitized["User-Agent"] == "MyApp/1.0"
        assert sanitized["X-Request-ID"] == "req-123"

    def test_mixed_sensitive_and_non_sensitive_headers(self):
        """Mixed headers should have only sensitive ones redacted."""
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer secret-token",
            "User-Agent": "MyApp/1.0",
            "X-API-Key": "api-key-secret",
        }
        sanitized = HeaderManager.sanitize_headers(headers)
        assert sanitized["Content-Type"] == "application/json"
        assert sanitized["Authorization"] == "***REDACTED***"
        assert sanitized["User-Agent"] == "MyApp/1.0"
        assert sanitized["X-API-Key"] == "***REDACTED***"

    def test_case_insensitive_matching(self):
        """Sensitive header detection should be case-insensitive."""
        headers = {
            "authorization": "Bearer token-lower",
            "AUTHORIZATION": "Bearer token-upper",
            "Authorization": "Bearer token-mixed",
            "AuThOrIzAtIoN": "Bearer token-crazy",
        }
        sanitized = HeaderManager.sanitize_headers(headers)
        assert all(v == "***REDACTED***" for v in sanitized.values())

    def test_empty_headers(self):
        """Empty headers dict should return empty dict."""
        sanitized = HeaderManager.sanitize_headers({})
        assert sanitized == {}

    def test_none_headers(self):
        """None headers should return empty dict."""
        sanitized = HeaderManager.sanitize_headers(None)
        assert sanitized == {}

    def test_headers_with_secret_in_name(self):
        """Headers with 'secret' in name should be redacted."""
        headers = {
            "X-Secret-Key": "my-secret-value",
            "Secret-Token": "another-secret",
        }
        sanitized = HeaderManager.sanitize_headers(headers)
        assert sanitized["X-Secret-Key"] == "***REDACTED***"
        assert sanitized["Secret-Token"] == "***REDACTED***"

    def test_headers_with_password_in_name(self):
        """Headers with 'password' in name should be redacted."""
        headers = {
            "X-Password": "my-password-123",
            "Password-Hash": "hashed-value",
        }
        sanitized = HeaderManager.sanitize_headers(headers)
        assert sanitized["X-Password"] == "***REDACTED***"
        assert sanitized["Password-Hash"] == "***REDACTED***"

    def test_partial_matching(self):
        """Headers containing sensitive keywords should be redacted."""
        headers = {
            "X-Custom-Authorization-Header": "Bearer token",
            "MyApp-API-KEY-Field": "secret-key",
            "X-Bearer-Token": "jwt-here",
        }
        sanitized = HeaderManager.sanitize_headers(headers)
        # All should be redacted because they contain sensitive keywords
        assert sanitized["X-Custom-Authorization-Header"] == "***REDACTED***"
        assert sanitized["MyApp-API-KEY-Field"] == "***REDACTED***"
        assert sanitized["X-Bearer-Token"] == "***REDACTED***"

    def test_rhesis_api_key_format(self):
        """Rhesis API keys (rh- prefix) should be redacted."""
        headers = {"Authorization": "Bearer rh-prod-abc123def456"}
        sanitized = HeaderManager.sanitize_headers(headers)
        assert sanitized["Authorization"] == "***REDACTED***"
        assert "rh-prod-abc123def456" not in str(sanitized)

    def test_jwt_token_redaction(self):
        """JWT tokens should be redacted."""
        jwt_token = (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJzdWIiOiIxMjM0NTY3ODkwIn0."
            "dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        )
        headers = {"Authorization": f"Bearer {jwt_token}"}
        sanitized = HeaderManager.sanitize_headers(headers)
        assert sanitized["Authorization"] == "***REDACTED***"
        assert "eyJhbGci" not in str(sanitized)

    def test_all_sensitive_keywords_covered(self):
        """Test that all sensitive keywords from SENSITIVE_KEYS are checked."""
        sensitive_keywords = [
            "authorization",
            "auth",
            "x-api-key",
            "api-key",
            "x-auth-token",
            "bearer",
            "token",
            "secret",
            "password",
            "x-access-token",
            "cookie",
        ]

        for keyword in sensitive_keywords:
            headers = {keyword.upper(): "sensitive-value"}
            sanitized = HeaderManager.sanitize_headers(headers)
            assert sanitized[keyword.upper()] == "***REDACTED***", (
                f"Keyword '{keyword}' was not properly redacted"
            )
