"""Tests for SDK endpoint invoker."""

import asyncio
import inspect
from unittest.mock import patch
from uuid import uuid4

import pytest

from rhesis.backend.app.services.invokers.context import InvocationContext
from rhesis.backend.app.services.invokers.sdk_invoker import SDK_FUNCTION_TIMEOUT, SdkEndpointInvoker


class TestSdkEndpointInvoker:
    """Test SdkEndpointInvoker class functionality."""

    def test_automatic_tracing_property(self):
        """Test that SdkEndpointInvoker has automatic_tracing set to True."""
        invoker = SdkEndpointInvoker()

        assert hasattr(invoker, "automatic_tracing")
        assert invoker.automatic_tracing is True

    def test_invoke_signature_includes_test_execution_context(self):
        """Test that invoke method signature includes test_execution_context parameter."""
        invoker = SdkEndpointInvoker()

        # Get the method signature
        sig = inspect.signature(invoker.invoke)
        params = sig.parameters

        # Verify the parameter exists
        assert "test_execution_context" in params

        # Verify it's optional (has a default value)
        assert params["test_execution_context"].default is not inspect.Parameter.empty

    def test_prepare_function_kwargs_includes_test_context(self, sample_endpoint_sdk):
        """Test that _prepare_function_kwargs correctly includes test context when provided."""
        # Mock endpoint with request mapping
        sample_endpoint_sdk.request_mapping = '{"input": "{{ input }}"}'

        input_data = {"input": "test message"}
        function_name = "test_function"

        context = InvocationContext(db=None, endpoint=sample_endpoint_sdk, input_data=input_data)
        invoker = SdkEndpointInvoker(context)

        # Prepare kwargs without test context
        kwargs = invoker._prepare_function_kwargs(function_name)
        assert "_rhesis_test_context" not in kwargs

    def test_test_context_can_be_added_to_function_kwargs(self):
        """Test that test context can be added to function kwargs dictionary."""
        function_kwargs = {"input": "test"}

        test_execution_context = {
            "test_run_id": str(uuid4()),
            "test_result_id": str(uuid4()),
            "test_id": str(uuid4()),
            "test_configuration_id": str(uuid4()),
        }

        # Simulate adding test context (as done in invoke method)
        function_kwargs["_rhesis_test_context"] = test_execution_context

        # Verify it was added
        assert "_rhesis_test_context" in function_kwargs
        assert function_kwargs["_rhesis_test_context"] == test_execution_context
        assert function_kwargs["input"] == "test"  # Original data preserved

    def test_prepare_function_kwargs_renders_params_in_mapping(self, sample_endpoint_sdk):
        """{{ params.model }} in request_mapping renders from input_data['params']."""
        sample_endpoint_sdk.request_mapping = {
            "query": "{{ input }}",
            "model": "{{ params.model }}",
            "temperature": "{{ params.temperature }}",
        }

        input_data = {
            "input": "hello",
            "params": {"model": "gpt-4o", "temperature": 0.9},
        }

        context = InvocationContext(db=None, endpoint=sample_endpoint_sdk, input_data=input_data)
        invoker = SdkEndpointInvoker(context)
        kwargs = invoker._prepare_function_kwargs("test_func")

        assert kwargs["query"] == "hello"
        assert kwargs["model"] == "gpt-4o"
        assert kwargs["temperature"] == 0.9

    def test_prepare_function_kwargs_params_with_defaults(self, sample_endpoint_sdk):
        """Jinja default() filters work when params is empty."""
        sample_endpoint_sdk.request_mapping = {
            "query": "{{ input }}",
            "model": "{{ params.model | default('gpt-4') }}",
        }

        input_data = {"input": "hello", "params": {}}

        context = InvocationContext(db=None, endpoint=sample_endpoint_sdk, input_data=input_data)
        invoker = SdkEndpointInvoker(context)
        kwargs = invoker._prepare_function_kwargs("test_func")

        assert kwargs["query"] == "hello"
        assert kwargs["model"] == "gpt-4"

    def test_prepare_function_kwargs_strips_params_in_passthrough(self, sample_endpoint_sdk):
        """Without request_mapping, params dict is stripped from passthrough kwargs."""
        sample_endpoint_sdk.request_mapping = None

        input_data = {
            "input": "hello",
            "params": {"model": "gpt-4o"},
        }

        context = InvocationContext(db=None, endpoint=sample_endpoint_sdk, input_data=input_data)
        invoker = SdkEndpointInvoker(context)
        kwargs = invoker._prepare_function_kwargs("test_func")

        assert "params" not in kwargs
        assert kwargs["input"] == "hello"


