"""Tests for @observe decorator."""

from unittest.mock import MagicMock, patch

import pytest

from rhesis.sdk import RhesisClient
from rhesis.sdk.decorators import observe


@pytest.fixture
def mock_client():
    """Create a mock RhesisClient for testing."""
    with patch("rhesis.sdk.decorators._default_client") as mock:
        client = MagicMock(spec=RhesisClient)

        # Mock the tracer
        tracer = MagicMock()
        tracer.trace_execution = MagicMock(
            side_effect=lambda fn, f, a, k, sn=None, ea=None: f(*a, **k)
        )
        tracer.trace_execution_async = MagicMock(
            side_effect=lambda fn, f, a, k, sn=None, ea=None: f(*a, **k)
        )

        client._tracer = tracer
        mock.return_value = client

        # Set _default_client
        import rhesis.sdk.decorators as decorators_module

        decorators_module._default_client = client

        yield client

        # Cleanup
        decorators_module._default_client = None


def test_observe_decorator_basic(mock_client):
    """Test basic @observe decorator functionality."""

    @observe()
    def test_function(x: int) -> int:
        return x * 2

    # Function should execute normally
    result = test_function(5)
    assert result == 10

    # Verify tracer.trace_execution was called
    mock_client._tracer.trace_execution.assert_called_once()


def test_observe_decorator_with_name(mock_client):
    """Test @observe decorator with custom name."""

    @observe(name="custom_name")
    def test_function(x: int) -> int:
        return x * 2

    result = test_function(5)
    assert result == 10

    # Verify tracer.trace_execution was called with custom name
    mock_client._tracer.trace_execution.assert_called_once()
    call_args = mock_client._tracer.trace_execution.call_args
    assert call_args[0][0] == "custom_name"  # function_name


def test_observe_decorator_with_span_name(mock_client):
    """Test @observe decorator with custom span name."""

    @observe(span_name="ai.llm.invoke")
    def test_function(prompt: str) -> str:
        return f"Response to: {prompt}"

    result = test_function("test prompt")
    assert result == "Response to: test prompt"

    # Verify span_name was passed
    call_args = mock_client._tracer.trace_execution.call_args
    assert call_args[0][4] == "ai.llm.invoke"  # span_name


def test_observe_decorator_with_attributes(mock_client):
    """Test @observe decorator with custom attributes."""

    @observe(model="gpt-4", temperature=0.7)
    def test_function(prompt: str) -> str:
        return f"Response to: {prompt}"

    result = test_function("test prompt")
    assert result == "Response to: test prompt"

    # Verify extra attributes were passed
    call_args = mock_client._tracer.trace_execution.call_args
    extra_attrs = call_args[0][5]  # extra_attributes
    assert extra_attrs == {"model": "gpt-4", "temperature": 0.7}


def test_observe_decorator_with_exception(mock_client):
    """Test @observe decorator when function raises exception."""

    # Make trace_execution propagate the exception
    def raise_error(fn, f, a, k, sn=None, ea=None):
        return f(*a, **k)

    mock_client._tracer.trace_execution.side_effect = raise_error

    @observe()
    def test_function():
        raise ValueError("Test error")

    # Exception should be propagated
    with pytest.raises(ValueError, match="Test error"):
        test_function()


def test_observe_decorator_captures_io(mock_client):
    """Test that @observe decorator captures inputs and outputs via trace_execution."""

    @observe()
    def test_function(x: int, y: int, multiplier: int = 2) -> int:
        return (x + y) * multiplier

    result = test_function(5, 3, multiplier=10)
    assert result == 80

    # Verify trace_execution was called with correct args
    call_args = mock_client._tracer.trace_execution.call_args
    assert call_args[0][0] == "test_function"  # function_name
    assert call_args[0][1] == test_function.__wrapped__  # func
    assert call_args[0][2] == (5, 3)  # args
    assert call_args[0][3] == {"multiplier": 10}  # kwargs
    # trace_execution will capture I/O internally
