"""Tests for ConnectorManager."""

import inspect
from unittest.mock import AsyncMock, Mock, patch

import pytest

from rhesis.sdk.connector.manager import ConnectorManager
from rhesis.sdk.connector.types import MessageType
from rhesis.sdk.telemetry import Tracer


def _make_create_task_mock():
    """Return a ``(mock_create_task, mock_task)`` pair.

    The mock ``create_task`` closes any coroutine it receives so that
    Python does not emit *RuntimeWarning: coroutine ... was never awaited*.
    """
    mock_task = Mock(spec=["cancel"])

    def _side_effect(coro, **kwargs):
        if inspect.iscoroutine(coro):
            coro.close()
        return mock_task

    mock_create_task = Mock(side_effect=_side_effect)
    return mock_create_task, mock_task


@pytest.fixture
def manager():
    """Create a connector manager for testing."""
    return ConnectorManager(
        api_key="test-api-key",
        project_id="test-project",
        environment="development",
        base_url="http://localhost:8080",
    )


@pytest.fixture
def sample_function():
    """Sample function for registration."""

    def sample_func(x: int, y: int = 10) -> int:
        return x + y

    return sample_func


def test_manager_initialization(manager):
    """Test manager initializes with correct configuration."""
    assert manager.api_key == "test-api-key"
    assert manager.project_id == "test-project"
    assert manager.environment == "development"
    assert manager.base_url == "http://localhost:8080"
    assert not manager._initialized
    assert manager._connection is None


def test_manager_has_components(manager):
    """Test manager has all required components."""
    assert hasattr(manager, "_registry")
    assert hasattr(manager, "_executor")
    assert hasattr(manager, "_tracer")


def test_manager_uses_telemetry_tracer(manager):
    """Test manager uses Tracer from telemetry module."""
    assert isinstance(manager._tracer, Tracer)


@patch("rhesis.sdk.connector.manager.WebSocketConnection")
@patch("asyncio.get_running_loop")
def test_initialize(mock_get_loop, mock_ws_class, manager):
    """Test manager initialization."""
    # Mock get_running_loop to return a mock loop (instead of raising RuntimeError)
    mock_get_loop.return_value = Mock()

    mock_ws_instance = Mock()
    # Make connect() return an AsyncMock to avoid coroutine warnings
    mock_ws_instance.connect = AsyncMock()
    mock_ws_class.return_value = mock_ws_instance

    mock_create_task, _mock_task = _make_create_task_mock()

    with patch("asyncio.create_task", mock_create_task):
        manager.initialize()

    assert manager._initialized
    assert manager._connection is not None
    mock_ws_class.assert_called_once()
    mock_create_task.assert_called_once()


@patch("asyncio.get_running_loop")
def test_initialize_idempotent(mock_get_loop, manager):
    """Test that calling initialize multiple times is safe."""
    # Mock get_running_loop to return a mock loop (instead of raising RuntimeError)
    mock_get_loop.return_value = Mock()

    mock_create_task, _mock_task = _make_create_task_mock()

    with (
        patch("asyncio.create_task", mock_create_task),
        patch("rhesis.sdk.connector.manager.WebSocketConnection") as mock_ws_class,
    ):
        mock_ws_instance = Mock()
        mock_ws_instance.connect = AsyncMock()
        mock_ws_class.return_value = mock_ws_instance

        manager.initialize()
        manager.initialize()

    # Should only initialize once
    assert mock_create_task.call_count == 1


def test_register_function(manager, sample_function):
    """Test function registration."""
    mock_create_task, _mock_task = _make_create_task_mock()

    with (
        patch("asyncio.create_task", mock_create_task),
        patch("rhesis.sdk.connector.manager.WebSocketConnection") as mock_ws_class,
    ):
        mock_ws_instance = Mock()
        mock_ws_instance.connect = AsyncMock()
        mock_ws_class.return_value = mock_ws_instance

        manager.register_function("sample_func", sample_function, {"desc": "test"})

        assert manager._initialized
        assert manager._registry.has("sample_func")
        assert manager._registry.get("sample_func") == sample_function


def test_websocket_url_construction(manager):
    """Test WebSocket URL construction."""
    url = manager._get_websocket_url()
    assert url == "ws://localhost:8080/connector/ws"


def test_websocket_url_https_to_wss():
    """Test WebSocket URL construction from HTTPS to WSS."""
    manager = ConnectorManager(
        api_key="key",
        project_id="project",
        environment="development",
        base_url="https://api.example.com",
    )

    url = manager._get_websocket_url()
    assert url == "wss://api.example.com/connector/ws"


def test_websocket_url_strips_trailing_slash():
    """Test WebSocket URL construction strips trailing slash."""
    manager = ConnectorManager(
        api_key="key",
        project_id="project",
        environment="development",
        base_url="http://localhost:8080/",
    )

    url = manager._get_websocket_url()
    assert url == "ws://localhost:8080/connector/ws"


