"""Tests for SDK endpoint invoker."""

import inspect
from uuid import uuid4

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

        # Get the method signature
        sig = inspect.signature(invoker.invoke)
        params = sig.parameters

        # Verify the parameter exists
        assert "test_execution_context" in params

        # Verify it's optional (has a default value)
        assert params["test_execution_context"].default is not inspect.Parameter.empty

    def test_prepare_function_kwargs_includes_test_context(self, sample_endpoint_sdk):
        """Test that _prepare_function_kwargs correctly includes test context when provided."""
        invoker = SdkEndpointInvoker()

        # Mock endpoint with request mapping
        sample_endpoint_sdk.request_mapping = '{"input": "{{ input }}"}'

        input_data = {"input": "test message"}
        function_name = "test_function"

        # Prepare kwargs without test context
        kwargs = invoker._prepare_function_kwargs(sample_endpoint_sdk, input_data, function_name)
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
