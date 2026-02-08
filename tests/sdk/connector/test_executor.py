"""Tests for TestExecutor."""

import pytest

from rhesis.sdk.connector.executor import TestExecutor


@pytest.fixture
def executor():
    """Create a test executor for testing."""
    return TestExecutor()


@pytest.fixture
def sync_function():
    """Sample synchronous function."""

    def sync_func(x: int, y: int) -> int:
        return x + y

    return sync_func


@pytest.fixture
def async_function():
    """Sample asynchronous function."""

    async def async_func(x: int, y: int) -> int:
        return x * y

    return async_func


@pytest.fixture
def generator_function():
    """Sample generator function."""

    def gen_func(n: int):
        for i in range(n):
            yield str(i)

    return gen_func


@pytest.fixture
def failing_function():
    """Function that raises an exception."""

    def fail_func():
        raise ValueError("Test error")

    return fail_func


@pytest.mark.asyncio
async def test_execute_sync_function(executor, sync_function):
    """Test executing a synchronous function."""
    result = await executor.execute(sync_function, "sync_func", {"x": 3, "y": 4})

    assert result["status"] == "success"
    assert result["output"] == 7
    assert result["error"] is None
    assert result["duration_ms"] > 0


@pytest.mark.asyncio
async def test_execute_async_function(executor, async_function):
    """Test executing an asynchronous function."""
    result = await executor.execute(async_function, "async_func", {"x": 3, "y": 4})

    assert result["status"] == "success"
    assert result["output"] == 12
    assert result["error"] is None
    assert result["duration_ms"] > 0


@pytest.mark.asyncio
async def test_execute_generator_function(executor, generator_function):
    """Test executing a generator function."""
    result = await executor.execute(generator_function, "gen_func", {"n": 5})

    assert result["status"] == "success"
    assert result["output"] == "01234"
    assert result["error"] is None
    assert result["duration_ms"] > 0


@pytest.mark.asyncio
async def test_execute_failing_function(executor, failing_function):
    """Test executing a function that raises an exception."""
    result = await executor.execute(failing_function, "fail_func", {})

    assert result["status"] == "error"
    assert result["output"] is None
    assert "Test error" in result["error"]
    assert result["duration_ms"] > 0


@pytest.mark.asyncio
async def test_execute_with_no_inputs(executor):
    """Test executing a function with no inputs."""

    def no_input_func():
        return "success"

    result = await executor.execute(no_input_func, "no_input_func", {})

    assert result["status"] == "success"
    assert result["output"] == "success"


@pytest.mark.asyncio
async def test_execute_with_complex_return(executor):
    """Test executing a function with complex return value."""

    def complex_return():
        return {"key": "value", "number": 42}

    result = await executor.execute(complex_return, "complex_return", {})

    assert result["status"] == "success"
    assert result["output"] == {"key": "value", "number": 42}


@pytest.mark.asyncio
async def test_execute_generator_with_error(executor):
    """Test generator that raises exception."""

    def failing_generator():
        yield "first"
        raise RuntimeError("Generator error")

    result = await executor.execute(failing_generator, "failing_gen", {})

    assert result["status"] == "error"
    assert "Generator error" in result["error"]


@pytest.mark.asyncio
async def test_execute_async_generator(executor):
    """Test executing an async generator function."""

    async def async_gen(n: int):
        for i in range(n):
            yield f"item_{i}"

    result = await executor.execute(async_gen, "async_gen", {"n": 3})

    assert result["status"] == "success"
    assert result["output"] == "item_0item_1item_2"


@pytest.mark.asyncio
async def test_duration_tracking(executor, sync_function):
    """Test that execution duration is tracked."""
    result = await executor.execute(sync_function, "sync_func", {"x": 1, "y": 2})

    assert "duration_ms" in result
    assert isinstance(result["duration_ms"], float)
    assert result["duration_ms"] >= 0


class TestTraceIdPropagation:
    """Tests for trace_id propagation through the executor."""

    @pytest.mark.asyncio
    async def test_trace_id_from_context_var_async(self, executor):
        """Test trace_id retrieval from context var for async functions."""
        from rhesis.sdk.telemetry.context import get_root_trace_id, set_root_trace_id

        test_trace_id = "abc123def456789012345678901234ab"

        async def async_func_with_trace():
            # Simulate tracer setting trace_id in context
            set_root_trace_id(test_trace_id)
            return {"result": "success"}

        result = await executor.execute(async_func_with_trace, "async_trace", {})

        assert result["status"] == "success"
        assert result["trace_id"] == test_trace_id
        # Context should be cleared after execution
        assert get_root_trace_id() is None

    @pytest.mark.asyncio
    async def test_trace_id_from_result_dict_sync(self, executor):
        """Test trace_id retrieval from thread-safe dict for sync functions.

        For sync functions running in thread pool, context vars don't propagate back.
        The tracer stores trace_id in a thread-safe dict keyed by result id.
        """
        from rhesis.sdk.telemetry.tracer import store_result_trace_id

        test_trace_id = "sync123456789012345678901234abcd"

        def sync_func_with_trace():
            result = {"result": "from sync"}
            # Simulate what the tracer does: store trace_id for this result
            store_result_trace_id(result, test_trace_id)
            return result

        result = await executor.execute(sync_func_with_trace, "sync_trace", {})

        assert result["status"] == "success"
        assert result["trace_id"] == test_trace_id

    @pytest.mark.asyncio
    async def test_trace_id_none_when_not_set(self, executor):
        """Test that trace_id is None when not set by tracer."""

        def func_without_trace():
            return {"result": "no trace"}

        result = await executor.execute(func_without_trace, "no_trace", {})

        assert result["status"] == "success"
        assert result["trace_id"] is None

    @pytest.mark.asyncio
    async def test_trace_id_on_error(self, executor):
        """Test that trace_id is None when function errors."""

        def failing_func():
            raise ValueError("Test error")

        result = await executor.execute(failing_func, "failing", {})

        assert result["status"] == "error"
        assert result["trace_id"] is None

    @pytest.mark.asyncio
    async def test_trace_id_with_pydantic_model_sync(self, executor):
        """Test trace_id retrieval works with Pydantic model results."""
        from pydantic import BaseModel

        from rhesis.sdk.telemetry.tracer import store_result_trace_id

        class TestResponse(BaseModel):
            message: str

        test_trace_id = "pydantic12345678901234567890abcd"

        def func_returning_pydantic():
            result = TestResponse(message="hello")
            # Tracer stores trace_id for the Pydantic model
            store_result_trace_id(result, test_trace_id)
            return result

        result = await executor.execute(func_returning_pydantic, "pydantic_func", {})

        assert result["status"] == "success"
        # Result should be serialized to dict
        assert result["output"] == {"message": "hello"}
        # trace_id should be retrieved before serialization
        assert result["trace_id"] == test_trace_id
