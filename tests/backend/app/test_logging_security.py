"""Tests to verify that sensitive information is not logged."""

import io
import json
import logging

import pytest

from rhesis.backend.app.services.invokers.common.headers import HeaderManager
from rhesis.backend.logging.logging_config import (
    JsonLogFormatter,
    RedactingFormatter,
    _redact,
    _WorkerContextFilter,
)


# Assembled at runtime so secret scanners -- GitHub push protection and the
# trufflehog CI job -- do not read these fixtures as live credentials.
_FAKE_SLACK_TOKEN = "xoxb-" + "1234567890-" + "abcdefghijklmno"
_FAKE_PW = "p4ss" + "w0rd"


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


class TestLogLineRedaction:
    """Credentials that reach a log *message* rather than a header.

    Upstream services describe their own auth failures in prose, and that text
    comes back to us verbatim -- through an endpoint test, an invoker error, a
    traceback. The formatter is the last place to catch it.
    """

    @pytest.mark.parametrize(
        "line,secret",
        [
            # Space-separated, as an upstream error body actually phrases it.
            ('{"error":"invalid api key: sk-live-9f8e7d6c"}', "sk-live-9f8e7d6c"),
            ("upstream said: client secret = abc123def", "abc123def"),
            ("aws secret access key: AbC123xyz", "AbC123xyz"),
            ("session token: tok-abc-123", "tok-abc-123"),
            ("refresh token = 0123456789abcdef", "0123456789abcdef"),
            # The pre-existing separators must keep working.
            ("api_key: sk-underscore-style", "sk-underscore-style"),
            ("api-key=sk-dash-style", "sk-dash-style"),
        ],
    )
    def test_secret_in_message_is_redacted(self, line, secret):
        redacted = _redact(line)
        assert secret not in redacted
        assert "[REDACTED]" in redacted

    @pytest.mark.parametrize(
        "line",
        [
            "the api key was missing from the request",
            "No api keys configured for this project",
            "client secret rotation is due",
            # A separator is present, but the value is prose rather than a key.
            "api key: not configured",
            "api key = missing for organization 42",
            "API key: none",
            "client secret: unset",
            "session token: expired at 2026-01-01",
            "access token: null",
            "refresh token = invalid",
            "password: empty",
            "password: rotated",
            "api key: not_configured",
            "Bearer token is missing",
        ],
    )
    def test_prose_without_a_value_is_left_alone(self, line):
        """Over-redaction hides the diagnosis, so a bare mention must survive."""
        assert _redact(line) == line

    @pytest.mark.parametrize(
        "line,secret",
        [
            # No keyword touches the value here -- only the key's own shape does.
            (
                "Incorrect API key provided: sk-proj-aBcD1234EfGh5678",
                "sk-proj-aBcD1234EfGh5678",
            ),
            (
                "anthropic api-key sk-ant-api03-XYZabc123DEFghi456jkl",
                "sk-ant-api03-XYZabc123DEFghi456jkl",
            ),
            (
                "fatal: token ghp_abcdefghij1234567890ABCDEFGHIJ rejected",
                "ghp_abcdefghij1234567890ABCDEFGHIJ",
            ),
            (
                "github_pat_11ABCDEFG0abcdefghij_klmnop",
                "github_pat_11ABCDEFG0abcdefghij_klmnop",
            ),
            (f"slack said {_FAKE_SLACK_TOKEN}", _FAKE_SLACK_TOKEN),
            (
                "AIzaSyABCDEFGHIJKLMNOPQRSTUVWXYZ0123456 is not valid",
                "AIzaSyABCDEFGHIJKLMNOPQRSTUVWXYZ0123456",
            ),
        ],
    )
    def test_key_shape_is_redacted_without_a_keyword(self, line, secret):
        redacted = _redact(line)
        assert secret not in redacted
        assert "[REDACTED]" in redacted

    @pytest.mark.parametrize(
        "line",
        [
            # rest_invoker logs the whole header dict; its repr puts quotes
            # between the header name and the token.
            "headers={'Authorization': 'Bearer sk-live-abc123def456'}",
            '{"Authorization": "Bearer sk-live-abc123def456"}',
            # No header name in reach at all.
            "Bearer sk-live-abc123def456",
        ],
    )
    def test_bearer_token_is_redacted_away_from_its_header_name(self, line):
        redacted = _redact(line)
        assert "sk-live-abc123def456" not in redacted
        assert "[REDACTED]" in redacted

    @pytest.mark.parametrize(
        "line",
        [
            # SQLAlchemy and the Celery broker write these exact schemes.
            f"postgresql://user:{_FAKE_PW}@host/db",
            f"postgresql+psycopg2://user:{_FAKE_PW}@host:5432/db",
            f"redis://default:{_FAKE_PW}@broker:6379/0",
            f"rediss://default:{_FAKE_PW}@broker:6379/0",
            f"amqps://guest:{_FAKE_PW}@rabbit:5671//",
            f"https://user:{_FAKE_PW}@example.com/callback",
        ],
    )
    def test_connection_url_password_is_redacted(self, line):
        redacted = _redact(line)
        assert _FAKE_PW not in redacted
        assert "[REDACTED]" in redacted

    def test_url_without_credentials_is_left_alone(self):
        line = "GET https://api.example.com/v1/things failed with 503"
        assert _redact(line) == line

    def test_bearer_token_is_redacted_once(self):
        """The generic authorization pattern must not re-fire on "Bearer"."""
        redacted = _redact("Authorization: Bearer sk-live-abc123def456")
        assert redacted == "Authorization: Bearer [REDACTED]"

    def test_redaction_stops_at_the_value_boundary(self):
        """A greedy value class swallowed the comma and the next field with it."""
        redacted = _redact("password: hunter2, user: bob")
        assert redacted == "password: [REDACTED], user: bob"


