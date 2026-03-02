"""Tests for Penelope utils module."""

from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest
from helpers import add_turns_to_state

from rhesis.penelope.context import ExecutionStatus
from rhesis.penelope.utils import (
    GoalAchievedCondition,
    MaxTurnsCondition,
    StoppingCondition,
    StopResult,
    TimeoutCondition,
)


def test_stopping_condition_base_class():
    """Test that StoppingCondition base class exists."""
    assert hasattr(StoppingCondition, "should_stop")


def test_stopping_condition_not_implemented():
    """Test that StoppingCondition.should_stop is not implemented."""
    condition = StoppingCondition()

    with pytest.raises(NotImplementedError):
        condition.should_stop(None)


def test_max_turns_condition_initialization():
    """Test MaxTurnsCondition initialization."""
    condition = MaxTurnsCondition(max_turns=10)

    assert condition.max_turns == 10


def test_max_turns_condition_should_not_stop(sample_test_state):
    """Test MaxTurnsCondition doesn't stop before limit."""
    condition = MaxTurnsCondition(max_turns=10)

    result = condition.should_stop(sample_test_state)

    assert result.should_stop is False
    assert result.status is None
    assert result.reason == ""


def test_max_turns_condition_should_stop(sample_test_state):
    """Test MaxTurnsCondition stops at limit."""
    condition = MaxTurnsCondition(max_turns=5)

    # Simulate reaching max turns
    for _ in range(5):
        sample_test_state.current_turn += 1

    result = condition.should_stop(sample_test_state)

    assert result.should_stop is True
    assert result.status == ExecutionStatus.MAX_TURNS
    assert "Maximum turns" in result.reason
    assert "5" in result.reason


def test_timeout_condition_initialization():
    """Test TimeoutCondition initialization."""
    condition = TimeoutCondition(timeout_seconds=60.0)

    assert condition.timeout_seconds == 60.0


def test_timeout_condition_should_not_stop(sample_test_state):
    """Test TimeoutCondition doesn't stop before timeout."""
    condition = TimeoutCondition(timeout_seconds=60.0)

    result = condition.should_stop(sample_test_state)

    assert result.should_stop is False
    assert result.status is None


def test_timeout_condition_should_stop(sample_test_state):
    """Test TimeoutCondition stops after timeout."""
    condition = TimeoutCondition(timeout_seconds=1.0)

    # Simulate time passing
    sample_test_state.start_time = datetime.now() - timedelta(seconds=2)

    result = condition.should_stop(sample_test_state)

    assert result.should_stop is True
    assert result.status == ExecutionStatus.TIMEOUT
    assert "Timeout" in result.reason


def test_goal_achieved_condition_initialization():
    """Test GoalAchievedCondition initialization."""
    mock_result = Mock()
    mock_result.score = 0.5
    mock_result.details = {"is_successful": False, "reason": "Testing"}

    condition = GoalAchievedCondition(result=mock_result)

    assert condition.result == mock_result


def test_goal_achieved_condition_initialization_without_result():
    """Test GoalAchievedCondition can be initialized without result."""
    condition = GoalAchievedCondition()

    assert condition.result is None


def test_goal_achieved_condition_should_not_stop_no_result(sample_test_state):
    """Test GoalAchievedCondition doesn't stop without result."""
    condition = GoalAchievedCondition()

    result = condition.should_stop(sample_test_state)

    assert result.should_stop is False
    assert result.status is None


def test_goal_achieved_condition_should_not_stop_goal_not_achieved(
    sample_test_state,
):
    """Test GoalAchievedCondition doesn't stop if goal not achieved."""
    mock_result = Mock()
    mock_result.score = 0.5
    mock_result.details = {"is_successful": False, "reason": "Still working"}

    condition = GoalAchievedCondition(result=mock_result)

    result = condition.should_stop(sample_test_state)

    assert result.should_stop is False
    assert result.status is None


