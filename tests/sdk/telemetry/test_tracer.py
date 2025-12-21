"""Tests for telemetry Tracer class."""

from unittest.mock import MagicMock, patch

import pytest

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
