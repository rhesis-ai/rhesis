"""Tests for REST endpoint invoker."""

from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from rhesis.backend.app.services.invokers.rest_invoker import RestEndpointInvoker


class TestRestEndpointInvoker:
    """Test RestEndpointInvoker class functionality."""

    def test_init_creates_required_components(self):
        """Test that invoker initializes with all required components."""
        invoker = RestEndpointInvoker()

        assert invoker.template_renderer is not None
        assert invoker.response_mapper is not None
        assert invoker.auth_manager is not None
        assert invoker.conversation_tracker is not None
        assert invoker.request_handlers is not None
        assert "POST" in invoker.request_handlers
        assert "GET" in invoker.request_handlers

    def test_invoke_success_with_simple_endpoint(
        self, mock_db, sample_endpoint_rest, sample_input_data
    ):
        """Test successful invocation of REST endpoint."""
        invoker = RestEndpointInvoker()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": {"text": "Paris is the capital of France."},
            "usage": {"total_tokens": 42},
        }

        with patch("requests.post", return_value=mock_response):
            result = invoker.invoke(mock_db, sample_endpoint_rest, sample_input_data)

        assert result["output"] == "Paris is the capital of France."
        assert result["tokens"] == 42

    def test_invoke_with_conversation_tracking(
        self, mock_db, sample_endpoint_conversation, sample_input_data
    ):
        """Test invocation with conversation tracking."""
        invoker = RestEndpointInvoker()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": "Hello!",
            "conversation_id": "conv-123",
            "context": "greeting",
        }

        with patch("requests.post", return_value=mock_response):
            result = invoker.invoke(mock_db, sample_endpoint_conversation, sample_input_data)

        assert result["output"] == "Hello!"
        assert result["conversation_id"] == "conv-123"
        assert result["context"] == ["greeting"]  # Context is normalized to a list

    def test_invoke_forwards_conversation_id(self, mock_db, sample_endpoint_conversation):
        """Test that conversation_id is forwarded in subsequent requests."""
        invoker = RestEndpointInvoker()
        input_data = {"input": "Follow-up question", "conversation_id": "conv-456"}

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": "Response",
            "conversation_id": "conv-789",
        }

        with patch("requests.post", return_value=mock_response) as mock_post:
            result = invoker.invoke(mock_db, sample_endpoint_conversation, input_data)

            # Verify conversation_id was included in request body
            call_args = mock_post.call_args
            request_body = call_args[1]["json"]
            assert request_body["conversation_id"] == "conv-456"

        assert result["conversation_id"] == "conv-789"

    def test_invoke_with_http_error(self, mock_db, sample_endpoint_rest, sample_input_data):
        """Test handling of HTTP error responses."""
        invoker = RestEndpointInvoker()

        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.reason = "Not Found"
        mock_response.text = "Endpoint not found"
        mock_response.headers = {}

        with patch("requests.post", return_value=mock_response):
            result = invoker.invoke(mock_db, sample_endpoint_rest, sample_input_data)

        assert result["error"] is True
        assert result["error_type"] == "http_error"
        assert "404" in result["message"]

    def test_invoke_with_network_error(self, mock_db, sample_endpoint_rest, sample_input_data):
        """Test handling of network errors."""
        invoker = RestEndpointInvoker()

        import requests

        with patch(
            "requests.post", side_effect=requests.exceptions.ConnectionError("Connection refused")
        ):
            result = invoker.invoke(mock_db, sample_endpoint_rest, sample_input_data)

        assert result["error"] is True
        assert result["error_type"] == "network_error"
        assert "Connection refused" in result["message"]

    def test_invoke_with_json_parsing_error(self, mock_db, sample_endpoint_rest, sample_input_data):
        """Test handling of invalid JSON response."""
        invoker = RestEndpointInvoker()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.text = "Not JSON"
        mock_response.headers = {}

        with patch("requests.post", return_value=mock_response):
            result = invoker.invoke(mock_db, sample_endpoint_rest, sample_input_data)

        assert result["error"] is True
        assert result["error_type"] == "json_parsing_error"

    def test_invoke_with_get_method(self, mock_db, sample_endpoint_rest, sample_input_data):
        """Test invocation with GET method."""
        invoker = RestEndpointInvoker()
        sample_endpoint_rest.method = "GET"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": {"text": "Success"}}

        with patch("requests.get", return_value=mock_response) as mock_get:
            invoker.invoke(mock_db, sample_endpoint_rest, sample_input_data)

            # Verify GET was called
            assert mock_get.called

    def test_invoke_with_put_method(self, mock_db, sample_endpoint_rest, sample_input_data):
        """Test invocation with PUT method."""
        invoker = RestEndpointInvoker()
        sample_endpoint_rest.method = "PUT"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": {"text": "Updated"}}

        with patch("requests.put", return_value=mock_response) as mock_put:
            invoker.invoke(mock_db, sample_endpoint_rest, sample_input_data)

            assert mock_put.called

    def test_invoke_with_delete_method(self, mock_db, sample_endpoint_rest, sample_input_data):
        """Test invocation with DELETE method."""
        invoker = RestEndpointInvoker()
        sample_endpoint_rest.method = "DELETE"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": {"text": "Deleted"}}

        with patch("requests.delete", return_value=mock_response) as mock_delete:
            invoker.invoke(mock_db, sample_endpoint_rest, sample_input_data)

            assert mock_delete.called

    def test_invoke_with_unsupported_method(self, mock_db, sample_endpoint_rest, sample_input_data):
        """Test invocation with unsupported HTTP method."""
        invoker = RestEndpointInvoker()
        sample_endpoint_rest.method = "PATCH"

        with pytest.raises(HTTPException) as exc_info:
            invoker.invoke(mock_db, sample_endpoint_rest, sample_input_data)

        assert exc_info.value.status_code == 400
        assert "Unsupported HTTP method" in str(exc_info.value.detail)

    def test_prepare_headers_with_bearer_token(self, mock_db, sample_endpoint_rest):
        """Test header preparation with bearer token."""
        invoker = RestEndpointInvoker()

        headers = invoker._prepare_headers(mock_db, sample_endpoint_rest, {})

        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer test-bearer-token"
        assert headers["Content-Type"] == "application/json"

    def test_prepare_headers_with_context_injection(self, mock_db, sample_endpoint_rest):
        """Test header preparation with context injection."""
        invoker = RestEndpointInvoker()
        input_data = {"organization_id": "org-123", "user_id": "user-456"}

        headers = invoker._prepare_headers(mock_db, sample_endpoint_rest, input_data)

        assert headers["X-Organization-ID"] == "org-123"
        assert headers["X-User-ID"] == "user-456"

    def test_invoke_preserves_unmapped_error_fields(
        self, mock_db, sample_endpoint_rest, sample_input_data
    ):
        """Test that important unmapped fields are preserved in response."""
        invoker = RestEndpointInvoker()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": {"text": "Result"},
            "error": "Warning message",
            "status": "partial_success",
            "message": "Processing completed with warnings",
        }

        with patch("requests.post", return_value=mock_response):
            result = invoker.invoke(mock_db, sample_endpoint_rest, sample_input_data)

        # Unmapped but important fields should be preserved
        assert result["error"] == "Warning message"
        assert result["status"] == "partial_success"
        assert result["message"] == "Processing completed with warnings"
