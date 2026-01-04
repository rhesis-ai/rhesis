"""Tests for executor handling of test execution context."""

import pytest

from rhesis.sdk.connector.executor import TestExecutor
from rhesis.sdk.telemetry.constants import TestExecutionContext as TestContextConstants
from rhesis.sdk.telemetry.context import get_test_execution_context


@pytest.fixture
def executor():
    """Create a test executor for testing."""
    return TestExecutor()


@pytest.fixture
def sample_test_context():
    """Sample test execution context."""
    return {
        TestContextConstants.Fields.TEST_RUN_ID: "550e8400-e29b-41d4-a716-446655440000",
        TestContextConstants.Fields.TEST_ID: "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
        TestContextConstants.Fields.TEST_CONFIGURATION_ID: "6ba7b814-9dad-11d1-80b4-00c04fd430c8",
        TestContextConstants.Fields.TEST_RESULT_ID: None,
    }


@pytest.mark.asyncio
async def test_executor_extracts_test_context(executor, sample_test_context):
    """Test that executor extracts _rhesis_test_context from inputs."""

    def test_func(x: int, y: int) -> int:
        # This function should NOT receive _rhesis_test_context
        return x + y

    inputs = {
        "x": 5,
        "y": 10,
        TestContextConstants.CONTEXT_KEY: sample_test_context,
    }

    result = await executor.execute(test_func, "test_func", inputs)

    assert result["status"] == "success"
    assert result["output"] == 15
    # Context should have been extracted, not passed to function


@pytest.mark.asyncio
async def test_executor_clears_context_after_execution(executor, sample_test_context):
    """Test that executor clears context after execution."""

    def test_func() -> str:
        return "success"

    inputs = {TestContextConstants.CONTEXT_KEY: sample_test_context}

    # Execute function
    await executor.execute(test_func, "test_func", inputs)

    # Context should be cleared
    assert get_test_execution_context() is None


@pytest.mark.asyncio
async def test_executor_clears_context_on_error(executor, sample_test_context):
    """Test that executor clears context even when function raises error."""

    def failing_func():
        raise ValueError("Test error")

    inputs = {TestContextConstants.CONTEXT_KEY: sample_test_context}

    # Execute function (will fail)
    result = await executor.execute(failing_func, "failing_func", inputs)

    assert result["status"] == "error"
    # Context should still be cleared
    assert get_test_execution_context() is None


@pytest.mark.asyncio
async def test_executor_without_test_context(executor):
    """Test that executor works normally without test context."""

    def test_func(x: int) -> int:
        return x * 2

    inputs = {"x": 7}  # No test context

    result = await executor.execute(test_func, "test_func", inputs)

    assert result["status"] == "success"
    assert result["output"] == 14
    assert get_test_execution_context() is None


@pytest.mark.asyncio
async def test_user_function_receives_clean_kwargs(executor, sample_test_context):
    """Test that user function receives kwargs without internal parameters."""

    received_kwargs = {}

    def capture_kwargs(**kwargs):
        received_kwargs.update(kwargs)
        return "captured"

    inputs = {
        "user_param": "value",
        "another_param": 42,
        TestContextConstants.CONTEXT_KEY: sample_test_context,
    }

    result = await executor.execute(capture_kwargs, "capture_kwargs", inputs)

    assert result["status"] == "success"
    # User function should only receive user params
    assert "user_param" in received_kwargs
    assert "another_param" in received_kwargs
    # Should NOT receive internal context
    assert TestContextConstants.CONTEXT_KEY not in received_kwargs


@pytest.mark.asyncio
async def test_async_function_with_context(executor, sample_test_context):
    """Test async function with test context."""

    async def async_func(x: int, y: int) -> int:
        return x * y

    inputs = {
        "x": 3,
        "y": 4,
        TestContextConstants.CONTEXT_KEY: sample_test_context,
    }

    result = await executor.execute(async_func, "async_func", inputs)

    assert result["status"] == "success"
    assert result["output"] == 12
    # Context should be cleared
    assert get_test_execution_context() is None