@pytest.mark.asyncio
async def test_handle_ping_message(manager):
    """Test handling ping message."""
    manager._connection = AsyncMock()

    await manager._handle_ping()

    manager._connection.send.assert_called_once_with({"type": MessageType.PONG})


@pytest.mark.asyncio
async def test_handle_unknown_message_type(manager):
    """Test handling unknown message type."""
    message = {"type": "unknown_type"}

    # Should not raise exception
    await manager._handle_message(message)


@pytest.mark.asyncio
async def test_handle_test_request_function_not_found(manager):
    """Test handling test request for non-existent function."""
    manager._connection = AsyncMock()

    message = {
        "type": MessageType.EXECUTE_TEST,
        "test_run_id": "test-123",
        "function_name": "nonexistent",
        "inputs": {},
    }

    await manager._handle_test_request(message)

    # Should send error result
    manager._connection.send.assert_called_once()
    call_args = manager._connection.send.call_args[0][0]
    assert call_args["status"] == "error"
    assert "not found" in call_args["error"]


@pytest.mark.asyncio
async def test_handle_test_request_success(manager, sample_function):
    """Test successful test execution."""
    manager._registry.register("sample_func", sample_function, {})
    manager._connection = AsyncMock()

    message = {
        "type": MessageType.EXECUTE_TEST,
        "test_run_id": "test-123",
        "function_name": "sample_func",
        "inputs": {"x": 5, "y": 10},
    }

    await manager._handle_test_request(message)

    manager._connection.send.assert_called_once()
    call_args = manager._connection.send.call_args[0][0]
    assert call_args["status"] == "success"
    assert call_args["output"] == 15
    assert call_args["test_run_id"] == "test-123"


@pytest.mark.asyncio
async def test_handle_test_request_execution_error(manager):
    """Test handling test execution errors."""

    def failing_func():
        raise ValueError("Test error")

    manager._registry.register("failing_func", failing_func, {})
    manager._connection = AsyncMock()

    message = {
        "type": MessageType.EXECUTE_TEST,
        "test_run_id": "test-123",
        "function_name": "failing_func",
        "inputs": {},
    }

    await manager._handle_test_request(message)

    call_args = manager._connection.send.call_args[0][0]
    assert call_args["status"] == "error"
    assert "Test error" in call_args["error"]


@pytest.mark.asyncio
async def test_send_registration(manager, sample_function):
    """Test sending function registration."""
    manager._registry.register("sample_func", sample_function, {"desc": "test"})
    manager._connection = AsyncMock()

    await manager._send_registration()

    manager._connection.send.assert_called_once()
    call_args = manager._connection.send.call_args[0][0]
    assert call_args["type"] == MessageType.REGISTER
    assert call_args["project_id"] == "test-project"
    assert call_args["environment"] == "development"
    assert len(call_args["functions"]) == 1
    assert call_args["functions"][0]["name"] == "sample_func"


@pytest.mark.asyncio
async def test_send_registration_no_connection(manager):
    """Test sending registration when no connection exists."""
    # Should not raise exception
    await manager._send_registration()


@pytest.mark.asyncio
async def test_shutdown(manager):
    """Test manager shutdown."""
    manager._connection = AsyncMock()
    manager._initialized = True

    await manager.shutdown()

    manager._connection.disconnect.assert_called_once()
    assert not manager._initialized


def test_trace_execution_delegates_to_tracer(manager, sample_function):
    """Test that trace_execution delegates to tracer."""
    with patch.object(manager._tracer, "trace_execution") as mock_trace:
        mock_trace.return_value = 42

        result = manager.trace_execution("func", sample_function, (1,), {"y": 2})

        assert result == 42
        mock_trace.assert_called_once_with("func", sample_function, (1,), {"y": 2}, None)


def test_trace_execution_with_span_name(manager, sample_function):
    """Test that trace_execution passes span_name to tracer."""
    with patch.object(manager._tracer, "trace_execution") as mock_trace:
        mock_trace.return_value = 42

        result = manager.trace_execution(
            "func", sample_function, (1,), {"y": 2}, span_name="ai.llm.invoke"
        )

        assert result == 42
        mock_trace.assert_called_once_with("func", sample_function, (1,), {"y": 2}, "ai.llm.invoke")


@pytest.mark.asyncio
async def test_handle_acknowledged_messages(manager):
    """Test handling acknowledgment messages."""
    # These should not raise exceptions
    await manager._handle_message({"type": "connected", "status": "success"})
    await manager._handle_message({"type": "registered", "status": "success"})


