"""Tests for common utility classes."""

from rhesis.backend.app.services.invokers.common.errors import ErrorResponseBuilder
from rhesis.backend.app.services.invokers.common.headers import HeaderManager


class TestHeaderManager:
    """Test HeaderManager class functionality."""

    def test_sanitize_headers_redacts_authorization(self):
        """Test that Authorization header is redacted."""
        headers = {"Authorization": "Bearer secret-token", "Content-Type": "application/json"}

        result = HeaderManager.sanitize_headers(headers)

        assert result["Authorization"] == "***REDACTED***"
        assert result["Content-Type"] == "application/json"

    def test_sanitize_headers_redacts_api_key(self):
        """Test that API key headers are redacted."""
        headers = {"X-API-Key": "secret-key", "x-api-key": "another-key", "User-Agent": "test"}

        result = HeaderManager.sanitize_headers(headers)

        assert result["X-API-Key"] == "***REDACTED***"
        assert result["x-api-key"] == "***REDACTED***"
        assert result["User-Agent"] == "test"

    def test_sanitize_headers_redacts_auth_token(self):
        """Test that auth token headers are redacted."""
        headers = {"X-Auth-Token": "secret", "X-Access-Token": "token"}

        result = HeaderManager.sanitize_headers(headers)

        assert result["X-Auth-Token"] == "***REDACTED***"
        assert result["X-Access-Token"] == "***REDACTED***"

    def test_sanitize_headers_redacts_cookie(self):
        """Test that Cookie header is redacted."""
        headers = {"Cookie": "session=abc123", "Accept": "application/json"}

        result = HeaderManager.sanitize_headers(headers)

        assert result["Cookie"] == "***REDACTED***"
        assert result["Accept"] == "application/json"

    def test_sanitize_headers_case_insensitive(self):
        """Test that sanitization is case-insensitive."""
        headers = {
            "AUTHORIZATION": "Bearer token",
            "authorization": "Bearer token2",
            "Authorization": "Bearer token3",
        }

        result = HeaderManager.sanitize_headers(headers)

        assert all(v == "***REDACTED***" for v in result.values())

    def test_sanitize_headers_empty_dict(self):
        """Test sanitizing empty headers dict."""
        result = HeaderManager.sanitize_headers({})

        assert result == {}

    def test_sanitize_headers_none(self):
        """Test sanitizing None headers."""
        result = HeaderManager.sanitize_headers(None)

        assert result == {}

    def test_sanitize_headers_preserves_safe_headers(self):
        """Test that safe headers are not redacted."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US",
        }

        result = HeaderManager.sanitize_headers(headers)

        assert result == headers

    def test_inject_context_headers_adds_organization_id(self):
        """Test injecting organization_id header."""
        headers = {}
        input_data = {"organization_id": "org-123", "input": "test"}

        HeaderManager.inject_context_headers(headers, input_data)

        assert headers["X-Organization-ID"] == "org-123"

    def test_inject_context_headers_adds_user_id(self):
        """Test injecting user_id header."""
        headers = {}
        input_data = {"user_id": "user-456", "input": "test"}

        HeaderManager.inject_context_headers(headers, input_data)

        assert headers["X-User-ID"] == "user-456"

    def test_inject_context_headers_adds_both(self):
        """Test injecting both context headers."""
        headers = {}
        input_data = {"organization_id": "org-123", "user_id": "user-456"}

        HeaderManager.inject_context_headers(headers, input_data)

        assert headers["X-Organization-ID"] == "org-123"
        assert headers["X-User-ID"] == "user-456"

    def test_inject_context_headers_doesnt_override_existing(self):
        """Test that existing headers are not overridden."""
        headers = {"X-Organization-ID": "existing-org"}
        input_data = {"organization_id": "org-123"}

        HeaderManager.inject_context_headers(headers, input_data)

        assert headers["X-Organization-ID"] == "existing-org"

    def test_inject_context_headers_with_none_input(self):
        """Test injecting headers with None input_data."""
        headers = {}

        HeaderManager.inject_context_headers(headers, None)

        assert headers == {}

    def test_inject_context_headers_with_missing_fields(self):
        """Test injecting headers when fields are missing from input."""
        headers = {}
        input_data = {"input": "test"}

        HeaderManager.inject_context_headers(headers, input_data)

        assert "X-Organization-ID" not in headers
        assert "X-User-ID" not in headers


class TestErrorResponseBuilder:
    """Test ErrorResponseBuilder class functionality."""

    def test_create_error_response_basic(self):
        """Test creating a basic error response."""
        builder = ErrorResponseBuilder()

        result = builder.create_error_response(
            error_type="network_error",
            output_message="Connection failed",
            message="Network timeout",
        )

        assert result["output"] == "Connection failed"
        assert result["error"] is True
        assert result["error_type"] == "network_error"
        assert result["message"] == "Network timeout"

    def test_create_error_response_with_request_details(self):
        """Test creating error response with request details."""
        builder = ErrorResponseBuilder()
        request_details = {
            "connection_type": "REST",
            "method": "POST",
            "url": "https://api.example.com",
        }

        result = builder.create_error_response(
            error_type="http_error",
            output_message="HTTP 500",
            message="Server error",
            request_details=request_details,
        )

        assert result["request"] == request_details

    def test_create_error_response_with_kwargs(self):
        """Test creating error response with additional kwargs."""
        builder = ErrorResponseBuilder()

        result = builder.create_error_response(
            error_type="validation_error",
            output_message="Invalid input",
            message="Field validation failed",
            status_code=400,
            field="email",
        )

        assert result["status_code"] == 400
        assert result["field"] == "email"

    def test_safe_request_details_basic(self):
        """Test creating safe request details from local vars."""
        builder = ErrorResponseBuilder()
        local_vars = {
            "method": "POST",
            "url": "https://api.example.com/chat",
            "headers": {"Authorization": "Bearer secret", "Content-Type": "application/json"},
        }

        result = builder.safe_request_details(local_vars, "REST")

        assert result["connection_type"] == "REST"
        assert result["method"] == "POST"
        assert result["url"] == "https://api.example.com/chat"
        assert result["headers"]["Authorization"] == "***REDACTED***"
        assert result["headers"]["Content-Type"] == "application/json"

    def test_safe_request_details_with_uri(self):
        """Test safe request details with uri instead of url."""
        builder = ErrorResponseBuilder()
        local_vars = {
            "uri": "wss://ws.example.com/chat",
            "headers": {},
        }

        result = builder.safe_request_details(local_vars, "WebSocket")

        assert result["connection_type"] == "WebSocket"
        assert result["url"] == "wss://ws.example.com/chat"

    def test_safe_request_details_with_message_data(self):
        """Test safe request details with message_data instead of request_body."""
        builder = ErrorResponseBuilder()
        local_vars = {
            "message_data": {"query": "test"},
        }

        result = builder.safe_request_details(local_vars)

        assert result["body"] == {"query": "test"}

    def test_safe_request_details_defaults(self):
        """Test safe request details with missing fields."""
        builder = ErrorResponseBuilder()
        local_vars = {}

        result = builder.safe_request_details(local_vars)

        assert result["connection_type"] == "unknown"
        assert result["method"] == "UNKNOWN"
        assert result["url"] == "UNKNOWN"
        assert result["headers"] == {}
        assert result["body"] is None
