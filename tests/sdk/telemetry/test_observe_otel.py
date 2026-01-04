"""OpenTelemetry integration tests for @observe decorator."""

from unittest.mock import MagicMock, patch

import pytest

from rhesis.sdk import decorators
from rhesis.sdk.decorators import observe
from rhesis.sdk.telemetry.schemas import AIOperationType


class TestObserveWithOTEL:
    """Integration tests for @observe decorator with OpenTelemetry."""

    def test_observe_raises_error_without_client_initialization(self):
        """Test @observe raises RuntimeError when RhesisClient not initialized."""
        # Save current client state and clear it
        original_client = decorators._default_client
        decorators._default_client = None

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
            decorators._default_client = original_client

    @patch("rhesis.sdk.decorators._default_client", MagicMock())
    @patch("rhesis.sdk.decorators.trace.get_tracer")
    def test_observe_creates_span_with_default_name(self, mock_get_tracer):
        """Test @observe creates OTEL span with default function name."""
        # Setup mock tracer
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_tracer.return_value = mock_tracer

        # Define function with @observe
        @observe()
        def helper_function(x: int) -> int:
            return x * 2

        # Execute function
        result = helper_function(5)

        assert result == 10
        # Verify span was created with default function.* name
        mock_tracer.start_as_current_span.assert_called_once()
        call_args = mock_tracer.start_as_current_span.call_args
        assert call_args[1]["name"] == "function.helper_function"

    @patch("rhesis.sdk.decorators._default_client", MagicMock())
    @patch("rhesis.sdk.decorators.trace.get_tracer")
    def test_observe_with_custom_span_name(self, mock_get_tracer):
        """Test @observe with custom span name."""
        # Setup mock tracer
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_tracer.return_value = mock_tracer

        # Define function with custom span name
        @observe(span_name="ai.llm.invoke")
        def call_llm(prompt: str) -> str:
            return f"Response to: {prompt}"

        # Execute function
        result = call_llm("test")

        assert result == "Response to: test"
        # Verify custom span name was used
        call_args = mock_tracer.start_as_current_span.call_args
        assert call_args[1]["name"] == "ai.llm.invoke"

    @patch("rhesis.sdk.decorators._default_client", MagicMock())
    @patch("rhesis.sdk.decorators.trace.get_tracer")
    def test_observe_with_constant_span_name(self, mock_get_tracer):
        """Test @observe with AIOperationType constant."""
        # Setup mock tracer
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_tracer.return_value = mock_tracer

        # Define function with constant span name
        @observe(span_name=AIOperationType.TOOL_INVOKE)
        def execute_tool(input_str: str) -> dict:
            return {"result": input_str.upper()}

        # Execute function
        result = execute_tool("test")

        assert result == {"result": "TEST"}
        # Verify constant value was used
        call_args = mock_tracer.start_as_current_span.call_args
        assert call_args[1]["name"] == "ai.tool.invoke"

    @patch("rhesis.sdk.decorators._default_client", MagicMock())
    @patch("rhesis.sdk.decorators.trace.get_tracer")
    def test_observe_sets_custom_attributes(self, mock_get_tracer):
        """Test @observe sets custom attributes on span."""
        # Setup mock tracer
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_tracer.return_value = mock_tracer

        # Define function with custom attributes
        @observe(model="gpt-4", temperature=0.7, max_tokens=150)
        def llm_call(prompt: str) -> str:
            return "response"

        # Execute function
        result = llm_call("test")

        assert result == "response"
        # Verify attributes were set
        mock_span.set_attribute.assert_any_call("function.name", "llm_call")
        mock_span.set_attribute.assert_any_call("model", "gpt-4")
        mock_span.set_attribute.assert_any_call("temperature", 0.7)
        mock_span.set_attribute.assert_any_call("max_tokens", 150)

    @patch("rhesis.sdk.decorators._default_client", MagicMock())
    @patch("rhesis.sdk.decorators.trace.get_tracer")
    def test_observe_records_exception(self, mock_get_tracer):
        """Test @observe records exceptions to span."""
        # Setup mock tracer
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_tracer.return_value = mock_tracer

        # Define function that raises exception
        @observe()
        def failing_function():
            raise ValueError("Test error")

        # Execute and verify exception is raised
        with pytest.raises(ValueError, match="Test error"):
            failing_function()

        # Verify exception was recorded
        mock_span.record_exception.assert_called_once()
        mock_span.set_status.assert_called_once()

    @patch("rhesis.sdk.decorators._default_client", MagicMock())
    @patch("rhesis.sdk.decorators.trace.get_tracer")
    def test_observe_sets_success_status(self, mock_get_tracer):
        """Test @observe sets OK status on success."""
        # Setup mock tracer
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_tracer.return_value = mock_tracer

        # Define successful function
        @observe()
        def successful_function(x: int) -> int:
            return x * 2

        # Execute function
        result = successful_function(10)

        assert result == 20
        # Verify OK status was set
        mock_span.set_status.assert_called_once()
        status_call = mock_span.set_status.call_args[0][0]
        assert status_call.status_code.name == "OK"

    def test_observe_preserves_function_metadata(self):
        """Test @observe preserves function name and docstring."""

        @observe()
        def my_helper(x: int) -> int:
            """This is my helper function."""
            return x + 1

        # Check metadata preserved
        assert my_helper.__name__ == "my_helper"
        assert my_helper.__doc__ == "This is my helper function."

    @patch("rhesis.sdk.decorators._default_client", MagicMock())
    @patch("rhesis.sdk.decorators.trace.get_tracer")
    def test_observe_with_custom_name_parameter(self, mock_get_tracer):
        """Test @observe with name parameter sets attribute."""
        # Setup mock tracer
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_tracer.return_value = mock_tracer

        # Define function with custom name
        @observe(name="custom_operation")
        def internal_func(x: int) -> int:
            return x * 2

        # Execute function
        result = internal_func(5)

        assert result == 10
        # Verify custom name was set as attribute
        mock_span.set_attribute.assert_any_call("function.name", "custom_operation")
