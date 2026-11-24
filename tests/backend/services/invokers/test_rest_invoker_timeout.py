"""Tests for REST invoker timeout override from endpoint.timeout_seconds."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

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
            assert call_kwargs["timeout"].read == 90.0
            # Connecting gets a short share, so a dropped attempt stays a retryable error.
            assert call_kwargs["timeout"].connect == 10.0

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
            assert call_kwargs["timeout"].read == 30.0


def _failing_client(error: Exception) -> AsyncMock:
    client = AsyncMock()
    client.post = AsyncMock(side_effect=error)
    return client


class TestRestInvokerDeadline:
    @pytest.mark.asyncio
    async def test_deadline_covers_the_whole_call(self):
        """httpx's timeout is per socket read; a slow trickle must still stop at the timeout."""
        endpoint = _make_endpoint(timeout_seconds_in_metadata=1)
        invoker = RestEndpointInvoker()

        async def _slow(*_args, **_kwargs):
            await asyncio.sleep(30)

        with patch.object(invoker, "_async_request", side_effect=_slow):
            result = await asyncio.wait_for(
                invoker.invoke(Mock(), endpoint, {"input": "hi"}), timeout=10
            )
        assert result.error_type == "call_timeout"
        assert "did not finish within 1 second." in result.output

    @pytest.mark.asyncio
    async def test_connect_timeout_stays_a_network_error(self):
        """It never reached the API, so the run's retry may try again."""
        endpoint = _make_endpoint()
        invoker = RestEndpointInvoker()
        with patch.object(
            invoker, "_async_request", new_callable=AsyncMock, side_effect=httpx.ConnectTimeout("")
        ):
            result = await invoker.invoke(Mock(), endpoint, {"input": "hi"})
        assert result.error_type == "network_error"


class TestRestInvokerRetries:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "error", [httpx.ReadTimeout("no answer"), httpx.ConnectError("refused")]
    )
    async def test_request_is_sent_once(self, error):
        """Retries belong to invoke_with_retry; a second layer here multiplied the attempts."""
        client = _failing_client(error)
        with patch(
            "rhesis.backend.app.services.invokers.rest_invoker._get_http_client",
            return_value=client,
        ):
            with pytest.raises(type(error)):
                await RestEndpointInvoker()._async_request(
                    "POST", "https://api.example.com", {}, {}, timeout=60
                )
        assert client.post.await_count == 1


def test_short_timeouts_keep_half_for_connecting():
    from rhesis.backend.app.services.invokers.rest_invoker import _http_timeout

    timeout = _http_timeout(4)
    assert (timeout.connect, timeout.pool, timeout.read) == (2, 2, 4)