@pytest.mark.asyncio
async def test_send_test_result(manager):
    """Test sending test result."""
    manager._connection = AsyncMock()

    await manager._send_test_result(
        test_run_id="test-123",
        status="success",
        output="result",
        error=None,
        duration_ms=100.5,
    )

    manager._connection.send.assert_called_once()
    call_args = manager._connection.send.call_args[0][0]
    assert call_args["test_run_id"] == "test-123"
    assert call_args["status"] == "success"
    assert call_args["output"] == "result"
    assert call_args["duration_ms"] == 100.5


@pytest.mark.asyncio
async def test_send_test_result_no_connection(manager):
    """Test sending test result when no connection."""
    # Should not raise exception
    await manager._send_test_result("test-123", "success", "result")


# ============================================================================
# Parameter injection tests
# ============================================================================


def _param_schema(*fields):
    """Build a valid ParameterSchema dict for tests."""
    return {"fields": [{"name": n, "type": t} for n, t in fields]}


@pytest.mark.asyncio
async def test_handle_test_request_sets_parameters_context(manager):
    """_handle_test_request sets _parameters_context from execute message."""
    import uuid

    from rhesis.sdk.decorators._state import _parameters_context

    captured_ctx = None

    def capturing_func(x: int = 1) -> int:
        nonlocal captured_ctx
        captured_ctx = _parameters_context.get(None)
        return x

    manager._registry.register("cap_func", capturing_func, {})
    manager._connection = AsyncMock()

    exp_id = str(uuid.uuid4())
    message = {
        "type": MessageType.EXECUTE_TEST,
        "test_run_id": "run-1",
        "function_name": "cap_func",
        "inputs": {"x": 42},
        "parameter_experiment_id": exp_id,
        "parameter_version": "v_abc",
        "parameter_source": "environment",
        "parameter_source_environment": "default",
        "parameters": {"model": "gpt-4o", "temperature": 0.9},
        "parameter_schema": _param_schema(("model", "string"), ("temperature", "number")),
    }

    await manager._handle_test_request(message)

    assert captured_ctx is not None
    assert captured_ctx.version == "v_abc"
    assert captured_ctx.source == "environment"
    assert captured_ctx.source_environment == "default"

    call_args = manager._connection.send.call_args[0][0]
    assert call_args["status"] == "success"
    assert call_args["output"] == 42


@pytest.mark.asyncio
async def test_handle_test_request_context_reset_after_execution(manager):
    """_parameters_context is reset after function execution completes."""
    import uuid

    from rhesis.sdk.decorators._state import _parameters_context

    def simple_func(x: int = 1) -> int:
        return x

    manager._registry.register("simple", simple_func, {})
    manager._connection = AsyncMock()

    message = {
        "type": MessageType.EXECUTE_TEST,
        "test_run_id": "run-2",
        "function_name": "simple",
        "inputs": {"x": 1},
        "parameter_experiment_id": str(uuid.uuid4()),
        "parameter_version": "v_1",
        "parameter_source": "version",
        "parameters": {"model": "gpt-4"},
        "parameter_schema": _param_schema(("model", "string")),
    }

    await manager._handle_test_request(message)

    assert _parameters_context.get(None) is None


@pytest.mark.asyncio
async def test_handle_test_request_legacy_parameters_kwarg_warns(manager):
    """Using parameters=True in metadata triggers DeprecationWarning."""
    import uuid
    import warnings

    def param_func(x: int = 1, model: str = "default") -> dict:
        return {"x": x, "model": model}

    manager._registry.register("param_func", param_func, {"parameters": True})
    manager._connection = AsyncMock()

    message = {
        "type": MessageType.EXECUTE_TEST,
        "test_run_id": "run-3",
        "function_name": "param_func",
        "inputs": {"x": 10},
        "parameter_experiment_id": str(uuid.uuid4()),
        "parameter_version": "v_1",
        "parameter_source": "environment",
        "parameter_source_environment": "default",
        "parameters": {"model": "gpt-4o"},
        "parameter_schema": _param_schema(("model", "string")),
    }

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        await manager._handle_test_request(message)

    deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
    assert len(deprecation_warnings) >= 1
    assert "deprecated" in str(deprecation_warnings[0].message).lower()

    call_args = manager._connection.send.call_args[0][0]
    assert call_args["status"] == "success"
    assert call_args["output"]["model"] == "gpt-4o"


@pytest.mark.asyncio
async def test_handle_test_request_no_params_no_warning(manager, sample_function):
    """No DeprecationWarning when no parameters metadata is set."""
    import warnings

    manager._registry.register("sample_func", sample_function, {})
    manager._connection = AsyncMock()

    message = {
        "type": MessageType.EXECUTE_TEST,
        "test_run_id": "run-4",
        "function_name": "sample_func",
        "inputs": {"x": 5, "y": 10},
    }

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        await manager._handle_test_request(message)

    deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
    assert len(deprecation_warnings) == 0

    call_args = manager._connection.send.call_args[0][0]
    assert call_args["status"] == "success"
    assert call_args["output"] == 15
