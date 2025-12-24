"""Tests for manual trace creation utility."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.app.services.invokers.manual_tracing import (
    EndpointAttributes,
    create_endpoint_attributes,
    create_manual_invocation_trace,
    generate_span_id,
    generate_trace_id,
)
from rhesis.sdk.telemetry.schemas import SpanKind, StatusCode


def test_generate_trace_id():
    """Test trace ID generation."""
    trace_id = generate_trace_id()
    assert len(trace_id) == 32
    assert all(c in "0123456789abcdef" for c in trace_id)


def test_generate_span_id():
    """Test span ID generation."""
    span_id = generate_span_id()
    assert len(span_id) == 16
    assert all(c in "0123456789abcdef" for c in span_id)


def test_endpoint_attributes_constants():
    """Test EndpointAttributes class has all required constants."""
    assert hasattr(EndpointAttributes, "ENDPOINT_ID")
    assert hasattr(EndpointAttributes, "ENDPOINT_NAME")
    assert hasattr(EndpointAttributes, "ENDPOINT_TYPE")
    assert hasattr(EndpointAttributes, "ENDPOINT_URL")
    assert hasattr(EndpointAttributes, "ENDPOINT_METHOD")
    assert hasattr(EndpointAttributes, "TEST_RUN_ID")
    assert hasattr(EndpointAttributes, "TEST_RESULT_ID")
    assert hasattr(EndpointAttributes, "TEST_ID")
    assert hasattr(EndpointAttributes, "TEST_CONFIGURATION_ID")

    # Verify semantic naming conventions
    assert EndpointAttributes.ENDPOINT_ID == "endpoint.id"
    assert EndpointAttributes.TEST_RUN_ID == "rhesis.test.run_id"
    assert EndpointAttributes.TEST_RESULT_ID == "rhesis.test.result_id"
    assert EndpointAttributes.TEST_ID == "rhesis.test.id"


def test_create_endpoint_attributes():
    """Test creating endpoint attributes."""
    # Create mock endpoint
    endpoint = MagicMock(spec=Endpoint)
    endpoint.id = uuid4()
    endpoint.name = "test-endpoint"
    endpoint.connection_type = "rest"
    endpoint.url = "https://api.example.com"
    endpoint.method = "POST"

    test_context = {
        "test_run_id": str(uuid4()),
        "test_result_id": str(uuid4()),
        "test_id": str(uuid4()),
        "test_configuration_id": str(uuid4()),
    }

    attrs = create_endpoint_attributes(endpoint, test_context)

    # Verify endpoint attributes
    assert attrs[EndpointAttributes.ENDPOINT_ID] == str(endpoint.id)
    assert attrs[EndpointAttributes.ENDPOINT_NAME] == "test-endpoint"
    assert attrs[EndpointAttributes.ENDPOINT_TYPE] == "rest"
    assert attrs[EndpointAttributes.ENDPOINT_URL] == "https://api.example.com"
    assert attrs[EndpointAttributes.ENDPOINT_METHOD] == "POST"

    # Verify test context attributes
    assert attrs[EndpointAttributes.TEST_RUN_ID] == test_context["test_run_id"]
    assert attrs[EndpointAttributes.TEST_RESULT_ID] == test_context["test_result_id"]
    assert attrs[EndpointAttributes.TEST_ID] == test_context["test_id"]
    assert attrs[EndpointAttributes.TEST_CONFIGURATION_ID] == test_context["test_configuration_id"]


def test_create_endpoint_attributes_with_extra_kwargs():
    """Test creating endpoint attributes with additional kwargs."""
    endpoint = MagicMock(spec=Endpoint)
    endpoint.id = uuid4()
    endpoint.name = "test-endpoint"
    endpoint.connection_type = "rest"
    endpoint.url = "https://api.example.com"

    test_context = {
        "test_run_id": str(uuid4()),
        "test_result_id": str(uuid4()),
        "test_id": str(uuid4()),
        "test_configuration_id": str(uuid4()),
    }

    attrs = create_endpoint_attributes(
        endpoint, test_context, custom_field="custom_value", another_field=123
    )

    # Verify extra kwargs are included
    assert attrs["custom_field"] == "custom_value"
    assert attrs["another_field"] == 123


@pytest.mark.asyncio
async def test_create_manual_invocation_trace_success():
    """Test manual trace creation for successful invocation."""
    # Setup mocks
    db_mock = MagicMock()
    endpoint = MagicMock(spec=Endpoint)
    endpoint.id = uuid4()
    endpoint.name = "test-endpoint"
    endpoint.connection_type = "rest"
    endpoint.url = "https://api.example.com"
    endpoint.project_id = uuid4()
    endpoint.environment = "development"

    test_context = {
        "test_run_id": str(uuid4()),
        "test_result_id": str(uuid4()),
        "test_id": str(uuid4()),
        "test_configuration_id": str(uuid4()),
    }

    org_id = str(uuid4())

    # Mock crud.create_trace_spans
    with patch(
        "rhesis.backend.app.services.invokers.manual_tracing.crud.create_trace_spans"
    ) as mock_create:
        async with create_manual_invocation_trace(
            db_mock, endpoint, test_context, org_id
        ) as trace_ctx:
            # Simulate successful invocation
            trace_ctx["result"] = {
                "status": "success",
                "output": "Test response",
            }

        # Verify crud.create_trace_spans was called
        assert mock_create.called
        call_args = mock_create.call_args
        assert call_args[0][0] == db_mock
        assert call_args[0][2] == org_id

        # Verify OTELSpan was created
        spans = call_args[0][1]
        assert len(spans) == 1
        span = spans[0]

        # Verify span properties
        assert span.span_kind == SpanKind.CLIENT
        assert span.status_code == StatusCode.OK
        assert span.project_id == str(endpoint.project_id)
        assert span.environment == "development"
        assert span.span_name == f"function.endpoint_{endpoint.connection_type}_invoke"

        # Verify test context in attributes
        assert span.attributes[EndpointAttributes.TEST_RUN_ID] == test_context["test_run_id"]
        assert span.attributes[EndpointAttributes.TEST_RESULT_ID] == test_context["test_result_id"]
        assert span.attributes[EndpointAttributes.TEST_ID] == test_context["test_id"]

        # Verify result metadata
        assert span.attributes[EndpointAttributes.RESPONSE_STATUS] == "success"
        assert span.attributes[EndpointAttributes.RESPONSE_HAS_OUTPUT] is True


@pytest.mark.asyncio
async def test_create_manual_invocation_trace_error():
    """Test manual trace creation for failed invocation."""
    db_mock = MagicMock()
    endpoint = MagicMock(spec=Endpoint)
    endpoint.id = uuid4()
    endpoint.name = "test-endpoint"
    endpoint.connection_type = "rest"
    endpoint.url = "https://api.example.com"
    endpoint.project_id = uuid4()
    endpoint.environment = "production"

    test_context = {
        "test_run_id": str(uuid4()),
        "test_result_id": str(uuid4()),
        "test_id": str(uuid4()),
        "test_configuration_id": str(uuid4()),
    }

    org_id = str(uuid4())

    with patch(
        "rhesis.backend.app.services.invokers.manual_tracing.crud.create_trace_spans"
    ) as mock_create:
        try:
            async with create_manual_invocation_trace(db_mock, endpoint, test_context, org_id) as _:
                # Simulate error during invocation
                raise ValueError("Test error")
        except ValueError:
            pass

        # Verify span was created with error status
        assert mock_create.called
        spans = mock_create.call_args[0][1]
        span = spans[0]

        assert span.status_code == StatusCode.ERROR
        assert "Test error" in span.status_message


@pytest.mark.asyncio
async def test_create_manual_invocation_trace_output_truncation():
    """Test that large outputs are truncated in trace attributes."""
    db_mock = MagicMock()
    endpoint = MagicMock(spec=Endpoint)
    endpoint.id = uuid4()
    endpoint.name = "test-endpoint"
    endpoint.connection_type = "rest"
    endpoint.url = "https://api.example.com"
    endpoint.project_id = uuid4()
    endpoint.environment = "development"

    test_context = {
        "test_run_id": str(uuid4()),
        "test_result_id": str(uuid4()),
        "test_id": str(uuid4()),
        "test_configuration_id": str(uuid4()),
    }

    org_id = str(uuid4())

    # Create a large output (> 1000 chars)
    large_output = "x" * 2000

    with patch(
        "rhesis.backend.app.services.invokers.manual_tracing.crud.create_trace_spans"
    ) as mock_create:
        async with create_manual_invocation_trace(
            db_mock, endpoint, test_context, org_id
        ) as trace_ctx:
            trace_ctx["result"] = {
                "status": "success",
                "output": large_output,
            }

        spans = mock_create.call_args[0][1]
        span = spans[0]

        # Verify output was truncated to 1000 chars
        output_preview = span.attributes[EndpointAttributes.RESPONSE_OUTPUT_PREVIEW]
        assert len(output_preview) == 1000
        assert output_preview == "x" * 1000

        # Verify size is recorded
        assert span.attributes[EndpointAttributes.RESPONSE_SIZE] == 2000


@pytest.mark.asyncio
async def test_create_manual_invocation_trace_span_name_format():
    """Test span name follows semantic conventions."""
    db_mock = MagicMock()

    for endpoint_type in ["rest", "websocket"]:
        endpoint = MagicMock(spec=Endpoint)
        endpoint.id = uuid4()
        endpoint.name = "test-endpoint"
        endpoint.connection_type = endpoint_type
        endpoint.url = "https://api.example.com"
        endpoint.project_id = uuid4()
        endpoint.environment = "development"

        test_context = {
            "test_run_id": str(uuid4()),
            "test_result_id": str(uuid4()),
            "test_id": str(uuid4()),
            "test_configuration_id": str(uuid4()),
        }

        with patch(
            "rhesis.backend.app.services.invokers.manual_tracing.crud.create_trace_spans"
        ) as mock_create:
            async with create_manual_invocation_trace(
                db_mock, endpoint, test_context, str(uuid4())
            ) as trace_ctx:
                trace_ctx["result"] = {"status": "success"}

            spans = mock_create.call_args[0][1]
            span = spans[0]

            # Verify span name follows function.* pattern
            expected_name = f"function.endpoint_{endpoint_type}_invoke"
            assert span.span_name == expected_name

            # Verify it matches OTELSpan validation regex (function.*)
            import re

            pattern = r"^(function|ai)\.[a-z0-9_\.]+$"
            assert re.match(pattern, span.span_name)
