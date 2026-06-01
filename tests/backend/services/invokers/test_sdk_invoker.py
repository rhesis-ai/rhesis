"""Tests for SDK endpoint invoker."""

import inspect
from uuid import uuid4

from rhesis.backend.app.services.invokers.context import InvocationContext
from rhesis.backend.app.services.invokers.sdk_invoker import SdkEndpointInvoker


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

        sig = inspect.signature(invoker.invoke)
        params = sig.parameters

        assert "test_execution_context" in params
        assert params["test_execution_context"].default is not inspect.Parameter.empty

    def test_prepare_function_kwargs_includes_test_context(self, sample_endpoint_sdk):
        """Test that _prepare_function_kwargs correctly includes test context when provided."""
        sample_endpoint_sdk.request_mapping = '{"input": "{{ input }}"}'

        input_data = {"input": "test message"}
        function_name = "test_function"

        context = InvocationContext(db=None, endpoint=sample_endpoint_sdk, input_data=input_data)
        invoker = SdkEndpointInvoker(context)

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

        function_kwargs["_rhesis_test_context"] = test_execution_context

        assert "_rhesis_test_context" in function_kwargs
        assert function_kwargs["_rhesis_test_context"] == test_execution_context
        assert function_kwargs["input"] == "test"

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