class TestJsonLogFormatterTraceback:
    """The JSON formatter is the one every deployed environment uses.

    The routers no longer log their own context -- they rely on the global
    exception handler's traceback -- so a JSON line without frames loses the
    error entirely.
    """

    @staticmethod
    def _emit(logger_call) -> dict:
        """Run *logger_call* through the real handler chain and parse the line."""
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(RedactingFormatter(JsonLogFormatter()))
        handler.addFilter(_WorkerContextFilter(None))
        logger = logging.getLogger("test_logging_security.json")
        logger.handlers = [handler]
        logger.propagate = False
        logger.setLevel(logging.DEBUG)
        try:
            logger_call(logger)
        finally:
            logger.handlers = []
        return json.loads(stream.getvalue())

    def test_exception_carries_the_traceback(self):
        def emit(logger):
            try:
                raise RuntimeError("upstream refused the call")
            except RuntimeError:
                logger.exception("Unhandled error in endpoint")

        payload = self._emit(emit)
        stack = payload["stack_trace"]
        assert "Traceback (most recent call last)" in stack
        assert "RuntimeError: upstream refused the call" in stack
        assert "test_logging_security.py" in stack

    def test_traceback_text_is_redacted(self):
        def emit(logger):
            try:
                raise RuntimeError("Incorrect API key provided: sk-proj-aBcD1234EfGh5678")
            except RuntimeError:
                logger.exception("Unhandled error in endpoint")

        payload = self._emit(emit)
        assert "sk-proj-aBcD1234EfGh5678" not in json.dumps(payload)
        assert "[REDACTED]" in payload["stack_trace"]

    def test_stack_info_is_included(self):
        payload = self._emit(lambda logger: logger.error("no exception", stack_info=True))
        assert "Stack (most recent call last)" in payload["stack_info"]

    def test_plain_record_has_no_traceback_fields(self):
        payload = self._emit(lambda logger: logger.info("nothing wrong"))
        assert "stack_trace" not in payload
        assert "stack_info" not in payload

    def test_explicit_request_id_survives_the_filter(self):
        """The global handler runs outside RequestIDMiddleware, so it passes the
        id via extra=; the filter used to overwrite it with the reset ContextVar."""
        payload = self._emit(
            lambda logger: logger.error("boom", extra={"request_id": "abc123def456"})
        )
        assert payload["request_id"] == "abc123def456"

    def test_request_id_is_absent_outside_a_request(self):
        payload = self._emit(lambda logger: logger.info("startup"))
        assert "request_id" not in payload
