"""Tests for async and sync endpoint decorator functionality."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from rhesis.sdk.decorators import endpoint


@pytest.fixture
def mock_client():
    """Create a mock RhesisClient for testing."""
    with patch("rhesis.sdk.decorators._state._default_client") as mock:
        mock._connector_manager = None
        mock._tracer = Mock()
        mock._tracer.trace_execution = Mock(
            side_effect=lambda name, func, args, kwargs, span: func(*args, **kwargs)
        )

        # Async side effect needs to properly await the coroutine
        async def async_side_effect(name, func, args, kwargs, span):
            return await func(*args, **kwargs)

        mock._tracer.trace_execution_async = AsyncMock(side_effect=async_side_effect)
        mock.register_endpoint = Mock()
        yield mock


class TestSyncEndpoint:
    """Tests for sync functions with @endpoint decorator."""

    def test_sync_function_basic(self, mock_client):
        """Test basic sync function with @endpoint decorator."""

        @endpoint()
        def add(x: int, y: int) -> int:
            return x + y

        result = add(5, 3)

        assert result == 8
        mock_client.register_endpoint.assert_called_once()
        mock_client._tracer.trace_execution.assert_called_once()

    def test_sync_function_with_name(self, mock_client):
        """Test sync function with custom name."""

        @endpoint(name="custom_add")
        def add(x: int, y: int) -> int:
            return x + y

        result = add(10, 20)

        assert result == 30
        # Check that custom name was used in registration
        call_args = mock_client.register_endpoint.call_args
        assert call_args[0][0] == "custom_add"

    def test_sync_function_observe_false(self, mock_client):
        """Test sync function with observe=False (no tracing)."""

        @endpoint(observe=False)
        def multiply(x: int, y: int) -> int:
            return x * y

        result = multiply(4, 5)

        assert result == 20
        # Should register but not trace
        mock_client.register_endpoint.assert_called_once()
        mock_client._tracer.trace_execution.assert_not_called()

    def test_sync_function_with_span_name(self, mock_client):
        """Test sync function with custom span name."""

        @endpoint(span_name="ai.llm.invoke")
        def generate_text(prompt: str) -> str:
            return f"Response to: {prompt}"

        result = generate_text("Hello")

        assert result == "Response to: Hello"
        # Verify span_name was passed to tracer
        call_args = mock_client._tracer.trace_execution.call_args
        assert call_args[0][4] == "ai.llm.invoke"  # 5th argument is span_name

    def test_sync_function_with_mappings(self, mock_client):
        """Test sync function with request/response mappings."""

        @endpoint(
            request_mapping={"message": "{{ input }}"}, response_mapping={"output": "{{ result }}"}
        )
        def process(message: str) -> dict:
            return {"result": message.upper()}

        result = process("hello")

        assert result == {"result": "HELLO"}
        # Verify mappings were included in metadata
        call_args = mock_client.register_endpoint.call_args
        enriched_metadata = call_args[0][2]
        assert "request_mapping" in enriched_metadata
        assert "response_mapping" in enriched_metadata

    def test_sync_function_error_handling(self, mock_client):
        """Test sync function error handling."""

        @endpoint()
        def divide(x: int, y: int) -> float:
            return x / y

        with pytest.raises(ZeroDivisionError):
            divide(10, 0)

    def test_sync_function_with_connector_manager(self, mock_client):
        """Test sync function uses connector manager when available."""
        mock_client._connector_manager = Mock()
        mock_client._connector_manager.trace_execution = Mock(
            side_effect=lambda name, func, args, kwargs, span: func(*args, **kwargs)
        )

        @endpoint()
        def compute(x: int) -> int:
            return x * 2

        result = compute(21)

        assert result == 42
        # Should use connector manager instead of direct tracer
        mock_client._connector_manager.trace_execution.assert_called_once()
        mock_client._tracer.trace_execution.assert_not_called()


class TestAsyncEndpoint:
    """Tests for async functions with @endpoint decorator."""

    @pytest.mark.asyncio
    async def test_async_function_basic(self, mock_client):
        """Test basic async function with @endpoint decorator."""

        @endpoint()
        async def add_async(x: int, y: int) -> int:
            await asyncio.sleep(0)  # Simulate async operation
            return x + y

        result = await add_async(5, 3)

        assert result == 8
        mock_client.register_endpoint.assert_called_once()
        mock_client._tracer.trace_execution_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_function_with_name(self, mock_client):
        """Test async function with custom name."""

        @endpoint(name="custom_async_add")
        async def add_async(x: int, y: int) -> int:
            return x + y

        result = await add_async(10, 20)

        assert result == 30
        # Check that custom name was used in registration
        call_args = mock_client.register_endpoint.call_args
        assert call_args[0][0] == "custom_async_add"

    @pytest.mark.asyncio
    async def test_async_function_observe_false(self, mock_client):
        """Test async function with observe=False (no tracing)."""

        @endpoint(observe=False)
        async def multiply_async(x: int, y: int) -> int:
            return x * y

        result = await multiply_async(4, 5)

        assert result == 20
        # Should register but not trace
        mock_client.register_endpoint.assert_called_once()
        mock_client._tracer.trace_execution_async.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_function_with_span_name(self, mock_client):
        """Test async function with custom span name."""

        @endpoint(span_name="ai.llm.invoke")
        async def generate_text_async(prompt: str) -> str:
            await asyncio.sleep(0)
            return f"Async response to: {prompt}"

        result = await generate_text_async("Hello")

        assert result == "Async response to: Hello"
        # Verify span_name was passed to tracer
        call_args = mock_client._tracer.trace_execution_async.call_args
        assert call_args[0][4] == "ai.llm.invoke"  # 5th argument is span_name

    @pytest.mark.asyncio
    async def test_async_function_with_mappings(self, mock_client):
        """Test async function with request/response mappings."""

        @endpoint(
            request_mapping={"message": "{{ input }}"}, response_mapping={"output": "{{ result }}"}
        )
        async def process_async(message: str) -> dict:
            await asyncio.sleep(0)
            return {"result": message.upper()}

        result = await process_async("hello")

        assert result == {"result": "HELLO"}
        # Verify mappings were included in metadata
        call_args = mock_client.register_endpoint.call_args
        enriched_metadata = call_args[0][2]
        assert "request_mapping" in enriched_metadata
        assert "response_mapping" in enriched_metadata

    @pytest.mark.asyncio
    async def test_async_function_error_handling(self, mock_client):
        """Test async function error handling."""

        @endpoint()
        async def divide_async(x: int, y: int) -> float:
            await asyncio.sleep(0)
            return x / y

        with pytest.raises(ZeroDivisionError):
            await divide_async(10, 0)

    @pytest.mark.asyncio
    async def test_async_function_with_connector_manager(self, mock_client):
        """Test async function uses connector manager when available."""
        mock_client._connector_manager = Mock()

        async def async_side_effect(name, func, args, kwargs, span):
            return await func(*args, **kwargs)

        mock_client._connector_manager.trace_execution_async = AsyncMock(
            side_effect=async_side_effect
        )

        @endpoint()
        async def compute_async(x: int) -> int:
            return x * 2

        result = await compute_async(21)

        assert result == 42
        # Should use connector manager instead of direct tracer
        mock_client._connector_manager.trace_execution_async.assert_called_once()
        mock_client._tracer.trace_execution_async.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_function_with_await_internally(self, mock_client):
        """Test async function that uses await internally."""

        async def external_async_call(value: int) -> int:
            await asyncio.sleep(0.001)
            return value * 2

        @endpoint()
        async def process_with_await(x: int) -> int:
            result = await external_async_call(x)
            return result + 10

        result = await process_with_await(5)

        assert result == 20  # (5 * 2) + 10


class TestEndpointManagerIntegration:
    """Tests for endpoint decorator integration with connector manager."""

    @pytest.mark.asyncio
    async def test_manager_trace_execution_async(self):
        """Test that manager's trace_execution_async method works."""
        from rhesis.sdk.connector.manager import ConnectorManager

        manager = ConnectorManager(
            api_key="test-key",
            project_id="test-project",
            environment="development",
            base_url="http://localhost:8080",
        )

        async def sample_async_func(x: int) -> int:
            return x * 2

        with patch.object(
            manager._tracer, "trace_execution_async", new_callable=AsyncMock
        ) as mock_trace:
            mock_trace.return_value = 42

            result = await manager.trace_execution_async(
                "test_func", sample_async_func, (21,), {}, None
            )

            assert result == 42
            mock_trace.assert_called_once()

    def test_manager_trace_execution_sync(self):
        """Test that manager's trace_execution method works."""
        from rhesis.sdk.connector.manager import ConnectorManager

        manager = ConnectorManager(
            api_key="test-key",
            project_id="test-project",
            environment="development",
            base_url="http://localhost:8080",
        )

        def sample_sync_func(x: int) -> int:
            return x * 2

        with patch.object(manager._tracer, "trace_execution") as mock_trace:
            mock_trace.return_value = 42

            result = manager.trace_execution("test_func", sample_sync_func, (21,), {}, None)

            assert result == 42
            mock_trace.assert_called_once()


class TestEndpointDecoratorEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_endpoint_without_client_raises_error(self):
        """Test that using @endpoint without RhesisClient raises error."""
        with patch("rhesis.sdk.decorators._state._default_client", None):
            with pytest.raises(RuntimeError, match="RhesisClient not initialized"):

                @endpoint()
                def some_func():
                    pass

    def test_sync_function_default_name(self, mock_client):
        """Test that function name defaults to __name__."""

        @endpoint()
        def my_special_function(x: int) -> int:
            return x

        call_args = mock_client.register_endpoint.call_args
        assert call_args[0][0] == "my_special_function"

    @pytest.mark.asyncio
    async def test_async_function_default_name(self, mock_client):
        """Test that async function name defaults to __name__."""

        @endpoint()
        async def my_async_special_function(x: int) -> int:
            return x

        call_args = mock_client.register_endpoint.call_args
        assert call_args[0][0] == "my_async_special_function"

    def test_sync_function_with_metadata(self, mock_client):
        """Test sync function with additional metadata."""

        @endpoint(description="A test function", version="1.0")
        def func_with_metadata(x: int) -> int:
            return x

        call_args = mock_client.register_endpoint.call_args
        metadata = call_args[0][2]
        assert metadata["description"] == "A test function"
        assert metadata["version"] == "1.0"

    @pytest.mark.asyncio
    async def test_async_function_with_metadata(self, mock_client):
        """Test async function with additional metadata."""

        @endpoint(description="An async test function", version="2.0")
        async def async_func_with_metadata(x: int) -> int:
            return x

        call_args = mock_client.register_endpoint.call_args
        metadata = call_args[0][2]
        assert metadata["description"] == "An async test function"
        assert metadata["version"] == "2.0"


