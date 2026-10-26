"""REST invocations carry W3C trace context, so an instrumented service joins the trace."""

from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from rhesis.backend.app.services.invokers.context import InvocationContext
from rhesis.backend.app.services.invokers.rest_invoker import RestEndpointInvoker

TRACEPARENT = "00-" + "a" * 32 + "-" + "b" * 16 + "-01"


def _ok_response():
    resp = Mock(spec=httpx.Response)
    resp.status_code = 200
    resp.reason_phrase = "OK"
    resp.text = ""
    resp.headers = {}
    resp.json.return_value = {"response": {"text": "Success"}}
    return resp


async def _sent_headers(mock_db, endpoint, input_data, traceparent):
    invoker = RestEndpointInvoker(
        InvocationContext(
            db=mock_db, endpoint=endpoint, input_data=input_data, traceparent=traceparent
        )
    )
    invoker._async_request = AsyncMock(return_value=_ok_response())
    await invoker.invoke()
    return invoker._async_request.call_args.args[2]


@pytest.mark.asyncio
async def test_the_invocation_span_is_sent_as_the_parent(
    mock_db, sample_endpoint_rest, sample_input_data
):
    headers = await _sent_headers(mock_db, sample_endpoint_rest, sample_input_data, TRACEPARENT)

    assert headers["traceparent"] == TRACEPARENT


@pytest.mark.asyncio
async def test_an_endpoint_can_turn_it_off(mock_db, sample_endpoint_rest, sample_input_data):
    sample_endpoint_rest.endpoint_metadata = {"propagate_trace_context": False}

    headers = await _sent_headers(mock_db, sample_endpoint_rest, sample_input_data, TRACEPARENT)

    assert "traceparent" not in headers


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["traceparent", "Traceparent", "TRACEPARENT"])
async def test_a_traceparent_the_endpoint_configures_wins(
    mock_db, sample_endpoint_rest, sample_input_data, name
):
    """Header names are case-insensitive; two traceparents would void both."""
    own = "00-" + "c" * 32 + "-" + "d" * 16 + "-01"
    sample_endpoint_rest.request_headers = {name: own}

    headers = await _sent_headers(mock_db, sample_endpoint_rest, sample_input_data, TRACEPARENT)

    assert [value for key, value in headers.items() if key.lower() == "traceparent"] == [own]


@pytest.mark.asyncio
async def test_without_an_open_span_nothing_is_sent(
    mock_db, sample_endpoint_rest, sample_input_data
):
    headers = await _sent_headers(mock_db, sample_endpoint_rest, sample_input_data, None)

    assert "traceparent" not in headers
