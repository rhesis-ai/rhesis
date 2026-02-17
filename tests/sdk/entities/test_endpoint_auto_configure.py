"""Unit tests for Endpoint.auto_configure() class method."""

import os
from unittest.mock import MagicMock, patch

from rhesis.sdk.entities.endpoint import ConnectionType, Endpoint

os.environ["RHESIS_BASE_URL"] = "http://test:8000"

# Reusable mock responses
SUCCESS_RESULT = {
    "status": "success",
    "request_mapping": {"messages": [{"role": "user", "content": "{{ input }}"}]},
    "response_mapping": {"output": "$.choices[0].message.content"},
    "request_headers": {
        "Content-Type": "application/json",
        "Authorization": "Bearer {{ auth_token }}",
    },
    "url": "https://api.example.com/chat",
    "method": "POST",
    "conversation_mode": "single_turn",
    "confidence": 0.85,
    "reasoning": "Detected OpenAI-compatible API",
    "warnings": [],
    "probe_success": True,
    "probe_attempts": 1,
}

PARTIAL_RESULT = {
    "status": "partial",
    "request_mapping": {"messages": [{"role": "user", "content": "{{ input }}"}]},
    "response_mapping": None,
    "request_headers": {"Content-Type": "application/json"},
    "url": "https://api.example.com/chat",
    "method": "POST",
    "conversation_mode": "single_turn",
    "confidence": 0.4,
    "reasoning": "Could not verify with probe",
    "warnings": ["Mapping generated but could not be verified via endpoint probe."],
    "probe_success": False,
    "probe_attempts": 3,
    "probe_error": "HTTP 422: validation error",
}

FAILED_RESULT = {
    "status": "failed",
    "error": "Could not parse the input",
    "reasoning": "The AI could not identify an API structure",
}


class TestAutoConfigureSuccess:
    """Tests for successful auto-configure calls."""

    @patch("requests.request")
    def test_auto_configure_success(self, mock_request):
        """auto_configure should return Endpoint with mappings on success."""
        mock_response = MagicMock()
        mock_response.json.return_value = SUCCESS_RESULT
        mock_request.return_value = mock_response

        endpoint = Endpoint.auto_configure(
            input_text='curl -X POST https://api.example.com/chat -d \'{"query": "hi"}\'',
            url="https://api.example.com/chat",
            auth_token="token123",
        )

        assert endpoint is not None
        assert endpoint.request_mapping == SUCCESS_RESULT["request_mapping"]
        assert endpoint.response_mapping == SUCCESS_RESULT["response_mapping"]
        assert endpoint.request_headers == SUCCESS_RESULT["request_headers"]
        assert endpoint.url == "https://api.example.com/chat"
        assert endpoint.method == "POST"
        assert endpoint.connection_type == ConnectionType.REST

    @patch("requests.request")
    def test_auto_configure_sends_correct_payload(self, mock_request):
        """auto_configure should POST to /endpoints/auto-configure with correct body."""
        mock_response = MagicMock()
        mock_response.json.return_value = SUCCESS_RESULT
        mock_request.return_value = mock_response

        Endpoint.auto_configure(
            input_text="some curl command",
            url="https://api.example.com",
            auth_token="my-token",
            method="POST",
            probe=True,
        )

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        url_value = call_args.kwargs.get(
            "url",
            call_args.args[1] if len(call_args.args) > 1 else "",
        )
        assert "auto-configure" in url_value
        request_data = call_args.kwargs.get("json", {})
        assert request_data["input_text"] == "some curl command"
        assert request_data["url"] == "https://api.example.com"
        assert request_data["auth_token"] == "my-token"
        assert request_data["method"] == "POST"
        assert request_data["probe"] is True

    @patch("requests.request")
    def test_auto_configure_preserves_auth_token(self, mock_request):
        """Returned endpoint should have auth_token set from input parameter."""
        mock_response = MagicMock()
        mock_response.json.return_value = SUCCESS_RESULT
        mock_request.return_value = mock_response

        endpoint = Endpoint.auto_configure(
            input_text="some code",
            url="https://api.example.com",
            auth_token="secret-token-123",
        )

        assert endpoint is not None
        assert endpoint.auth_token == "secret-token-123"

    @patch("requests.request")
    def test_auto_configure_sets_name_and_project(self, mock_request):
        """When name and project_id are passed, they should appear on the endpoint."""
        mock_response = MagicMock()
        mock_response.json.return_value = SUCCESS_RESULT
        mock_request.return_value = mock_response

        endpoint = Endpoint.auto_configure(
            input_text="some code",
            url="https://api.example.com",
            name="My Chat API",
            project_id="project-uuid-123",
        )

        assert endpoint is not None
        assert endpoint.name == "My Chat API"
        assert endpoint.project_id == "project-uuid-123"


