"""
Test validation for single-turn and multi-turn tests.

This test file verifies that:
1. Single-turn tests require a prompt
2. Multi-turn tests require a goal in test_configuration
"""

from unittest.mock import MagicMock, Mock
from uuid import uuid4

import pytest

from rhesis.backend.tasks.enums import TestType
from rhesis.backend.tasks.execution.executors.data import get_test_and_prompt


def test_single_turn_requires_prompt(mocker):
    """Test that single-turn tests require a prompt."""
    # Mock database session
    mock_db = MagicMock()

    # Create mock test without prompt
    mock_test = Mock()
    mock_test.id = uuid4()
    mock_test.prompt = None  # No prompt
    mock_test.test_type = Mock()
    mock_test.test_type.type_value = TestType.SINGLE_TURN.value
    mock_test.test_configuration = {}

    # Mock crud.get_test to return our mock test
    mocker.patch(
        "rhesis.backend.tasks.execution.executors.shared.crud.get_test", return_value=mock_test
    )

    # This should raise ValueError for missing prompt
    with pytest.raises(ValueError, match="Single-turn test .* has no associated prompt"):
        get_test_and_prompt(mock_db, str(mock_test.id))


def test_multi_turn_requires_goal(mocker):
    """Test that multi-turn tests require a goal in test_configuration."""
    # Mock database session
    mock_db = MagicMock()

    # Create mock test without goal in test_configuration
    mock_test = Mock()
    mock_test.id = uuid4()
    mock_test.prompt = None  # Multi-turn tests don't need prompts
    mock_test.test_type = Mock()
    mock_test.test_type.type_value = TestType.MULTI_TURN.value
    mock_test.test_configuration = {}  # No goal defined

    # Mock crud.get_test to return our mock test
    mocker.patch(
        "rhesis.backend.tasks.execution.executors.shared.crud.get_test", return_value=mock_test
    )

    # This should raise ValueError for missing goal
    with pytest.raises(ValueError, match="Multi-turn test .* has no goal defined"):
        get_test_and_prompt(mock_db, str(mock_test.id))


def test_single_turn_with_prompt_succeeds(mocker):
    """Test that single-turn tests with prompt succeed validation."""
    # Mock database session
    mock_db = MagicMock()

    # Create mock prompt
    mock_prompt = Mock()
    mock_prompt.content = "Test prompt content"
    mock_prompt.expected_response = "Expected response"

    # Create mock test with prompt
    mock_test = Mock()
    mock_test.id = uuid4()
    mock_test.prompt = mock_prompt
    mock_test.test_type = Mock()
    mock_test.test_type.type_value = TestType.SINGLE_TURN.value
    mock_test.test_configuration = {}

    # Mock crud.get_test to return our mock test
    mocker.patch(
        "rhesis.backend.tasks.execution.executors.shared.crud.get_test", return_value=mock_test
    )

    # This should succeed
    test, prompt_content, expected_response = get_test_and_prompt(mock_db, str(mock_test.id))

    assert test == mock_test
    assert prompt_content == "Test prompt content"
    assert expected_response == "Expected response"


def test_multi_turn_with_goal_succeeds(mocker):
    """Test that multi-turn tests with goal succeed validation."""
    # Mock database session
    mock_db = MagicMock()

    # Create mock test with goal in test_configuration
    mock_test = Mock()
    mock_test.id = uuid4()
    mock_test.prompt = None  # Multi-turn tests don't need prompts
    mock_test.test_type = Mock()
    mock_test.test_type.type_value = TestType.MULTI_TURN.value
    mock_test.test_configuration = {"goal": "Complete a multi-turn conversation", "max_turns": 5}

    # Mock crud.get_test to return our mock test
    mocker.patch(
        "rhesis.backend.tasks.execution.executors.shared.crud.get_test", return_value=mock_test
    )

    # This should succeed
    test, prompt_content, expected_response = get_test_and_prompt(mock_db, str(mock_test.id))

    assert test == mock_test
    # For multi-turn tests, prompt fields should be empty strings
    assert prompt_content == ""
    assert expected_response == ""


def test_multi_turn_with_empty_goal_fails(mocker):
    """Test that multi-turn tests with empty goal fail validation."""
    # Mock database session
    mock_db = MagicMock()

    # Create mock test with empty goal
    mock_test = Mock()
    mock_test.id = uuid4()
    mock_test.prompt = None
    mock_test.test_type = Mock()
    mock_test.test_type.type_value = TestType.MULTI_TURN.value
    mock_test.test_configuration = {"goal": ""}  # Empty goal

    # Mock crud.get_test to return our mock test
    mocker.patch(
        "rhesis.backend.tasks.execution.executors.shared.crud.get_test", return_value=mock_test
    )

    # This should raise ValueError for empty goal
    with pytest.raises(ValueError, match="Multi-turn test .* has no goal defined"):
        get_test_and_prompt(mock_db, str(mock_test.id))
