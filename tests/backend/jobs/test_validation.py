"""
Test validation for single-turn and multi-turn tests.

This test file verifies that:
1. Single-turn tests require a prompt
2. Multi-turn tests require a goal in test_configuration
"""

from unittest.mock import MagicMock, Mock
from uuid import uuid4

import pytest

from rhesis.backend.app.constants import TestType
from rhesis.backend.app.utils.database_exceptions import ItemDeletedException
from rhesis.backend.jobs.execution.executors.data import get_test_and_prompt


def _mock_query_builder(mocker, test_obj):
    """Mock get_item_detail, which get_test_and_prompt uses to fetch the test."""
    mocker.patch("rhesis.backend.app.utils.crud_utils.get_item_detail", return_value=test_obj)


def test_deleted_test_raises_clear_value_error(mocker):
    """A soft-deleted test must raise a clear ValueError, not ItemDeletedException.

    get_test_and_prompt's contract is ValueError for every failure mode --
    background executors only catch/re-raise generically, so the exception
    type doesn't need to change, but the message should say "deleted" rather
    than the generic "not found".
    """
    mock_db = MagicMock()
    mocker.patch(
        "rhesis.backend.app.utils.crud_utils.get_item_detail",
        side_effect=ItemDeletedException("Test", "some-id"),
    )

    with pytest.raises(ValueError, match="has been deleted"):
        get_test_and_prompt(mock_db, str(uuid4()))


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

    # Mock the QueryBuilder chain to return our mock test
    _mock_query_builder(mocker, mock_test)

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

    # Mock the QueryBuilder chain to return our mock test
    _mock_query_builder(mocker, mock_test)

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

    # Mock the QueryBuilder chain to return our mock test
    _mock_query_builder(mocker, mock_test)

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

    # Mock the QueryBuilder chain to return our mock test
    _mock_query_builder(mocker, mock_test)

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

    # Mock the QueryBuilder chain to return our mock test
    _mock_query_builder(mocker, mock_test)

    # This should raise ValueError for empty goal
    with pytest.raises(ValueError, match="Multi-turn test .* has no goal defined"):
        get_test_and_prompt(mock_db, str(mock_test.id))