class TestGetTracerMethod:
    """Tests for the get_tracer_method helper function logic."""

    def test_tracer_selection_with_connector_manager_sync(self, mock_client):
        """Test that connector manager is preferred for sync functions."""
        mock_client._connector_manager = Mock()
        mock_client._connector_manager.trace_execution = Mock(return_value=100)

        @endpoint()
        def test_func(x: int) -> int:
            return x

        _ = test_func(50)

        # Connector manager should be used
        mock_client._connector_manager.trace_execution.assert_called_once()
        mock_client._tracer.trace_execution.assert_not_called()

    @pytest.mark.asyncio
    async def test_tracer_selection_with_connector_manager_async(self, mock_client):
        """Test that connector manager is preferred for async functions."""
        mock_client._connector_manager = Mock()
        mock_client._connector_manager.trace_execution_async = AsyncMock(return_value=100)

        @endpoint()
        async def test_func_async(x: int) -> int:
            return x

        _ = await test_func_async(50)

        # Connector manager should be used
        mock_client._connector_manager.trace_execution_async.assert_called_once()
        mock_client._tracer.trace_execution_async.assert_not_called()

    def test_tracer_selection_without_connector_manager_sync(self, mock_client):
        """Test that direct tracer is used when no connector manager (sync)."""
        mock_client._connector_manager = None

        @endpoint()
        def test_func(x: int) -> int:
            return x

        _ = test_func(50)

        # Direct tracer should be used
        mock_client._tracer.trace_execution.assert_called_once()

    @pytest.mark.asyncio
    async def test_tracer_selection_without_connector_manager_async(self, mock_client):
        """Test that direct tracer is used when no connector manager (async)."""
        mock_client._connector_manager = None

        @endpoint()
        async def test_func_async(x: int) -> int:
            return x

        _ = await test_func_async(50)

        # Direct tracer should be used
        mock_client._tracer.trace_execution_async.assert_called_once()
