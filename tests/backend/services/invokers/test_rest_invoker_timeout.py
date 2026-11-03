"""Tests for REST invoker timeout override from endpoint.timeout_seconds."""

from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from tenacity import wait_none

from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.app.models.enums import EndpointAuthType, EndpointConnectionType
from rhesis.backend.app.services.invokers.rest_invoker import RestEndpointInvoker


def _mock_httpx_response(status_code=200, json_data=None, text="", reason_phrase="OK"):
    resp = Mock(spec=httpx.Response)
    resp.status_code = status_code
    resp.reason_phrase = reason_phrase
    resp.text = text or ""
    resp.headers = {}
    if json_data is not None:
        resp.json.return_value = json_data
    return resp


def _make_endpoint(timeout_seconds_in_metadata=None):
    meta = {}
    if timeout_seconds_in_metadata is not None:
        meta["timeout_seconds"] = timeout_seconds_in_metadata
    return Endpoint(
        id="ep-timeout",
        name="Timeout EP",
        connection_type=EndpointConnectionType.REST.value,
        method="POST",
        url="https://api.example.com/chat",
        auth_type=EndpointAuthType.BEARER_TOKEN.value,
        auth_token="tok",
        request_mapping='{"msg": "{{ input }}"}',
        response_mapping={"output": "$.answer"},
        endpoint_metadata=meta or None,
        project_id="00000000-0000-0000-0000-000000000001",
    )


class TestRestInvokerTimeout:
    @pytest.mark.asyncio
    async def test_custom_timeout_forwarded(self):
        endpoint = _make_endpoint(timeout_seconds_in_metadata=90)
        invoker = RestEndpointInvoker()
        mock_resp = _mock_httpx_response(json_data={"answer": "ok"})

        with patch.object(
            invoker, "_async_request", new_callable=AsyncMock, return_value=mock_resp
        ) as mock_req:
            await invoker.invoke(Mock(), endpoint, {"input": "hi"}, test_execution_context=None)
            _, call_kwargs = mock_req.call_args
            assert call_kwargs.get("timeout") == 90.0

    @pytest.mark.asyncio
    async def test_no_timeout_uses_default(self):
        endpoint = _make_endpoint(timeout_seconds_in_metadata=None)
        invoker = RestEndpointInvoker()
        mock_resp = _mock_httpx_response(json_data={"answer": "ok"})

        with patch.object(
            invoker, "_async_request", new_callable=AsyncMock, return_value=mock_resp
        ) as mock_req:
            await invoker.invoke(Mock(), endpoint, {"input": "hi"}, test_execution_context=None)
            _, call_kwargs = mock_req.call_args
            assert call_kwargs.get("timeout") is None


def _failing_client(error: Exception) -> AsyncMock:
    client = AsyncMock()
    client.post = AsyncMock(side_effect=error)
    return client


# The real backoff waits 1-10s between tries; the attempt count is what matters here.
_request_without_backoff = RestEndpointInvoker._async_request.retry_with(wait=wait_none())


class TestRestInvokerRetries:
    @pytest.mark.asyncio
    async def test_read_timeout_is_not_retried(self):
        """The API had its whole timeout to answer; another try only triples the wait."""
        client = _failing_client(httpx.ReadTimeout("no answer"))
        with patch(
            "rhesis.backend.app.services.invokers.rest_invoker._get_http_client",
            return_value=client,
        ):
            with pytest.raises(httpx.ReadTimeout):
                await _request_without_backoff(
                    RestEndpointInvoker(), "POST", "https://api.example.com", {}, {}, timeout=60
                )
        assert client.post.await_count == 1

    @pytest.mark.asyncio
    async def test_connection_error_is_still_retried(self):
        client = _failing_client(httpx.ConnectError("refused"))
        with patch(
            "rhesis.backend.app.services.invokers.rest_invoker._get_http_client",
            return_value=client,
        ):
            with pytest.raises(httpx.ConnectError):
                await _request_without_backoff(
                    RestEndpointInvoker(), "POST", "https://api.example.com", {}, {}
                )
        assert client.post.await_count == 3