class TestSdkEndpointInvokerLocalRegistry:
    """Local-registry invoke path: tracing opt-out and execution timeout."""

    @pytest.fixture
    def local_endpoint(self, sample_endpoint_sdk):
        sample_endpoint_sdk.endpoint_metadata = {
            "sdk_connection": {
                "function_name": "test_local_fn",
                "project_id": "test-project-id",
                "environment": "development",
            }
        }
        sample_endpoint_sdk.request_mapping = None
        sample_endpoint_sdk.response_mapping = None
        return sample_endpoint_sdk

    @pytest.mark.asyncio
    async def test_local_invoke_respects_disable_tracing(self, local_endpoint):
        observed = []

        async def test_local_fn(**kwargs):
            from rhesis.sdk.telemetry.context import is_tracing_disabled

            observed.append(is_tracing_disabled())
            return "ok"

        local_endpoint.disable_tracing = True
        registry = {"test_local_fn": test_local_fn}
        context = InvocationContext(db=None, endpoint=local_endpoint, input_data={"input": "hi"})
        invoker = SdkEndpointInvoker(context)

        with (
            patch(
                "rhesis.backend.app.services.local_function_registry.ensure_local_functions_registered"
            ),
            patch("rhesis.backend.app.services.local_function_registry.registry", registry),
        ):
            result = await invoker.invoke()

        assert observed == [True]
        assert result["output"] == "ok"

    @pytest.mark.asyncio
    async def test_local_invoke_strips_injected_rhesis_keys(self, local_endpoint):
        received = {}

        async def test_local_fn(**kwargs):
            received.update(kwargs)
            return "ok"

        local_endpoint.disable_tracing = False
        registry = {"test_local_fn": test_local_fn}
        context = InvocationContext(
            db=None,
            endpoint=local_endpoint,
            input_data={"input": "hi", "_rhesis_disable_tracing": True},
        )
        invoker = SdkEndpointInvoker(context)

        with (
            patch(
                "rhesis.backend.app.services.local_function_registry.ensure_local_functions_registered"
            ),
            patch("rhesis.backend.app.services.local_function_registry.registry", registry),
        ):
            await invoker.invoke()

        assert "_rhesis_disable_tracing" not in received

    @pytest.mark.asyncio
    async def test_local_invoke_times_out(self, local_endpoint, monkeypatch):
        async def slow_fn(**kwargs):
            await asyncio.sleep(SDK_FUNCTION_TIMEOUT + 5)
            return "ok"

        monkeypatch.setattr(
            "rhesis.backend.app.services.invokers.sdk_invoker.SDK_FUNCTION_TIMEOUT",
            0.05,
        )
        registry = {"test_local_fn": slow_fn}
        context = InvocationContext(db=None, endpoint=local_endpoint, input_data={"input": "hi"})
        invoker = SdkEndpointInvoker(context)

        with (
            patch(
                "rhesis.backend.app.services.local_function_registry.ensure_local_functions_registered"
            ),
            patch("rhesis.backend.app.services.local_function_registry.registry", registry),
        ):
            result = await invoker.invoke()

        assert result.error_type == "sdk_timeout"
