"""Tests for telemetry Tracer class."""

from unittest.mock import MagicMock, patch

import pytest

from rhesis.sdk.telemetry.attributes import AIAttributes
from rhesis.sdk.telemetry.tracer import Tracer


class TestTracer:
    """Tests for Tracer class."""

    @patch("rhesis.sdk.telemetry.tracer.get_tracer_provider")
    def test_tracer_initialization(self, mock_get_provider):
        """Test Tracer initialization."""
        mock_provider = MagicMock()
        mock_provider.get_tracer.return_value = MagicMock()
        mock_get_provider.return_value = mock_provider

        tracer = Tracer(
            api_key="test-key",
            project_id="test-project",
            environment="test",
            base_url="http://localhost:8080",
        )

        assert tracer.api_key == "test-key"
        assert tracer.project_id == "test-project"
        assert tracer.environment == "test"
        assert tracer.tracer is not None

        mock_get_provider.assert_called_once_with(
            service_name="rhesis-sdk",
            api_key="test-key",
            base_url="http://localhost:8080",
            project_id="test-project",
            environment="test",
        )

    @patch("rhesis.sdk.telemetry.tracer.get_tracer_provider")
    def test_trace_execution_default_span_name(self, mock_get_provider):
        """Test trace_execution with default span name."""
        mock_provider = MagicMock()
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_provider.get_tracer.return_value = mock_tracer
        mock_get_provider.return_value = mock_provider

        tracer = Tracer(
            api_key="test-key",
            project_id="test-project",
            environment="test",
            base_url="http://localhost:8080",
        )

        def test_func():
            return "result"

        result = tracer.trace_execution("test_func", test_func, (), {})

        assert result == "result"
        mock_tracer.start_as_current_span.assert_called_once()
        call_args = mock_tracer.start_as_current_span.call_args
        assert call_args[1]["name"] == "function.test_func"

    @patch("rhesis.sdk.telemetry.tracer.get_tracer_provider")
    def test_trace_execution_custom_span_name(self, mock_get_provider):
        """Test trace_execution with custom span name."""
        mock_provider = MagicMock()
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_provider.get_tracer.return_value = mock_tracer
        mock_get_provider.return_value = mock_provider

        tracer = Tracer(
            api_key="test-key",
            project_id="test-project",
            environment="test",
            base_url="http://localhost:8080",
        )

        def test_func():
            return "result"

        result = tracer.trace_execution("test_func", test_func, (), {}, span_name="ai.llm.invoke")

        assert result == "result"
        call_args = mock_tracer.start_as_current_span.call_args
        assert call_args[1]["name"] == "ai.llm.invoke"

    @patch("rhesis.sdk.telemetry.tracer.get_tracer_provider")
    def test_trace_execution_with_error(self, mock_get_provider):
        """Test trace_execution records exceptions."""
        mock_provider = MagicMock()
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_provider.get_tracer.return_value = mock_tracer
        mock_get_provider.return_value = mock_provider

        tracer = Tracer(
            api_key="test-key",
            project_id="test-project",
            environment="test",
            base_url="http://localhost:8080",
        )

        def failing_func():
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            tracer.trace_execution("failing_func", failing_func, (), {})

        # Verify error was recorded on span
        mock_span.record_exception.assert_called_once()
        mock_span.set_status.assert_called()

    @patch("rhesis.sdk.telemetry.tracer.get_tracer_provider")
    def test_trace_execution_with_args_kwargs(self, mock_get_provider):
        """Test trace_execution with args and kwargs."""
        mock_provider = MagicMock()
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_provider.get_tracer.return_value = mock_tracer
        mock_get_provider.return_value = mock_provider

        tracer = Tracer(
            api_key="test-key",
            project_id="test-project",
            environment="test",
            base_url="http://localhost:8080",
        )

        def test_func(a, b, c=None):
            return f"{a}-{b}-{c}"

        result = tracer.trace_execution("test_func", test_func, (1, 2), {"c": 3})

        assert result == "1-2-3"
        mock_span.set_attribute.assert_any_call("function.args_count", 2)
        mock_span.set_attribute.assert_any_call("function.kwargs_count", 1)

    @patch("rhesis.sdk.telemetry.tracer.get_tracer_provider")
    def test_trace_execution_generator(self, mock_get_provider):
        """Test trace_execution with generator function."""
        mock_provider = MagicMock()
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_provider.get_tracer.return_value = mock_tracer
        mock_get_provider.return_value = mock_provider

        tracer = Tracer(
            api_key="test-key",
            project_id="test-project",
            environment="test",
            base_url="http://localhost:8080",
        )

        def generator_func():
            yield 1
            yield 2
            yield 3

        result = tracer.trace_execution("generator_func", generator_func, (), {})

        # Result should be a generator
        items = list(result)
        assert items == [1, 2, 3]

        # Span should have recorded output chunks
        mock_span.set_attribute.assert_any_call("function.output_chunks", 3)

    @patch("rhesis.sdk.telemetry.tracer.get_tracer_provider")
    def test_trace_execution_generator_with_error(self, mock_get_provider):
        """Test trace_execution with generator that raises error."""
        mock_provider = MagicMock()
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_provider.get_tracer.return_value = mock_tracer
        mock_get_provider.return_value = mock_provider

        tracer = Tracer(
            api_key="test-key",
            project_id="test-project",
            environment="test",
            base_url="http://localhost:8080",
        )

        def failing_generator():
            yield 1
            raise ValueError("Generator error")

        result = tracer.trace_execution("failing_generator", failing_generator, (), {})

        # Consume generator until error
        with pytest.raises(ValueError, match="Generator error"):
            list(result)

        # Span should have recorded the error
        mock_span.record_exception.assert_called()

    @patch("rhesis.sdk.telemetry.tracer.get_tracer_provider")
    def test_trace_execution_captures_inputs_and_outputs(self, mock_get_provider):
        """Test trace_execution captures function inputs and outputs."""
        mock_provider = MagicMock()
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_provider.get_tracer.return_value = mock_tracer
        mock_get_provider.return_value = mock_provider

        tracer = Tracer(
            api_key="test-key",
            project_id="test-project",
            environment="test",
            base_url="http://localhost:8080",
        )

        def test_func(x, y, multiplier=2):
            return (x + y) * multiplier

        result = tracer.trace_execution("test_func", test_func, (5, 3), {"multiplier": 10})

        assert result == 80

        # Verify inputs were captured
        import json

        # Check args captured
        args_calls = [
            call
            for call in mock_span.set_attribute.call_args_list
            if call[0][0] == AIAttributes.FUNCTION_ARGS
        ]
        assert len(args_calls) == 1
        captured_args = json.loads(args_calls[0][0][1])
        assert captured_args == [5, 3]

        # Check kwargs captured (without _rhesis_* fields)
        kwargs_calls = [
            call
            for call in mock_span.set_attribute.call_args_list
            if call[0][0] == AIAttributes.FUNCTION_KWARGS
        ]
        assert len(kwargs_calls) == 1
        captured_kwargs = json.loads(kwargs_calls[0][0][1])
        assert captured_kwargs == {"multiplier": 10}

        # Check result captured
        result_calls = [
            call
            for call in mock_span.set_attribute.call_args_list
            if call[0][0] == AIAttributes.FUNCTION_RESULT
        ]
        assert len(result_calls) == 1
        assert result_calls[0][0][1] == "80"

    @patch("rhesis.sdk.telemetry.tracer.get_tracer_provider")
    def test_trace_execution_filters_internal_kwargs(self, mock_get_provider):
        """Test trace_execution filters _rhesis_* internal fields from kwargs."""
        mock_provider = MagicMock()
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_provider.get_tracer.return_value = mock_tracer
        mock_get_provider.return_value = mock_provider

        tracer = Tracer(
            api_key="test-key",
            project_id="test-project",
            environment="test",
            base_url="http://localhost:8080",
        )

        def test_func(x, **kwargs):
            return x

        # Include internal field that should be filtered
        result = tracer.trace_execution(
            "test_func", test_func, (42,), {"public_param": "value", "_rhesis_internal": "secret"}
        )

        assert result == 42

        # Check that kwargs were captured without internal fields
        import json

        kwargs_calls = [
            call
            for call in mock_span.set_attribute.call_args_list
            if call[0][0] == AIAttributes.FUNCTION_KWARGS
        ]
        assert len(kwargs_calls) == 1
        captured_kwargs = json.loads(kwargs_calls[0][0][1])
        assert captured_kwargs == {"public_param": "value"}
        assert "_rhesis_internal" not in captured_kwargs

    @patch("rhesis.sdk.telemetry.tracer.get_tracer_provider")
    def test_trace_execution_truncates_large_inputs(self, mock_get_provider):
        """Test trace_execution truncates large inputs and outputs."""
        mock_provider = MagicMock()
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_provider.get_tracer.return_value = mock_tracer
        mock_get_provider.return_value = mock_provider

        tracer = Tracer(
            api_key="test-key",
            project_id="test-project",
            environment="test",
            base_url="http://localhost:8080",
        )

        # Create large string that will be truncated
        large_string = "x" * 3000

        def test_func(data):
            return data

        result = tracer.trace_execution("test_func", test_func, (large_string,), {})

        assert result == large_string

        # Check that args were truncated
        args_calls = [
            call
            for call in mock_span.set_attribute.call_args_list
            if call[0][0] == AIAttributes.FUNCTION_ARGS
        ]
        assert len(args_calls) == 1
        captured_args_str = args_calls[0][0][1]
        assert len(captured_args_str) <= 2020  # 2000 + "[truncated]"
        assert "[truncated]" in captured_args_str

    @patch("rhesis.sdk.telemetry.tracer.get_tracer_provider")
    def test_serialize_arg_for_trace_with_instance_method(self, mock_get_provider):
        """Test smart serialization of instance methods with self parameter."""
        mock_provider = MagicMock()
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_provider.get_tracer.return_value = mock_tracer
        mock_get_provider.return_value = mock_provider

        tracer = Tracer(
            api_key="test-key",
            project_id="test-project",
            environment="test",
            base_url="http://localhost:8080",
        )

        # Create a test class with public attributes
        class TestService:
            def __init__(self, name, config):
                self.name = name
                self.config = config
                self._internal = "should not appear"

            def process(self, data):
                return f"Processed: {data}"

        service = TestService(name="test-service", config="production")

        # When tracing a bound method, self is already included
        # We need to use __func__ to get the unbound function and pass self explicitly
        result = tracer.trace_execution(
            "process", service.process.__func__, (service, "test data"), {}
        )

        assert result == "Processed: test data"

        # Verify self was serialized intelligently
        import json

        args_calls = [
            call
            for call in mock_span.set_attribute.call_args_list
            if call[0][0] == AIAttributes.FUNCTION_ARGS
        ]
        assert len(args_calls) == 1
        captured_args = json.loads(args_calls[0][0][1])

        # First arg should be the self object with class and attributes
        assert len(captured_args) == 2
        assert isinstance(captured_args[0], dict)
        # The class name will include the full qualified name for nested classes
        assert "_class" in captured_args[0]
        assert "TestService" in captured_args[0]["_class"]
        assert "_attributes" in captured_args[0]
        assert captured_args[0]["_attributes"]["name"] == "test-service"
        assert captured_args[0]["_attributes"]["config"] == "production"
        # Internal attributes (starting with _) should not be included
        assert "_internal" not in captured_args[0]["_attributes"]

        # Second arg should be the data string
        assert captured_args[1] == "test data"

    @patch("rhesis.sdk.telemetry.tracer.get_tracer_provider")
    def test_serialize_arg_with_custom_repr(self, mock_get_provider):
        """Test that custom __repr__ is used when available."""
        mock_provider = MagicMock()
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_provider.get_tracer.return_value = mock_tracer
        mock_get_provider.return_value = mock_provider

        tracer = Tracer(
            api_key="test-key",
            project_id="test-project",
            environment="test",
            base_url="http://localhost:8080",
        )

        # Create a class with custom __repr__
        class CustomReprService:
            def __init__(self, use_case):
                self.use_case = use_case

            def __repr__(self):
                return f"CustomReprService(use_case='{self.use_case}')"

            def process(self, data):
                return data

        service = CustomReprService(use_case="insurance")
        # Use __func__ to get unbound function and pass self explicitly
        tracer.trace_execution("process", service.process.__func__, (service, "input"), {})

        # Verify custom __repr__ was used
        import json

        args_calls = [
            call
            for call in mock_span.set_attribute.call_args_list
            if call[0][0] == AIAttributes.FUNCTION_ARGS
        ]
        assert len(args_calls) == 1
        captured_args = json.loads(args_calls[0][0][1])

        # First arg should be the custom repr string
        assert captured_args[0] == "CustomReprService(use_case='insurance')"
        assert captured_args[1] == "input"

    @patch("rhesis.sdk.telemetry.tracer.get_tracer_provider")
    def test_serialize_arg_handles_collections(self, mock_get_provider):
        """Test serialization of lists and dicts in arguments."""
        mock_provider = MagicMock()
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_provider.get_tracer.return_value = mock_tracer
        mock_get_provider.return_value = mock_provider

        tracer = Tracer(
            api_key="test-key",
            project_id="test-project",
            environment="test",
            base_url="http://localhost:8080",
        )

        def test_func(items, config):
            return len(items)

        # Test with list and dict
        items = [1, 2, 3, "test"]
        config = {"timeout": 30, "retry": True}

        tracer.trace_execution("test_func", test_func, (items, config), {})

        # Verify collections were serialized correctly
        import json

        args_calls = [
            call
            for call in mock_span.set_attribute.call_args_list
            if call[0][0] == AIAttributes.FUNCTION_ARGS
        ]
        assert len(args_calls) == 1
        captured_args = json.loads(args_calls[0][0][1])

        # Collections should be preserved
        assert captured_args[0] == [1, 2, 3, "test"]
        assert captured_args[1] == {"timeout": 30, "retry": True}

    @patch("rhesis.sdk.telemetry.tracer.get_tracer_provider")
    def test_serialize_arg_limits_collection_size(self, mock_get_provider):
        """Test that large collections are truncated."""
        mock_provider = MagicMock()
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_provider.get_tracer.return_value = mock_tracer
        mock_get_provider.return_value = mock_provider

        tracer = Tracer(
            api_key="test-key",
            project_id="test-project",
            environment="test",
            base_url="http://localhost:8080",
        )

        def test_func(items):
            return len(items)

        # Test with large list (more than 10 items)
        large_list = list(range(20))

        tracer.trace_execution("test_func", test_func, (large_list,), {})

        # Verify collections were truncated
        import json

        args_calls = [
            call
            for call in mock_span.set_attribute.call_args_list
            if call[0][0] == AIAttributes.FUNCTION_ARGS
        ]
        assert len(args_calls) == 1
        captured_args = json.loads(args_calls[0][0][1])

        # Should only have first 10 items plus truncation message
        assert len(captured_args[0]) == 11  # 10 items + truncation message
        assert captured_args[0][:10] == list(range(10))
        assert "more items" in captured_args[0][10]

    @patch("rhesis.sdk.telemetry.tracer.get_tracer_provider")
    def test_output_serialization_consistent_with_input(self, mock_get_provider):
        """Test that outputs are serialized consistently with inputs (as JSON)."""
        mock_provider = MagicMock()
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_provider.get_tracer.return_value = mock_tracer
        mock_get_provider.return_value = mock_provider

        tracer = Tracer(
            api_key="test-key",
            project_id="test-project",
            environment="test",
            base_url="http://localhost:8080",
        )

        def test_func(data):
            # Return a dict (common for API responses)
            return {"intent": "informational", "confidence": "low"}

        tracer.trace_execution("test_func", test_func, ("test input",), {})

        # Verify output is JSON serialized
        import json

        result_calls = [
            call
            for call in mock_span.set_attribute.call_args_list
            if call[0][0] == AIAttributes.FUNCTION_RESULT
        ]
        assert len(result_calls) == 1

        # The result should be a valid JSON string that can be parsed
        result_str = result_calls[0][0][1]
        parsed_result = json.loads(result_str)

        # Verify it matches the original dict
        assert parsed_result == {"intent": "informational", "confidence": "low"}

        # Verify it's formatted like inputs (with JSON.dumps)
        # Not like the old format: str(dict) = "{'intent': 'informational', 'confidence': 'low'}"
        assert result_str == '{"intent": "informational", "confidence": "low"}'
