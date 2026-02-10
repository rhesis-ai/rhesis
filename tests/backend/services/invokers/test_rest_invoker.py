"""Tests for REST endpoint invoker."""

from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from fastapi import HTTPException

from rhesis.backend.app.services.invokers.rest_invoker import RestEndpointInvoker


def _mock_httpx_response(
    status_code=200, json_data=None, text="", reason_phrase="OK", headers=None
):
    """Create a mock httpx.Response."""
    resp = Mock(spec=httpx.Response)
    resp.status_code = status_code
    resp.reason_phrase = reason_phrase
    resp.text = text or ""
    resp.headers = headers or {}
    if json_data is not None:
        resp.json.return_value = json_data
    return resp


class TestRestEndpointInvoker:
    """Test RestEndpointInvoker class functionality."""

    def test_init_creates_required_components(self):
        """Test that invoker initializes with all required components."""
        invoker = RestEndpointInvoker()

        assert invoker.template_renderer is not None
        assert invoker.response_mapper is not None
        assert invoker.auth_manager is not None
        assert invoker.conversation_tracker is not None

    @pytest.mark.asyncio
    async def test_invoke_success_with_simple_endpoint(
        self, mock_db, sample_endpoint_rest, sample_input_data
    ):
        """Test successful invocation of REST endpoint."""
        invoker = RestEndpointInvoker()

        mock_response = _mock_httpx_response(
            json_data={
                "response": {"text": "Paris is the capital of France."},
                "usage": {"total_tokens": 42},
            }
        )

        with patch.object(
            invoker, "_async_request", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await invoker.invoke(
                mock_db, sample_endpoint_rest, sample_input_data, test_execution_context=None
            )

        assert result["output"] == "Paris is the capital of France."
        assert result["tokens"] == 42

    @pytest.mark.asyncio
    async def test_invoke_with_conversation_tracking(
        self, mock_db, sample_endpoint_conversation, sample_input_data
    ):
        """Test invocation with conversation tracking."""
        invoker = RestEndpointInvoker()

        mock_response = _mock_httpx_response(
            json_data={
                "message": "Hello!",
                "conversation_id": "conv-123",
                "context": "greeting",
            }
        )

        with patch.object(
            invoker, "_async_request", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await invoker.invoke(mock_db, sample_endpoint_conversation, sample_input_data)

        assert result["output"] == "Hello!"
        assert result["conversation_id"] == "conv-123"
        assert result["context"] == ["greeting"]  # Context is normalized to a list

    @pytest.mark.asyncio
    async def test_invoke_forwards_conversation_id(self, mock_db, sample_endpoint_conversation):
        """Test that conversation_id is forwarded in subsequent requests."""
        invoker = RestEndpointInvoker()
        input_data = {"input": "Follow-up question", "conversation_id": "conv-456"}

        mock_response = _mock_httpx_response(
            json_data={
                "message": "Response",
                "conversation_id": "conv-789",
            }
        )

        with patch.object(
            invoker, "_async_request", new_callable=AsyncMock, return_value=mock_response
        ) as mock_req:
            result = await invoker.invoke(mock_db, sample_endpoint_conversation, input_data)

            # Verify _async_request was called
            assert mock_req.called

        assert result["conversation_id"] == "conv-789"

    @pytest.mark.asyncio
    async def test_invoke_with_http_error(self, mock_db, sample_endpoint_rest, sample_input_data):
        """Test handling of HTTP error responses."""
        invoker = RestEndpointInvoker()

        mock_response = _mock_httpx_response(
            status_code=404,
            reason_phrase="Not Found",
            text="Endpoint not found",
        )

        with patch.object(
            invoker, "_async_request", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await invoker.invoke(mock_db, sample_endpoint_rest, sample_input_data)

        # Convert ErrorResponse to dict for testing (Pydantic v1/v2 compatible)
        if hasattr(result, "to_dict"):
            result = result.to_dict()
        elif hasattr(result, "model_dump"):
            result = result.model_dump(exclude_none=True)
        elif hasattr(result, "dict"):
            result = result.dict(exclude_none=True)

        assert result["error"] is True
        assert result["error_type"] == "http_error"
        assert "404" in result["message"]

    @pytest.mark.asyncio
    async def test_invoke_with_network_error(
        self, mock_db, sample_endpoint_rest, sample_input_data
    ):
        """Test handling of network errors."""
        invoker = RestEndpointInvoker()

        with patch.object(
            invoker,
            "_async_request",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            result = await invoker.invoke(mock_db, sample_endpoint_rest, sample_input_data)

        # Convert ErrorResponse to dict for testing (Pydantic v1/v2 compatible)
        if hasattr(result, "to_dict"):
            result = result.to_dict()
        elif hasattr(result, "model_dump"):
            result = result.model_dump(exclude_none=True)
        elif hasattr(result, "dict"):
            result = result.dict(exclude_none=True)

        assert result["error"] is True
        assert result["error_type"] == "network_error"
        assert "Connection refused" in result["message"]

    @pytest.mark.asyncio
    async def test_invoke_with_json_parsing_error(
        self, mock_db, sample_endpoint_rest, sample_input_data
    ):
        """Test handling of invalid JSON response."""
        invoker = RestEndpointInvoker()

        mock_response = _mock_httpx_response(status_code=200, text="Not JSON")
        mock_response.json.side_effect = ValueError("Invalid JSON")

        with patch.object(
            invoker, "_async_request", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await invoker.invoke(mock_db, sample_endpoint_rest, sample_input_data)

        # Convert ErrorResponse to dict for testing (Pydantic v1/v2 compatible)
        if hasattr(result, "to_dict"):
            result = result.to_dict()
        elif hasattr(result, "model_dump"):
            result = result.model_dump(exclude_none=True)
        elif hasattr(result, "dict"):
            result = result.dict(exclude_none=True)

        assert result["error"] is True
        assert result["error_type"] == "json_parsing_error"

    @pytest.mark.asyncio
    async def test_invoke_with_get_method(self, mock_db, sample_endpoint_rest, sample_input_data):
        """Test invocation with GET method."""
        invoker = RestEndpointInvoker()
        sample_endpoint_rest.method = "GET"

        mock_response = _mock_httpx_response(json_data={"response": {"text": "Success"}})

        with patch.object(
            invoker, "_async_request", new_callable=AsyncMock, return_value=mock_response
        ) as mock_req:
            await invoker.invoke(mock_db, sample_endpoint_rest, sample_input_data)

            # Verify _async_request was called with GET method
            assert mock_req.called
            assert mock_req.call_args[0][0] == "GET"

    @pytest.mark.asyncio
    async def test_invoke_with_put_method(self, mock_db, sample_endpoint_rest, sample_input_data):
        """Test invocation with PUT method."""
        invoker = RestEndpointInvoker()
        sample_endpoint_rest.method = "PUT"

        mock_response = _mock_httpx_response(json_data={"response": {"text": "Updated"}})

        with patch.object(
            invoker, "_async_request", new_callable=AsyncMock, return_value=mock_response
        ) as mock_req:
            await invoker.invoke(mock_db, sample_endpoint_rest, sample_input_data)

            assert mock_req.called
            assert mock_req.call_args[0][0] == "PUT"

    @pytest.mark.asyncio
    async def test_invoke_with_delete_method(
        self, mock_db, sample_endpoint_rest, sample_input_data
    ):
        """Test invocation with DELETE method."""
        invoker = RestEndpointInvoker()
        sample_endpoint_rest.method = "DELETE"

        mock_response = _mock_httpx_response(json_data={"response": {"text": "Deleted"}})

        with patch.object(
            invoker, "_async_request", new_callable=AsyncMock, return_value=mock_response
        ) as mock_req:
            await invoker.invoke(mock_db, sample_endpoint_rest, sample_input_data)

            assert mock_req.called
            assert mock_req.call_args[0][0] == "DELETE"

    @pytest.mark.asyncio
    async def test_invoke_with_unsupported_method(
        self, mock_db, sample_endpoint_rest, sample_input_data
    ):
        """Test invocation with unsupported HTTP method."""
        invoker = RestEndpointInvoker()
        sample_endpoint_rest.method = "PATCH"

        with pytest.raises(HTTPException) as exc_info:
            await invoker.invoke(mock_db, sample_endpoint_rest, sample_input_data)

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

    @pytest.mark.asyncio
    async def test_invoke_preserves_unmapped_error_fields(
        self, mock_db, sample_endpoint_rest, sample_input_data
    ):
        """Test that important unmapped fields are preserved in response."""
        invoker = RestEndpointInvoker()

        mock_response = _mock_httpx_response(
            json_data={
                "response": {"text": "Result"},
                "error": "Warning message",
                "status": "partial_success",
                "message": "Processing completed with warnings",
            }
        )

        with patch.object(
            invoker, "_async_request", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await invoker.invoke(mock_db, sample_endpoint_rest, sample_input_data)

        # Unmapped but important fields should be preserved
        assert result["error"] == "Warning message"
        assert result["status"] == "partial_success"
        assert result["message"] == "Processing completed with warnings"
