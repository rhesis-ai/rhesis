"""Tests for Penelope utils module."""

from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest

from rhesis.penelope.utils import (
    GoalAchievedCondition,
    MaxIterationsCondition,
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


def test_max_iterations_condition_initialization():
    """Test MaxIterationsCondition initialization."""
    condition = MaxIterationsCondition(max_iterations=10)

    assert condition.max_iterations == 10


def test_max_iterations_condition_should_not_stop(sample_test_state):
    """Test MaxIterationsCondition doesn't stop before limit."""
    condition = MaxIterationsCondition(max_iterations=10)

    should_stop, reason = condition.should_stop(sample_test_state)

    assert should_stop is False
    assert reason == ""


def test_max_iterations_condition_should_stop(sample_test_state):
    """Test MaxIterationsCondition stops at limit."""
    condition = MaxIterationsCondition(max_iterations=5)

    # Simulate reaching max iterations
    for _ in range(5):
        sample_test_state.current_turn += 1

    should_stop, reason = condition.should_stop(sample_test_state)

    assert should_stop is True
    assert "Maximum iterations" in reason
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


def test_goal_achieved_condition_should_not_stop_goal_not_achieved(sample_test_state):
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
    mock_result.details = {"is_successful": True, "reason": "Goal successfully achieved"}

    condition = GoalAchievedCondition(result=mock_result)

    should_stop, reason = condition.should_stop(sample_test_state)

    assert should_stop is True
    assert "Goal achieved" in reason
    assert "successfully achieved" in reason


def test_goal_achieved_condition_should_stop_goal_impossible(sample_test_state):
    """Test GoalAchievedCondition stops when goal is impossible (low score after 5+ turns)."""
    from rhesis.penelope.context import ToolExecution, Turn
    from rhesis.penelope.schemas import AssistantMessage, FunctionCall, MessageToolCall, ToolMessage

    mock_result = Mock()
    mock_result.score = 0.2  # Low score
    mock_result.details = {"is_successful": False, "reason": "Cannot achieve goal"}

    condition = GoalAchievedCondition(result=mock_result)

    # Simulate 5+ turns by adding turns to state
    for i in range(5):
        assistant_msg = AssistantMessage(
                content=f"Turn {i + 1}",
                tool_calls=[
                    MessageToolCall(
                        id=f"call_{i}",
                        type="function",
                    function=FunctionCall(name="send_message_to_target", arguments="{}"),
                    )
                ],
        )
        
        tool_msg = ToolMessage(tool_call_id=f"call_{i}", name="send_message_to_target", content="result")
        
        # Create a ToolExecution for the target interaction
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
        sample_test_state.turns.append(turn)

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


# Tests removed: format_tool_schema_for_llm is no longer needed
# Tool schemas are self-documenting via the ToolCall Pydantic schema
