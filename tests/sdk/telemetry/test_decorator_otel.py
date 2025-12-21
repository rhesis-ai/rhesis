"""End-to-end tests for @collaborate with OTEL integration."""

from unittest.mock import MagicMock, patch

import pytest

from rhesis.sdk import Client
from rhesis.sdk.decorators import collaborate


class TestCollaborateWithOTEL:
    """End-to-end tests for @collaborate decorator with OpenTelemetry."""

    @patch("rhesis.sdk.telemetry.tracer.get_tracer_provider")
    def test_collaborate_uses_telemetry_default_span_name(self, mock_get_provider):
        """Test @collaborate uses telemetry with default span name."""
        # Setup mock provider
        mock_provider = MagicMock()
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_provider.get_tracer.return_value = mock_tracer
        mock_get_provider.return_value = mock_provider

        # Create client (registers as default)
        _client = Client(
            api_key="test-key",
            project_id="test-project",
            environment="test",
        )

        # Define function with @collaborate
        @collaborate()
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
    def test_collaborate_with_custom_span_name(self, mock_get_provider):
        """Test @collaborate with custom span name."""
        # Setup mock provider
        mock_provider = MagicMock()
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_provider.get_tracer.return_value = mock_tracer
        mock_get_provider.return_value = mock_provider

        # Create client (registers as default)
        _client = Client(
            api_key="test-key",
            project_id="test-project",
            environment="test",
        )

        # Define function with custom span name
        @collaborate(span_name="ai.llm.invoke")
        def call_llm(prompt: str) -> str:
            return f"response to {prompt}"

        # Execute function
        result = call_llm("test prompt")

        assert result == "response to test prompt"
        # Verify span was created with custom ai.* name
        call_args = mock_tracer.start_as_current_span.call_args
        assert call_args[1]["name"] == "ai.llm.invoke"

    @patch("rhesis.sdk.telemetry.tracer.get_tracer_provider")
    def test_collaborate_with_tool_span_name(self, mock_get_provider):
        """Test @collaborate with tool operation span name."""
        # Setup mock provider
        mock_provider = MagicMock()
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_provider.get_tracer.return_value = mock_tracer
        mock_get_provider.return_value = mock_provider

        # Create client (registers as default)
        _client = Client(
            api_key="test-key",
            project_id="test-project",
            environment="test",
        )

        # Define tool function
        @collaborate(span_name="ai.tool.invoke")
        def weather_api(city: str) -> dict:
            return {"city": city, "temp": 72}

        # Execute function
        result = weather_api("San Francisco")

        assert result["city"] == "San Francisco"
        call_args = mock_tracer.start_as_current_span.call_args
        assert call_args[1]["name"] == "ai.tool.invoke"

    @patch("rhesis.sdk.telemetry.tracer.get_tracer_provider")
    def test_collaborate_records_function_attributes(self, mock_get_provider):
        """Test @collaborate records function metadata as span attributes."""
        # Setup mock provider
        mock_provider = MagicMock()
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_provider.get_tracer.return_value = mock_tracer
        mock_get_provider.return_value = mock_provider

        # Create client (registers as default)
        _client = Client(
            api_key="test-key",
            project_id="test-project",
            environment="test",
        )

        @collaborate()
        def test_func(a: int, b: int = 5) -> int:
            return a + b

        # Execute with args and kwargs
        _result = test_func(10, b=20)

        # Verify attributes were set
        mock_span.set_attribute.assert_any_call("function.name", "test_func")
        mock_span.set_attribute.assert_any_call("function.args_count", 1)
        mock_span.set_attribute.assert_any_call("function.kwargs_count", 1)

    @patch("rhesis.sdk.telemetry.tracer.get_tracer_provider")
    def test_collaborate_without_client(self, mock_get_provider):
        """Test @collaborate falls back when client not initialized."""
        # Don't create a client - decorator should handle gracefully

        def test_func():
            return "result"

        # Applying decorator without client should raise RuntimeError
        with pytest.raises(RuntimeError, match="RhesisClient not initialized"):

            @collaborate()
            def decorated_func():
                return "result"

    @patch("rhesis.sdk.telemetry.tracer.get_tracer_provider")
    def test_collaborate_preserves_function_metadata(self, mock_get_provider):
        """Test @collaborate preserves function name and docstring."""
        # Setup mock provider
        mock_provider = MagicMock()
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_provider.get_tracer.return_value = mock_tracer
        mock_get_provider.return_value = mock_provider

        # Create client (registers as default)
        _client = Client(
            api_key="test-key",
            project_id="test-project",
            environment="test",
        )

        @collaborate()
        def my_function(x: int) -> int:
            """This is my function."""
            return x * 2

        # Check metadata preserved
        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "This is my function."

    @patch("rhesis.sdk.telemetry.tracer.get_tracer_provider")
    def test_collaborate_with_generator_function(self, mock_get_provider):
        """Test @collaborate with generator functions."""
        # Setup mock provider
        mock_provider = MagicMock()
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_provider.get_tracer.return_value = mock_tracer
        mock_get_provider.return_value = mock_provider

        # Create client (registers as default)
        _client = Client(
            api_key="test-key",
            project_id="test-project",
            environment="test",
        )

        @collaborate()
        def stream_tokens():
            for i in range(3):
                yield f"token_{i}"

        # Execute generator
        result = list(stream_tokens())

        assert result == ["token_0", "token_1", "token_2"]
        # Verify span recorded output chunks
        mock_span.set_attribute.assert_any_call("function.output_chunks", 3)
