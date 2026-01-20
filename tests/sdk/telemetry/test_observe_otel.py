"""OpenTelemetry integration tests for @observe decorator."""

from unittest.mock import MagicMock

import pytest

from rhesis.sdk.decorators import _state as decorators_state
from rhesis.sdk.decorators import observe
from rhesis.sdk.telemetry.schemas import AIOperationType


@pytest.fixture
def mock_client_with_tracer():
    """Create a mock client that executes functions properly."""
    mock_client = MagicMock()

    # Mock tracer that executes functions (side effect calls the actual function)
    mock_tracer = MagicMock()
    mock_tracer.trace_execution = MagicMock(
        side_effect=lambda fn, f, a, k, sn=None, ea=None: f(*a, **k)
    )

    # For exception testing, we need the side effect to propagate exceptions
    def trace_with_exception(fn, f, a, k, sn=None, ea=None):
        return f(*a, **k)

    mock_tracer.trace_execution_async = MagicMock(
        side_effect=lambda fn, f, a, k, sn=None, ea=None: f(*a, **k)
    )

    mock_client._tracer = mock_tracer

    return mock_client


class TestObserveWithOTEL:
    """Integration tests for @observe decorator with OpenTelemetry."""

    def test_observe_raises_error_without_client_initialization(self):
        """Test @observe raises RuntimeError when RhesisClient not initialized."""
        # Save current client state and clear it
        original_client = decorators_state._default_client
        decorators_state._default_client = None

        try:
            # Define function with @observe (should succeed - decorator applied)
            @observe()
            def uninit_function(x: int) -> int:
                return x * 2

            # Execute function - should raise RuntimeError
            with pytest.raises(
                RuntimeError, match="RhesisClient not initialized. Create a RhesisClient instance"
            ):
                uninit_function(5)
        finally:
            # Restore original client state
            decorators_state._default_client = original_client

    def test_observe_creates_span_with_default_name(self, mock_client_with_tracer):
        """Test @observe creates OTEL span with default function name."""
        decorators_state._default_client = mock_client_with_tracer

        @observe()
        def helper_function(x: int) -> int:
            return x * 2

        result = helper_function(5)
        assert result == 10

        # Verify trace_execution was called with correct span_name
        mock_client_with_tracer._tracer.trace_execution.assert_called_once()
        call_args = mock_client_with_tracer._tracer.trace_execution.call_args
        assert call_args[0][4] == "function.helper_function"  # span_name

        decorators_state._default_client = None

    def test_observe_with_custom_span_name(self, mock_client_with_tracer):
        """Test @observe with custom span name."""
        decorators_state._default_client = mock_client_with_tracer

        @observe(span_name="ai.llm.invoke")
        def call_llm(prompt: str) -> str:
            return f"Response to: {prompt}"

        result = call_llm("test")
        assert result == "Response to: test"

        # Verify custom span name was used
        call_args = mock_client_with_tracer._tracer.trace_execution.call_args
        assert call_args[0][4] == "ai.llm.invoke"  # span_name

        decorators_state._default_client = None

    def test_observe_with_constant_span_name(self, mock_client_with_tracer):
        """Test @observe with AIOperationType constant."""
        decorators_state._default_client = mock_client_with_tracer

        @observe(span_name=AIOperationType.TOOL_INVOKE)
        def execute_tool(input_str: str) -> dict:
            return {"result": input_str.upper()}

        result = execute_tool("test")
        assert result == {"result": "TEST"}

        # Verify constant value was used
        call_args = mock_client_with_tracer._tracer.trace_execution.call_args
        assert call_args[0][4] == "ai.tool.invoke"  # span_name

        decorators_state._default_client = None

    def test_observe_sets_custom_attributes(self, mock_client_with_tracer):
        """Test @observe sets custom attributes on span."""
        decorators_state._default_client = mock_client_with_tracer

        @observe(model="gpt-4", temperature=0.7, max_tokens=150)
        def llm_call(prompt: str) -> str:
            return "response"

        result = llm_call("test")
        assert result == "response"

        # Verify extra attributes were passed
        call_args = mock_client_with_tracer._tracer.trace_execution.call_args
        extra_attrs = call_args[0][5]  # extra_attributes
        assert extra_attrs == {"model": "gpt-4", "temperature": 0.7, "max_tokens": 150}

        decorators_state._default_client = None

    def test_observe_records_exception(self, mock_client_with_tracer):
        """Test @observe records exceptions to span."""
        decorators_state._default_client = mock_client_with_tracer

        @observe()
        def failing_function():
            raise ValueError("Test error")

        # Execute and verify exception is raised
        with pytest.raises(ValueError, match="Test error"):
            failing_function()

        decorators_state._default_client = None

    def test_observe_sets_success_status(self, mock_client_with_tracer):
        """Test @observe sets OK status on success."""
        decorators_state._default_client = mock_client_with_tracer

        @observe()
        def successful_function(x: int) -> int:
            return x * 2

        result = successful_function(10)
        assert result == 20

        # Function executed successfully
        mock_client_with_tracer._tracer.trace_execution.assert_called_once()

        decorators_state._default_client = None

    def test_observe_preserves_function_metadata(self):
        """Test @observe preserves function name and docstring."""

        @observe()
        def my_helper(x: int) -> int:
            """This is my helper function."""
            return x + 1

        # Check metadata preserved
        assert my_helper.__name__ == "my_helper"
        assert my_helper.__doc__ == "This is my helper function."

    def test_observe_with_custom_name_parameter(self, mock_client_with_tracer):
        """Test @observe with name parameter sets attribute."""
        decorators_state._default_client = mock_client_with_tracer

        @observe(name="custom_operation")
        def internal_func(x: int) -> int:
            return x * 2

        result = internal_func(5)
        assert result == 10

        # Verify custom name was used as function_name
        call_args = mock_client_with_tracer._tracer.trace_execution.call_args
        assert call_args[0][0] == "custom_operation"  # function_name

        decorators_state._default_client = None
