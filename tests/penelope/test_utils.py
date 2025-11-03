"""Tests for Penelope utils module."""

import pytest
from datetime import datetime, timedelta
from rhesis.penelope.utils import (
    StoppingCondition,
    MaxIterationsCondition,
    TimeoutCondition,
    GoalAchievedCondition,
    format_tool_schema_for_llm,
)
from rhesis.penelope.context import GoalProgress


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
    progress = GoalProgress(
        goal_achieved=False,
        goal_impossible=False,
        confidence=0.5,
        reasoning="Testing",
    )

    condition = GoalAchievedCondition(progress=progress)

    assert condition.progress == progress


def test_goal_achieved_condition_initialization_without_progress():
    """Test GoalAchievedCondition can be initialized without progress."""
    condition = GoalAchievedCondition()

    assert condition.progress is None


def test_goal_achieved_condition_should_not_stop_no_progress(sample_test_state):
    """Test GoalAchievedCondition doesn't stop without progress."""
    condition = GoalAchievedCondition()

    should_stop, reason = condition.should_stop(sample_test_state)

    assert should_stop is False
    assert reason == ""


def test_goal_achieved_condition_should_not_stop_goal_not_achieved(sample_test_state):
    """Test GoalAchievedCondition doesn't stop if goal not achieved."""
    progress = GoalProgress(
        goal_achieved=False,
        goal_impossible=False,
        confidence=0.5,
        reasoning="Still working",
    )

    condition = GoalAchievedCondition(progress=progress)

    should_stop, reason = condition.should_stop(sample_test_state)

    assert should_stop is False
    assert reason == ""


def test_goal_achieved_condition_should_stop_goal_achieved(sample_test_state):
    """Test GoalAchievedCondition stops when goal achieved."""
    progress = GoalProgress(
        goal_achieved=True,
        goal_impossible=False,
        confidence=0.9,
        reasoning="Goal successfully achieved",
    )

    condition = GoalAchievedCondition(progress=progress)

    should_stop, reason = condition.should_stop(sample_test_state)

    assert should_stop is True
    assert "Goal achieved" in reason
    assert "successfully achieved" in reason


def test_goal_achieved_condition_should_stop_goal_impossible(sample_test_state):
    """Test GoalAchievedCondition stops when goal is impossible."""
    progress = GoalProgress(
        goal_achieved=False,
        goal_impossible=True,
        confidence=0.8,
        reasoning="Cannot achieve goal",
    )

    condition = GoalAchievedCondition(progress=progress)

    should_stop, reason = condition.should_stop(sample_test_state)

    assert should_stop is True
    assert "impossible" in reason.lower()


def test_goal_achieved_condition_update_progress():
    """Test GoalAchievedCondition can update progress."""
    condition = GoalAchievedCondition()

    assert condition.progress is None

    new_progress = GoalProgress(
        goal_achieved=True,
        goal_impossible=False,
        confidence=0.9,
        reasoning="Updated",
    )

    condition.update_progress(new_progress)

    assert condition.progress == new_progress


def test_format_tool_schema_for_llm(mock_tool):
    """Test format_tool_schema_for_llm function."""
    tools = [mock_tool]

    formatted = format_tool_schema_for_llm(tools)

    assert isinstance(formatted, str)
    assert "mock_tool" in formatted
    assert "Mock tool for testing" in formatted


def test_format_tool_schema_for_llm_multiple_tools(mock_tool):
    """Test format_tool_schema_for_llm with multiple tools."""

    class AnotherMockTool:
        @property
        def name(self):
            return "another_tool"

        @property
        def description(self):
            return "Another tool description"

        @property
        def parameters(self):
            return []

    tools = [mock_tool, AnotherMockTool()]

    formatted = format_tool_schema_for_llm(tools)

    assert "mock_tool" in formatted
    assert "another_tool" in formatted
    assert "Mock tool for testing" in formatted
    assert "Another tool description" in formatted


def test_format_tool_schema_for_llm_includes_parameters(mock_tool):
    """Test format_tool_schema_for_llm includes parameter information."""
    tools = [mock_tool]

    formatted = format_tool_schema_for_llm(tools)

    # Should include parameter name and type
    assert "param1" in formatted
    assert "string" in formatted

