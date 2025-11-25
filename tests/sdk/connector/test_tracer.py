"""Tests for Tracer."""

from unittest.mock import MagicMock, patch

import pytest

from rhesis.sdk.connector.tracer import Tracer


@pytest.fixture
def tracer():
    """Create a tracer for testing."""
    return Tracer(
        api_key="test-api-key",
        project_id="test-project",
        environment="test",
        base_url="http://localhost:8080",
    )


@pytest.fixture
def sample_function():
    """Sample function for testing."""

    def sample_func(x: int) -> int:
        return x * 2

    return sample_func


@pytest.fixture
def generator_function():
    """Sample generator function."""

    def gen_func(n: int):
        for i in range(n):
            yield i

    return gen_func


@pytest.fixture
def failing_function():
    """Function that raises an exception."""

    def fail_func():
        raise ValueError("Test error")

    return fail_func


def test_tracer_initialization(tracer):
    """Test tracer initializes with correct configuration."""
    assert tracer.api_key == "test-api-key"
    assert tracer.project_id == "test-project"
    assert tracer.environment == "test"
    assert tracer.base_url == "http://localhost:8080"


@patch("rhesis.sdk.connector.tracer.threading.Thread")
def test_trace_execution_sync_function(mock_thread, tracer, sample_function):
    """Test tracing a synchronous function."""
    result = tracer.trace_execution("sample_func", sample_function, (5,), {})

    assert result == 10
    # Verify trace was sent asynchronously
    mock_thread.assert_called_once()
    call_args = mock_thread.call_args
    assert call_args[1]["daemon"] is True


@patch("rhesis.sdk.connector.tracer.threading.Thread")
def test_trace_execution_with_kwargs(mock_thread, tracer):
    """Test tracing function with keyword arguments."""

    def func_with_kwargs(a, b=10):
        return a + b

    result = tracer.trace_execution("func", func_with_kwargs, (5,), {"b": 20})

    assert result == 25
    mock_thread.assert_called_once()


@patch("rhesis.sdk.connector.tracer.threading.Thread")
def test_trace_execution_generator(mock_thread, tracer, generator_function):
    """Test tracing a generator function."""
    result = tracer.trace_execution("gen_func", generator_function, (3,), {})

    # Result should be a generator
    output = list(result)
    assert output == [0, 1, 2]

    # Trace should be sent after generator is consumed
    mock_thread.assert_called_once()


@patch("rhesis.sdk.connector.tracer.threading.Thread")
def test_trace_execution_error(mock_thread, tracer, failing_function):
    """Test tracing a function that raises an exception."""
    with pytest.raises(ValueError, match="Test error"):
        tracer.trace_execution("fail_func", failing_function, (), {})

    # Verify error trace was sent
    mock_thread.assert_called_once()
    call_args = mock_thread.call_args
    args = call_args[1]["args"]
    # Check that error status and message are included
    assert args[4] == "error"  # status
    assert "Test error" in args[5]  # error message


@patch("requests.post")
def test_send_trace_sync_success(mock_post, tracer):
    """Test successful trace sending."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    tracer._send_trace_sync(
        function_name="test_func",
        inputs={"args": (1,), "kwargs": {}},
        output="result",
        duration_ms=100.5,
        status="success",
        error=None,
    )

    mock_post.assert_called_once()
    call_args = mock_post.call_args

    # Verify request details
    assert call_args[1]["json"]["function_name"] == "test_func"
    assert call_args[1]["json"]["status"] == "success"
    assert call_args[1]["json"]["output"] == "result"
    assert call_args[1]["json"]["duration_ms"] == 100.5
    assert call_args[1]["json"]["project_id"] == "test-project"
    assert call_args[1]["json"]["environment"] == "test"


@patch("requests.post")
def test_send_trace_sync_with_error(mock_post, tracer):
    """Test sending error trace."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    tracer._send_trace_sync(
        function_name="fail_func",
        inputs={"args": (), "kwargs": {}},
        output=None,
        duration_ms=50.0,
        status="error",
        error="ValueError: Test error",
    )

    call_args = mock_post.call_args
    assert call_args[1]["json"]["status"] == "error"
    assert call_args[1]["json"]["error"] == "ValueError: Test error"
    assert call_args[1]["json"]["output"] is None


@patch("requests.post")
def test_send_trace_handles_network_error(mock_post, tracer):
    """Test that trace sending handles network errors gracefully."""
    mock_post.side_effect = Exception("Network error")

    # Should not raise exception
    tracer._send_trace_sync(
        function_name="test_func",
        inputs={},
        output="result",
        duration_ms=100.0,
        status="success",
        error=None,
    )


@patch("requests.post")
def test_url_construction_ws_to_http(mock_post):
    """Test URL construction from WebSocket to HTTP."""
    tracer = Tracer(
        api_key="key",
        project_id="project",
        environment="dev",
        base_url="ws://localhost:8080",
    )

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    tracer._send_trace_sync("func", {}, "result", 100.0, "success")

    call_args = mock_post.call_args
    url = call_args[0][0]
    assert url == "http://localhost:8080/connector/trace"


@patch("requests.post")
def test_url_construction_wss_to_https(mock_post):
    """Test URL construction from secure WebSocket to HTTPS."""
    tracer = Tracer(
        api_key="key",
        project_id="project",
        environment="prod",
        base_url="wss://api.example.com",
    )

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    tracer._send_trace_sync("func", {}, "result", 100.0, "success")

    call_args = mock_post.call_args
    url = call_args[0][0]
    assert url == "https://api.example.com/connector/trace"


def test_wrap_generator(tracer):
    """Test generator wrapping for tracing."""

    def simple_gen():
        yield "a"
        yield "b"
        yield "c"

    with patch.object(tracer, "_send_trace_async") as mock_send:
        wrapped = tracer._wrap_generator("simple_gen", simple_gen(), {}, 0.0)
        result = list(wrapped)

        assert result == ["a", "b", "c"]
        mock_send.assert_called_once()
        # Verify output was collected
        call_args = mock_send.call_args[0]
        assert call_args[2] == "abc"  # output


def test_wrap_generator_with_error(tracer):
    """Test generator wrapping handles errors."""

    def failing_gen():
        yield "first"
        raise RuntimeError("Gen error")

    with patch.object(tracer, "_send_trace_async") as mock_send:
        wrapped = tracer._wrap_generator("failing_gen", failing_gen(), {}, 0.0)

        with pytest.raises(RuntimeError, match="Gen error"):
            list(wrapped)

        mock_send.assert_called_once()
        call_args = mock_send.call_args[0]
        assert call_args[4] == "error"  # status
        assert "Gen error" in call_args[5]  # error message
