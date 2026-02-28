"""Tests for Penelope utils module."""

from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest

from rhesis.penelope.utils import (
    GoalAchievedCondition,
    MaxTurnsCondition,
    StoppingCondition,
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

    should_stop, reason = condition.should_stop(sample_test_state)

    assert should_stop is False
    assert reason == ""


def test_max_turns_condition_should_stop(sample_test_state):
    """Test MaxTurnsCondition stops at limit."""
    condition = MaxTurnsCondition(max_turns=5)

    # Simulate reaching max turns
    for _ in range(5):
        sample_test_state.current_turn += 1

    should_stop, reason = condition.should_stop(sample_test_state)

    assert should_stop is True
    assert "Maximum turns" in reason
    assert "5" in reason


def test_timeout_condition_initialization():
    """Test TimeoutCondition initialization."""
    condition = TimeoutCondition(timeout_seconds=60.0)

    assert condition.timeout_seconds == 60.0


def test_timeout_condition_should_not_stop(sample_test_state):
    """Test TimeoutCondition doesn't stop before timeout."""
    condition = TimeoutCondition(timeout_seconds=60.0)

    should_stop, reason = condition.should_stop(sample_test_state)

    assert should_stop is False
    assert reason == ""


def test_timeout_condition_should_stop(sample_test_state):
    """Test TimeoutCondition stops after timeout."""
    condition = TimeoutCondition(timeout_seconds=1.0)

    # Simulate time passing
    sample_test_state.start_time = datetime.now() - timedelta(seconds=2)

    should_stop, reason = condition.should_stop(sample_test_state)

    assert should_stop is True
    assert "Timeout" in reason


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

    should_stop, reason = condition.should_stop(sample_test_state)

    assert should_stop is False
    assert reason == ""


def test_goal_achieved_condition_should_not_stop_goal_not_achieved(
    sample_test_state,
):
    """Test GoalAchievedCondition doesn't stop if goal not achieved."""
    mock_result = Mock()
    mock_result.score = 0.5
    mock_result.details = {"is_successful": False, "reason": "Still working"}

    condition = GoalAchievedCondition(result=mock_result)

    should_stop, reason = condition.should_stop(sample_test_state)

    assert should_stop is False
    assert reason == ""


def test_goal_achieved_condition_should_stop_goal_achieved(sample_test_state):
    """Test GoalAchievedCondition stops when goal achieved."""
    mock_result = Mock()
    mock_result.score = 0.9
    mock_result.details = {
        "is_successful": True,
        "reason": "Goal successfully achieved",
    }

    condition = GoalAchievedCondition(result=mock_result)

    should_stop, reason = condition.should_stop(sample_test_state)

    assert should_stop is True
    assert "Goal achieved" in reason
    assert "successfully achieved" in reason


def _add_turns_to_state(state, count):
    """Helper to add N turns to a test state."""
    from rhesis.penelope.context import ToolExecution, Turn
    from rhesis.penelope.schemas import (
        AssistantMessage,
        FunctionCall,
        MessageToolCall,
        ToolMessage,
    )

    for i in range(count):
        assistant_msg = AssistantMessage(
            content=f"Turn {i + 1}",
            tool_calls=[
                MessageToolCall(
                    id=f"call_{i}",
                    type="function",
                    function=FunctionCall(
                        name="send_message_to_target", arguments="{}"
                    ),
                )
            ],
        )
        tool_msg = ToolMessage(
            tool_call_id=f"call_{i}",
            name="send_message_to_target",
            content="result",
        )
        target_execution = ToolExecution(
            tool_name="send_message_to_target",
            reasoning="test",
            assistant_message=assistant_msg,
            tool_message=tool_msg,
        )
        turn = Turn(
            turn_number=i + 1,
            executions=[target_execution],
            target_interaction=target_execution,
        )
        state.turns.append(turn)


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
    _add_turns_to_state(sample_test_state, 5)

    should_stop, reason = condition.should_stop(sample_test_state)

    assert should_stop is True
    assert "impossible" in reason.lower()


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

    condition = GoalAchievedCondition(
        result=mock_result, max_turns=10, min_turns=8
    )
    _add_turns_to_state(sample_test_state, 5)

    # At 5 turns with min_turns=8, should NOT stop
    should_stop, reason = condition.should_stop(sample_test_state)
    assert should_stop is False


def test_min_turns_allows_stop_after_threshold(sample_test_state):
    """Test that early stopping is allowed after min_turns is reached."""
    mock_result = Mock()
    mock_result.score = 0.9
    mock_result.details = {
        "is_successful": True,
        "reason": "Goal achieved",
    }

    condition = GoalAchievedCondition(
        result=mock_result, max_turns=10, min_turns=5
    )
    _add_turns_to_state(sample_test_state, 5)

    # At 5 turns with min_turns=5, should stop
    should_stop, reason = condition.should_stop(sample_test_state)
    assert should_stop is True
    assert "Goal achieved" in reason


def test_min_turns_capped_at_max_turns(sample_test_state):
    """Test that min_turns cannot exceed max_turns."""
    condition = GoalAchievedCondition(max_turns=10, min_turns=15)

    # min_turns=15 should be capped to max_turns=10
    assert condition._get_min_turns_before_stop() == 10


def test_default_threshold_when_no_min_turns():
    """Test that 80% threshold applies when min_turns is not set."""
    condition = GoalAchievedCondition(max_turns=10)

    # 80% of 10 = 8
    assert condition._get_min_turns_before_stop() == 8


def test_no_floor_when_neither_set():
    """Test fallback to 0 when neither max_turns nor min_turns is set."""
    condition = GoalAchievedCondition()

    assert condition._get_min_turns_before_stop() == 0
