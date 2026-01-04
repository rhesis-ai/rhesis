"""Tests for test execution context variables."""

import pytest

from rhesis.sdk.telemetry.context import (
    get_test_execution_context,
    set_test_execution_context,
)


@pytest.fixture
def sample_test_context():
    """Sample test execution context."""
    return {
        "test_run_id": "550e8400-e29b-41d4-a716-446655440000",
        "test_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
        "test_configuration_id": "6ba7b814-9dad-11d1-80b4-00c04fd430c8",
        "test_result_id": None,
    }


def test_context_starts_empty():
    """Test that context variable starts as None."""
    context = get_test_execution_context()
    assert context is None


def test_set_and_get_context(sample_test_context):
    """Test setting and retrieving context."""
    set_test_execution_context(sample_test_context)

    retrieved = get_test_execution_context()
    assert retrieved == sample_test_context
    assert retrieved["test_run_id"] == sample_test_context["test_run_id"]

    # Clean up
    set_test_execution_context(None)


def test_clear_context(sample_test_context):
    """Test clearing context by setting to None."""
    set_test_execution_context(sample_test_context)
    assert get_test_execution_context() is not None

    set_test_execution_context(None)
    assert get_test_execution_context() is None


def test_context_isolation():
    """Test that context changes don't affect other contexts."""
    context1 = {"test_run_id": "run-1", "test_id": "test-1"}
    context2 = {"test_run_id": "run-2", "test_id": "test-2"}

    # Set first context
    set_test_execution_context(context1)
    assert get_test_execution_context() == context1

    # Override with second context
    set_test_execution_context(context2)
    assert get_test_execution_context() == context2
    assert get_test_execution_context() != context1

    # Clean up
    set_test_execution_context(None)


def test_context_with_partial_data():
    """Test context with missing optional fields."""
    partial_context = {
        "test_run_id": "550e8400-e29b-41d4-a716-446655440000",
        "test_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
        "test_configuration_id": "6ba7b814-9dad-11d1-80b4-00c04fd430c8",
        # test_result_id is missing
    }

    set_test_execution_context(partial_context)
    retrieved = get_test_execution_context()

    assert retrieved["test_run_id"] is not None
    assert retrieved["test_id"] is not None
    assert "test_result_id" not in retrieved

    # Clean up
    set_test_execution_context(None)
