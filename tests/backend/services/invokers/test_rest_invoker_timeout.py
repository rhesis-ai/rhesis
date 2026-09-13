"""Tests for REST invoker timeout override from endpoint.timeout_seconds."""

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
            await invoker.invoke(
                Mock(), endpoint, {"input": "hi"}, test_execution_context=None
            )
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
            await invoker.invoke(
                Mock(), endpoint, {"input": "hi"}, test_execution_context=None
            )
            _, call_kwargs = mock_req.call_args
            assert call_kwargs.get("timeout") is None
