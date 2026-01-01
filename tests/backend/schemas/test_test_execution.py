"""Tests for test execution context schema."""

from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from rhesis.backend.app.schemas.test_execution import TestExecutionContext


def test_valid_test_execution_context():
    """Test creating a valid test execution context."""
    test_run_id = uuid4()
    test_id = uuid4()
    test_config_id = uuid4()

    context = TestExecutionContext(
        test_run_id=test_run_id,
        test_id=test_id,
        test_configuration_id=test_config_id,
    )

    assert context.test_run_id == test_run_id
    assert context.test_id == test_id
    assert context.test_configuration_id == test_config_id
    assert context.test_result_id is None


def test_test_execution_context_with_result_id():
    """Test context with optional test_result_id."""
    test_run_id = uuid4()
    test_id = uuid4()
    test_config_id = uuid4()
    test_result_id = uuid4()

    context = TestExecutionContext(
        test_run_id=test_run_id,
        test_id=test_id,
        test_configuration_id=test_config_id,
        test_result_id=test_result_id,
    )

    assert context.test_result_id == test_result_id


def test_test_execution_context_from_strings():
    """Test creating context from UUID strings."""
    context = TestExecutionContext(
        test_run_id="550e8400-e29b-41d4-a716-446655440000",
        test_id="6ba7b810-9dad-11d1-80b4-00c04fd430c8",
        test_configuration_id="6ba7b814-9dad-11d1-80b4-00c04fd430c8",
    )

    assert isinstance(context.test_run_id, UUID)
    assert isinstance(context.test_id, UUID)
    assert isinstance(context.test_configuration_id, UUID)


def test_test_execution_context_invalid_uuid():
    """Test that invalid UUIDs raise ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        TestExecutionContext(
            test_run_id="not-a-uuid",
            test_id="6ba7b810-9dad-11d1-80b4-00c04fd430c8",
            test_configuration_id="6ba7b814-9dad-11d1-80b4-00c04fd430c8",
        )

    assert "test_run_id" in str(exc_info.value)


def test_test_execution_context_missing_required_field():
    """Test that missing required fields raise ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        TestExecutionContext(
            test_run_id=uuid4(),
            # test_id is missing
            test_configuration_id=uuid4(),
        )

    assert "test_id" in str(exc_info.value)


def test_test_execution_context_model_dump():
    """Test serializing context to dict."""
    test_run_id = uuid4()
    test_id = uuid4()
    test_config_id = uuid4()

    context = TestExecutionContext(
        test_run_id=test_run_id,
        test_id=test_id,
        test_configuration_id=test_config_id,
    )

    dumped = context.model_dump()

    assert dumped["test_run_id"] == test_run_id
    assert dumped["test_id"] == test_id
    assert dumped["test_configuration_id"] == test_config_id
    assert dumped["test_result_id"] is None


def test_test_execution_context_json_serialization():
    """Test JSON serialization with proper UUID handling."""
    test_run_id = uuid4()
    test_id = uuid4()
    test_config_id = uuid4()

    context = TestExecutionContext(
        test_run_id=test_run_id,
        test_id=test_id,
        test_configuration_id=test_config_id,
    )

    # JSON mode converts UUIDs to strings
    dumped = context.model_dump(mode="json")

    assert isinstance(dumped["test_run_id"], str)
    assert isinstance(dumped["test_id"], str)
    assert isinstance(dumped["test_configuration_id"], str)
    assert dumped["test_result_id"] is None
