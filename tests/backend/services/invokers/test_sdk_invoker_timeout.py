"""Tests for SDK invoker timeout override from endpoint.timeout_seconds."""

from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID

import pytest

from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.app.models.enums import EndpointConnectionType
from rhesis.backend.app.services.invokers.sdk_invoker import (
    SDK_FUNCTION_TIMEOUT,
    SdkEndpointInvoker,
)

TEST_PROJECT_ID = UUID("00000000-0000-0000-0000-000000000001")


def _sdk_endpoint(timeout_seconds_in_metadata=None):
    meta = {
        "sdk_connection": {
            "function_name": "my_func",
        }
    }
    if timeout_seconds_in_metadata is not None:
        meta["timeout_seconds"] = timeout_seconds_in_metadata
    return Endpoint(
        id="ep-sdk-timeout",
        name="SDK Timeout EP",
        connection_type=EndpointConnectionType.SDK.value,
        url="",
        environment="development",
        request_mapping={"input": "{{ input }}"},
        response_mapping={"output": "$.output"},
        endpoint_metadata=meta,
        project_id=TEST_PROJECT_ID,
        organization_id=TEST_PROJECT_ID,
    )


class TestSdkInvokerTimeout:
    @pytest.mark.asyncio
    async def test_custom_timeout_passed_to_rpc(self):
        endpoint = _sdk_endpoint(timeout_seconds_in_metadata=180)
        invoker = SdkEndpointInvoker()

        rpc_result = {"output": "hello", "status": "ok"}

        with (
            patch.object(
                invoker,
                "_determine_invocation_context",
                return_value=(True, "WORKER (RPC)"),
            ),
            patch.object(
                invoker,
                "_execute_via_rpc",
                new_callable=AsyncMock,
                return_value=rpc_result,
            ) as mock_rpc,
        ):
            await invoker.invoke(
                Mock(), endpoint, {"input": "hi"}, test_execution_context=None
            )
            call_kwargs = mock_rpc.call_args
            assert call_kwargs.kwargs.get("timeout") == 180.0

    @pytest.mark.asyncio
    async def test_no_timeout_uses_sdk_default(self):
        endpoint = _sdk_endpoint(timeout_seconds_in_metadata=None)
        invoker = SdkEndpointInvoker()

        rpc_result = {"output": "hello", "status": "ok"}

        with (
            patch.object(
                invoker,
                "_determine_invocation_context",
                return_value=(True, "WORKER (RPC)"),
            ),
            patch.object(
                invoker,
                "_execute_via_rpc",
                new_callable=AsyncMock,
                return_value=rpc_result,
            ) as mock_rpc,
        ):
            await invoker.invoke(
                Mock(), endpoint, {"input": "hi"}, test_execution_context=None
            )
            call_kwargs = mock_rpc.call_args
            assert call_kwargs.kwargs.get("timeout") == SDK_FUNCTION_TIMEOUT

    @pytest.mark.asyncio
    async def test_custom_timeout_passed_to_websocket(self):
        endpoint = _sdk_endpoint(timeout_seconds_in_metadata=60)
        invoker = SdkEndpointInvoker()

        ws_result = {"output": "world", "status": "ok"}

        with (
            patch.object(
                invoker,
                "_determine_invocation_context",
                return_value=(False, "BACKEND (direct WebSocket)"),
            ),
            patch.object(
                invoker,
                "_execute_via_websocket",
                new_callable=AsyncMock,
                return_value=ws_result,
            ) as mock_ws,
        ):
            await invoker.invoke(
                Mock(), endpoint, {"input": "hi"}, test_execution_context=None
            )
            call_kwargs = mock_ws.call_args
            assert call_kwargs.kwargs.get("timeout") == 60.0