class TestAutoConfigureFailure:
    """Tests for auto-configure failure cases."""

    @patch("requests.request")
    def test_auto_configure_failed_returns_none(self, mock_request):
        """auto_configure should return None when status is 'failed'."""
        mock_response = MagicMock()
        mock_response.json.return_value = FAILED_RESULT
        mock_request.return_value = mock_response

        endpoint = Endpoint.auto_configure(
            input_text="garbled text",
            url="https://api.example.com",
        )

        assert endpoint is None

    @patch("requests.request")
    def test_auto_configure_http_error_returns_none(self, mock_request):
        """auto_configure should return None on HTTP errors."""
        from requests.exceptions import HTTPError

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.content = b"Internal Server Error"
        mock_response.request.url = "http://test:8000/api/v1/endpoints/auto-configure"
        mock_response.request.method = "POST"
        mock_response.request.headers = {}
        mock_response.request.body = None

        error = HTTPError("500 Server Error", response=mock_response)
        mock_response.raise_for_status.side_effect = error
        mock_request.return_value = mock_response

        # The @handle_http_errors decorator should catch this
        endpoint = Endpoint.auto_configure(
            input_text="some code",
            url="https://api.example.com",
        )

        assert endpoint is None


class TestAutoConfigurePartial:
    """Tests for partial auto-configure results."""

    @patch("requests.request")
    def test_auto_configure_partial_returns_endpoint(self, mock_request):
        """auto_configure should return Endpoint even with partial status."""
        mock_response = MagicMock()
        mock_response.json.return_value = PARTIAL_RESULT
        mock_request.return_value = mock_response

        endpoint = Endpoint.auto_configure(
            input_text="some code",
            url="https://api.example.com",
        )

        assert endpoint is not None
        assert endpoint.request_mapping == PARTIAL_RESULT["request_mapping"]
        # response_mapping is None for partial
        assert endpoint.response_mapping is None


class TestAutoConfigureResult:
    """Tests for accessing auto-configure metadata."""

    @patch("requests.request")
    def test_auto_configure_result_accessible(self, mock_request):
        """After success, auto_configure_result should have full result dict."""
        mock_response = MagicMock()
        mock_response.json.return_value = SUCCESS_RESULT
        mock_request.return_value = mock_response

        endpoint = Endpoint.auto_configure(
            input_text="some code",
            url="https://api.example.com",
        )

        assert endpoint is not None
        result = endpoint.auto_configure_result
        assert result is not None
        assert result["confidence"] == 0.85
        assert result["reasoning"] == "Detected OpenAI-compatible API"
        assert result["warnings"] == []
        assert result["probe_success"] is True

    def test_auto_configure_result_none_for_regular_endpoint(self):
        """Regular endpoints should have auto_configure_result as None."""
        endpoint = Endpoint(name="Regular API")
        assert endpoint.auto_configure_result is None


class TestAutoConfigureProbeToggle:
    """Tests for probe toggle parameter."""

    @patch("requests.request")
    def test_auto_configure_probe_disabled(self, mock_request):
        """When probe=False, payload should contain probe: false."""
        mock_response = MagicMock()
        mock_response.json.return_value = SUCCESS_RESULT
        mock_request.return_value = mock_response

        Endpoint.auto_configure(
            input_text="some code",
            url="https://api.example.com",
            probe=False,
        )

        call_args = mock_request.call_args
        request_data = call_args.kwargs.get("json", {})
        assert request_data["probe"] is False


class TestAutoConfigurePushWorkflow:
    """Tests for push after auto-configure."""

    @patch("requests.request")
    def test_auto_configure_push_after_configure(self, mock_request):
        """After auto_configure, push() should send generated mappings."""
        # First call: auto-configure
        # Second call: push
        mock_response = MagicMock()
        mock_response.json.side_effect = [
            SUCCESS_RESULT,
            {"id": "new-endpoint-id", "name": "My API"},
        ]
        mock_request.return_value = mock_response

        endpoint = Endpoint.auto_configure(
            input_text="some code",
            url="https://api.example.com",
            auth_token="token123",
            name="My API",
            project_id="project-123",
        )

        assert endpoint is not None
        endpoint.push()

        # Verify push was called (second call)
        assert mock_request.call_count == 2
        push_call = mock_request.call_args_list[-1]
        push_data = push_call.kwargs.get("json", {})
        assert push_data.get("name") == "My API"
        assert push_data.get("request_mapping") == SUCCESS_RESULT["request_mapping"]
