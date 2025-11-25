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