def test_goal_achieved_condition_should_stop_goal_achieved(sample_test_state):
    """Test GoalAchievedCondition stops when goal achieved."""
    mock_result = Mock()
    mock_result.score = 0.9
    mock_result.details = {
        "is_successful": True,
        "reason": "Goal successfully achieved",
    }

    condition = GoalAchievedCondition(result=mock_result)

    result = condition.should_stop(sample_test_state)

    assert result.should_stop is True
    assert result.status == ExecutionStatus.SUCCESS
    assert "Goal achieved" in result.reason
    assert "successfully achieved" in result.reason


def test_goal_achieved_condition_should_stop_goal_impossible(
    sample_test_state,
):
    """Test GoalAchievedCondition stops when goal is impossible."""
    mock_result = Mock()
    mock_result.score = 0.2
    mock_result.details = {
        "is_successful": False,
        "reason": "Cannot achieve goal",
    }

    condition = GoalAchievedCondition(result=mock_result)
    add_turns_to_state(sample_test_state, 5)

    result = condition.should_stop(sample_test_state)

    assert result.should_stop is True
    assert result.status == ExecutionStatus.FAILURE
    assert "impossible" in result.reason.lower()


def test_goal_achieved_condition_update_result():
    """Test GoalAchievedCondition can update result."""
    condition = GoalAchievedCondition()

    assert condition.result is None

    mock_result = Mock()
    mock_result.score = 0.9
    mock_result.details = {"is_successful": True, "reason": "Updated"}

    condition.update_result(mock_result)

    assert condition.result == mock_result


def test_min_turns_blocks_early_stop(sample_test_state):
    """Test that min_turns prevents early stopping."""
    mock_result = Mock()
    mock_result.score = 0.9
    mock_result.details = {
        "is_successful": True,
        "reason": "Goal achieved",
    }

    condition = GoalAchievedCondition(result=mock_result, max_turns=10, min_turns=8)
    add_turns_to_state(sample_test_state, 5)

    # At 5 turns with min_turns=8, should NOT stop
    result = condition.should_stop(sample_test_state)
    assert result.should_stop is False


def test_min_turns_allows_stop_after_threshold(sample_test_state):
    """Test that early stopping is allowed after min_turns is reached."""
    mock_result = Mock()
    mock_result.score = 0.9
    mock_result.details = {
        "is_successful": True,
        "reason": "Goal achieved",
    }

    condition = GoalAchievedCondition(result=mock_result, max_turns=10, min_turns=5)
    add_turns_to_state(sample_test_state, 5)

    # At 5 turns with min_turns=5, should stop
    result = condition.should_stop(sample_test_state)
    assert result.should_stop is True
    assert result.status == ExecutionStatus.SUCCESS
    assert "Goal achieved" in result.reason


def test_min_turns_capped_at_max_turns(sample_test_state):
    """Test that min_turns cannot exceed max_turns."""
    condition = GoalAchievedCondition(max_turns=10, min_turns=15)

    # min_turns=15 should be capped to max_turns=10
    assert condition._get_early_stop_floor(strict=False) == 10


def test_default_threshold_when_no_min_turns():
    """Test that 80% threshold applies when min_turns is not set."""
    condition = GoalAchievedCondition(max_turns=10)

    # 80% of 10 = 8
    assert condition._get_early_stop_floor(strict=False) == 8


def test_no_floor_when_neither_set():
    """Test fallback to 0 when neither max_turns nor min_turns is set."""
    condition = GoalAchievedCondition()

    assert condition._get_early_stop_floor(strict=False) == 0


def test_stop_result_continue():
    """Test StopResult.continue_() sentinel."""
    result = StopResult.continue_()

    assert result.should_stop is False
    assert result.status is None
    assert result.reason == ""


def test_stop_result_with_status():
    """Test StopResult with a status."""
    result = StopResult(ExecutionStatus.SUCCESS, True, "Test reason")

    assert result.should_stop is True
    assert result.status == ExecutionStatus.SUCCESS
    assert result.goal_achieved is True
    assert result.reason == "Test reason"
