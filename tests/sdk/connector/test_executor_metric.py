"""Tests for TestExecutor.execute_metric."""

import pytest

from rhesis.sdk.connector.executor import TestExecutor


@pytest.fixture
def executor():
    """Create a test executor."""
    return TestExecutor()


@pytest.fixture
def sync_metric():
    """Sync metric function (input, output only)."""

    def score_metric(input: str, output: str) -> dict:
        length_ratio = len(output) / max(len(input), 1)
        return {"score": min(length_ratio, 1.0)}

    return score_metric


@pytest.fixture
def async_metric():
    """Async metric function (all four params)."""

    async def score_metric(input: str, output: str, expected_output: str, context: list) -> dict:
        match = 1.0 if output == expected_output else 0.0
        return {"score": match, "details": {"reason": "exact match"}}

    return score_metric


@pytest.fixture
def failing_metric():
    """Metric function that raises."""

    def bad_metric(input: str, output: str) -> dict:
        raise ValueError("metric computation failed")

    return bad_metric


@pytest.mark.asyncio
async def test_execute_sync_metric(executor, sync_metric):
    """Test executing a synchronous metric."""
    result = await executor.execute_metric(
        metric_func=sync_metric,
        metric_name="length_ratio",
        inputs={
            "input": "hello",
            "output": "hello world",
            "expected_output": "",
            "context": [],
        },
        accepted_params=["input", "output"],
    )

    assert result["status"] == "success"
    assert result["score"] is not None
    assert result["error"] is None
    assert result["duration_ms"] > 0


@pytest.mark.asyncio
async def test_execute_async_metric(executor, async_metric):
    """Test executing an async metric."""
    result = await executor.execute_metric(
        metric_func=async_metric,
        metric_name="exact_match",
        inputs={
            "input": "what is 2+2?",
            "output": "4",
            "expected_output": "4",
            "context": ["math"],
        },
        accepted_params=["input", "output", "expected_output", "context"],
    )

    assert result["status"] == "success"
    assert result["score"] == 1.0
    assert result["details"]["reason"] == "exact match"


@pytest.mark.asyncio
async def test_execute_metric_filters_inputs(executor):
    """Test that only accepted_params are passed to the metric function."""
    received_kwargs = {}

    def capture_metric(input: str, output: str) -> dict:
        received_kwargs.update({"input": input, "output": output})
        return {"score": 1.0}

    await executor.execute_metric(
        metric_func=capture_metric,
        metric_name="capture",
        inputs={
            "input": "hello",
            "output": "world",
            "expected_output": "should be filtered",
            "context": ["should", "be", "filtered"],
        },
        accepted_params=["input", "output"],
    )

    assert received_kwargs == {"input": "hello", "output": "world"}


@pytest.mark.asyncio
async def test_execute_metric_failure(executor, failing_metric):
    """Test metric that raises an exception."""
    result = await executor.execute_metric(
        metric_func=failing_metric,
        metric_name="bad_metric",
        inputs={
            "input": "hello",
            "output": "world",
            "expected_output": "",
            "context": [],
        },
        accepted_params=["input", "output"],
    )

    assert result["status"] == "error"
    assert result["score"] is None
    assert "metric computation failed" in result["error"]
    assert result["duration_ms"] > 0


@pytest.mark.asyncio
async def test_execute_metric_bare_score_return(executor):
    """Test metric that returns a bare numeric value."""

    def bare_metric(input: str, output: str) -> float:
        return 0.75

    result = await executor.execute_metric(
        metric_func=bare_metric,
        metric_name="bare",
        inputs={"input": "a", "output": "b", "expected_output": "", "context": []},
        accepted_params=["input", "output"],
    )

    assert result["status"] == "success"
    assert result["score"] == 0.75
    assert result["details"] == {}


@pytest.mark.asyncio
async def test_execute_metric_object_result(executor):
    """Test metric that returns an object with .score and .details."""

    class MetricResult:
        def __init__(self, score, details):
            self.score = score
            self.details = details

    def obj_metric(input: str, output: str):
        return MetricResult(0.95, {"reason": "very good"})

    result = await executor.execute_metric(
        metric_func=obj_metric,
        metric_name="obj_metric",
        inputs={"input": "a", "output": "b", "expected_output": "", "context": []},
        accepted_params=["input", "output"],
    )

    assert result["status"] == "success"
    assert result["score"] == 0.95
    assert result["details"]["reason"] == "very good"
