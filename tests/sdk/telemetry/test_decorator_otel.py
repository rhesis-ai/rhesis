"""End-to-end tests for @endpoint with OTEL integration."""

from unittest.mock import MagicMock, patch

import pytest

from rhesis.sdk import RhesisClient
from rhesis.sdk.decorators import endpoint


@patch("rhesis.sdk.connector.manager.asyncio.create_task")
class TestEndpointWithOTEL:
    """End-to-end tests for @endpoint decorator with OpenTelemetry."""

    @patch("rhesis.sdk.telemetry.tracer.get_tracer_provider")
    def test_endpoint_uses_telemetry_default_span_name(self, mock_get_provider, mock_create_task):
        """Test @endpoint uses telemetry with default span name."""
        # Setup mock provider
        mock_provider = MagicMock()
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_provider.get_tracer.return_value = mock_tracer
        mock_get_provider.return_value = mock_provider

        # Create client (registers as default)
        _client = RhesisClient(
            api_key="test-key",
            project_id="test-project",
            environment="development",
        )

        # Define function with @endpoint
        @endpoint()
        def process_data(x: int, y: int) -> int:
            return x + y

        # Execute function
        result = process_data(5, 10)

        assert result == 15
        # Verify span was created with default function.* name
        mock_tracer.start_as_current_span.assert_called_once()
        call_args = mock_tracer.start_as_current_span.call_args
        assert call_args[1]["name"] == "function.process_data"

    @patch("rhesis.sdk.telemetry.tracer.get_tracer_provider")
    def test_endpoint_with_custom_span_name(self, mock_get_provider, mock_create_task):
        """Test @endpoint with custom span name."""
        # Setup mock provider
        mock_provider = MagicMock()
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_provider.get_tracer.return_value = mock_tracer
        mock_get_provider.return_value = mock_provider

        # Create client (registers as default)
        _client = RhesisClient(
            api_key="test-key",
            project_id="test-project",
            environment="development",
        )

        # Define function with custom span name
        @endpoint(span_name="ai.llm.invoke")
        def call_llm(prompt: str) -> str:
            return f"response to {prompt}"

        # Execute function
        result = call_llm("test prompt")

        assert result == "response to test prompt"
        # Verify span was created with custom ai.* name
        call_args = mock_tracer.start_as_current_span.call_args
        assert call_args[1]["name"] == "ai.llm.invoke"

    @patch("rhesis.sdk.telemetry.tracer.get_tracer_provider")
    def test_endpoint_with_tool_span_name(self, mock_get_provider, mock_create_task):
        """Test @endpoint with tool operation span name."""
        # Setup mock provider
        mock_provider = MagicMock()
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_provider.get_tracer.return_value = mock_tracer
        mock_get_provider.return_value = mock_provider

        # Create client (registers as default)
        _client = RhesisClient(
            api_key="test-key",
            project_id="test-project",
            environment="development",
        )

        # Define tool function
        @endpoint(span_name="ai.tool.invoke")
        def weather_api(city: str) -> dict:
            return {"city": city, "temp": 72}

        # Execute function
        result = weather_api("San Francisco")

        assert result["city"] == "San Francisco"
        call_args = mock_tracer.start_as_current_span.call_args
        assert call_args[1]["name"] == "ai.tool.invoke"

    @patch("rhesis.sdk.telemetry.tracer.get_tracer_provider")
    def test_endpoint_records_function_attributes(self, mock_get_provider, mock_create_task):
        """Test @endpoint records function metadata as span attributes."""
        # Setup mock provider
        mock_provider = MagicMock()
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_provider.get_tracer.return_value = mock_tracer
        mock_get_provider.return_value = mock_provider

        # Create client (registers as default)
        _client = RhesisClient(
            api_key="test-key",
            project_id="test-project",
            environment="development",
        )

        @endpoint()
        def test_func(a: int, b: int = 5) -> int:
            return a + b

        # Execute with args and kwargs
        _result = test_func(10, b=20)

        # Verify attributes were set
        mock_span.set_attribute.assert_any_call("function.name", "test_func")
        mock_span.set_attribute.assert_any_call("function.args_count", 1)
        mock_span.set_attribute.assert_any_call("function.kwargs_count", 1)

    @pytest.mark.skip(reason="Class-level mock prevents testing no-client scenario")
    @patch("rhesis.sdk.telemetry.tracer.get_tracer_provider")
    def test_endpoint_without_client(self, mock_get_provider, mock_create_task):
        """Test @endpoint falls back when client not initialized."""
        # Don't create a client - decorator should handle gracefully

        def test_func():
            return "result"

        # Applying decorator without client should raise RuntimeError
        with pytest.raises(RuntimeError, match="RhesisClient not initialized"):

            @endpoint()
            def decorated_func():
                return "result"

    @patch("rhesis.sdk.telemetry.tracer.get_tracer_provider")
    def test_endpoint_preserves_function_metadata(self, mock_get_provider, mock_create_task):
        """Test @endpoint preserves function name and docstring."""
        # Setup mock provider
        mock_provider = MagicMock()
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_provider.get_tracer.return_value = mock_tracer
        mock_get_provider.return_value = mock_provider

        # Create client (registers as default)
        _client = RhesisClient(
            api_key="test-key",
            project_id="test-project",
            environment="development",
        )

        @endpoint()
        def my_function(x: int) -> int:
            """This is my function."""
            return x * 2

        # Check metadata preserved
        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "This is my function."

    @patch("rhesis.sdk.telemetry.tracer.get_tracer_provider")
    def test_endpoint_with_generator_function(self, mock_get_provider, mock_create_task):
        """Test @endpoint with generator functions."""
        # Setup mock provider
        mock_provider = MagicMock()
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_provider.get_tracer.return_value = mock_tracer
        mock_get_provider.return_value = mock_provider

        # Create client (registers as default)
        _client = RhesisClient(
            api_key="test-key",
            project_id="test-project",
            environment="development",
        )

        @endpoint()
        def stream_tokens():
            for i in range(3):
                yield f"token_{i}"

        # Execute generator
        result = list(stream_tokens())

        assert result == ["token_0", "token_1", "token_2"]
        # Verify span recorded output chunks
        mock_span.set_attribute.assert_any_call("function.output_chunks", 3)

    @patch("rhesis.sdk.telemetry.tracer.get_tracer_provider")
    def test_endpoint_with_observe_false(self, mock_get_provider, mock_create_task):
        """Test @endpoint(observe=False) skips tracing."""
        # Setup mock provider
        mock_provider = MagicMock()
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_provider.get_tracer.return_value = mock_tracer
        mock_get_provider.return_value = mock_provider

        # Create client (registers as default)
        _client = RhesisClient(
            api_key="test-key",
            project_id="test-project",
            environment="development",
        )

        # Define function with observe=False
        @endpoint(observe=False)
        def no_trace_function(x: int) -> int:
            return x * 2

        # Execute function
        result = no_trace_function(10)

        assert result == 20
        # Verify NO span was created
        mock_tracer.start_as_current_span.assert_not_called()

    @patch("rhesis.sdk.telemetry.tracer.get_tracer_provider")
    def test_endpoint_with_observe_true_explicit(self, mock_get_provider, mock_create_task):
        """Test @endpoint(observe=True) creates spans."""
        # Setup mock provider
        mock_provider = MagicMock()
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_provider.get_tracer.return_value = mock_tracer
        mock_get_provider.return_value = mock_provider

        # Create client (registers as default)
        _client = RhesisClient(
            api_key="test-key",
            project_id="test-project",
            environment="development",
        )

        # Define function with explicit observe=True
        @endpoint(observe=True)
        def trace_function(x: int) -> int:
            return x * 2

        # Execute function
        result = trace_function(10)

        assert result == 20
        # Verify span was created (default behavior)
        mock_tracer.start_as_current_span.assert_called_once()

    @patch("rhesis.sdk.telemetry.tracer.get_tracer_provider")
    def test_endpoint_observe_default_is_true(self, mock_get_provider, mock_create_task):
        """Test @endpoint() traces by default (backwards compatible)."""
        # Setup mock provider
        mock_provider = MagicMock()
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_provider.get_tracer.return_value = mock_tracer
        mock_get_provider.return_value = mock_provider

        # Create client (registers as default)
        _client = RhesisClient(
            api_key="test-key",
            project_id="test-project",
            environment="development",
        )

        # Define function without observe parameter
        @endpoint()
        def default_trace_function(x: int) -> int:
            return x * 2

        # Execute function
        result = default_trace_function(10)

        assert result == 20
        # Verify span was created (backwards compatible default)
        mock_tracer.start_as_current_span.assert_called_once()
