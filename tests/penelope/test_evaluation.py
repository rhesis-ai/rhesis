"""Tests for goal evaluation logic (inlined in agent.py)."""

import json
from unittest.mock import Mock

import pytest

from rhesis.penelope.context import TestContext, TestState, ToolExecution, Turn
from rhesis.penelope.schemas import (
    AssistantMessage as PenelopeAssistantMessage,
)
from rhesis.penelope.schemas import (
    FunctionCall,
    MessageToolCall,
    ToolMessage,
)
from rhesis.sdk.metrics.base import MetricResult
from rhesis.sdk.metrics.conversational import ConversationHistory


def _add_conversation_turn(state, message, response, turn_number=None):
    """Add a turn to state that produces a conversation entry."""
    if turn_number is None:
        turn_number = len(state.turns) + 1
    tool_result = json.dumps(
        {
            "success": True,
            "output": {"response": response},
        }
    )
    assistant_msg = PenelopeAssistantMessage(
        content="Test",
        tool_calls=[
            MessageToolCall(
                id=f"call_turn_{turn_number}",
                type="function",
                function=FunctionCall(
                    name="send_message_to_target",
                    arguments=json.dumps({"message": message}),
                ),
            )
        ],
    )
    tool_msg = ToolMessage(
        tool_call_id=f"call_turn_{turn_number}",
        name="send_message_to_target",
        content=tool_result,
    )
    execution = ToolExecution(
        tool_name="send_message_to_target",
        reasoning="Test",
        assistant_message=assistant_msg,
        tool_message=tool_msg,
    )
    turn = Turn(
        turn_number=turn_number,
        executions=[execution],
        target_interaction=execution,
    )
    state.turns.append(turn)


@pytest.fixture
def mock_goal_metric():
    """Mock goal metric for testing."""
    from rhesis.sdk.metrics.providers.native import GoalAchievementJudge

    mock_metric = Mock(spec=GoalAchievementJudge)
    mock_metric.name = "test_metric"
    mock_metric.is_goal_achievement_metric = True
    mock_metric.evaluate = Mock(
        return_value=MetricResult(
            score=0.85,
            details={
                "is_successful": True,
                "reason": "Goal achieved",
                "name": "test_metric",
            },
        )
    )
    return mock_metric


@pytest.fixture
def test_state():
    """Create test state with one conversation turn."""
    context = TestContext(
        target_id="test",
        target_type="test",
        instructions="Test instructions",
        goal="Test goal",
    )
    state = TestState(context=context)
    _add_conversation_turn(state, "Hello", "Hi there")
    return state


@pytest.fixture
def empty_state():
    """Create test state with empty conversation."""
    context = TestContext(
        target_id="test",
        target_type="test",
        instructions="Test",
        goal="Test goal",
    )
    return TestState(context=context)


def _evaluate_goal(goal_metric, state, goal, instructions=""):
    """
    Replicate the inlined goal evaluation logic from agent.py.

    This is the exact logic that was previously in GoalEvaluator.evaluate().
    """
    conversation = state.get_conversation()
    if len(conversation) < 1:
        return MetricResult(
            score=0.0,
            details={
                "is_successful": False,
                "confidence": 0.0,
                "reason": "Insufficient conversation (< 1 turn)",
            },
        )
    return goal_metric.evaluate(
        conversation_history=conversation,
        goal=goal,
        instructions=instructions,
    )


class TestGoalEvaluation:
    """Tests for the inlined goal evaluation logic."""

    def test_evaluate_calls_goal_metric(self, mock_goal_metric, test_state):
        """Test evaluate calls goal_metric.evaluate with conversation."""
        _evaluate_goal(mock_goal_metric, test_state, "Test goal")

        mock_goal_metric.evaluate.assert_called_once()
        call_args = mock_goal_metric.evaluate.call_args
        assert "conversation_history" in call_args[1]
        assert isinstance(call_args[1]["conversation_history"], ConversationHistory)
        assert call_args[1]["goal"] == "Test goal"

    def test_evaluate_returns_metric_result(self, mock_goal_metric, test_state):
        """Test evaluate returns MetricResult from goal_metric."""
        result = _evaluate_goal(mock_goal_metric, test_state, "Test goal")

        assert isinstance(result, MetricResult)
        assert result.score == 0.85
        assert result.details["is_successful"] is True
        assert result.details["reason"] == "Goal achieved"

    def test_evaluate_with_empty_conversation(self, mock_goal_metric, empty_state):
        """Test evaluate with empty conversation returns insufficient data."""
        result = _evaluate_goal(mock_goal_metric, empty_state, "Test goal")

        mock_goal_metric.evaluate.assert_not_called()
        assert isinstance(result, MetricResult)
        assert result.score == 0.0
        assert result.details["is_successful"] is False
        assert "Insufficient conversation" in result.details["reason"]

    def test_evaluate_with_instructions(self, mock_goal_metric, test_state):
        """Test evaluate passes instructions to goal_metric."""
        _evaluate_goal(mock_goal_metric, test_state, "Test goal", instructions="Do X then Y")

        call_args = mock_goal_metric.evaluate.call_args
        assert call_args[1]["instructions"] == "Do X then Y"

    def test_evaluate_with_no_goal(self, mock_goal_metric, test_state):
        """Test evaluate with None as goal."""
        _evaluate_goal(mock_goal_metric, test_state, None)

        mock_goal_metric.evaluate.assert_called_once()
        call_args = mock_goal_metric.evaluate.call_args
        assert call_args[1]["goal"] is None


class TestGoalEvaluationEdgeCases:
    """Tests for edge cases in goal evaluation."""

    def test_evaluate_handles_metric_errors(self, mock_goal_metric, test_state):
        """Test evaluate propagates errors from goal_metric."""
        mock_goal_metric.evaluate.side_effect = RuntimeError("Metric error")

        with pytest.raises(RuntimeError, match="Metric error"):
            _evaluate_goal(mock_goal_metric, test_state, "Test goal")

    def test_evaluate_with_long_conversation(self, mock_goal_metric):
        """Test evaluate with long conversation history."""
        context = TestContext(
            target_id="test",
            target_type="test",
            instructions="Test",
            goal="Test goal",
        )
        state = TestState(context=context)

        for i in range(100):
            _add_conversation_turn(state, f"Message {i}", f"Response {i}")

        _evaluate_goal(mock_goal_metric, state, "Test goal")

        mock_goal_metric.evaluate.assert_called_once()
        call_args = mock_goal_metric.evaluate.call_args
        assert len(call_args[1]["conversation_history"].messages) == 100

    def test_evaluate_preserves_metric_details(self, test_state):
        """Test evaluate preserves all details from metric result."""
        mock_metric = Mock()
        mock_metric.name = "detailed_metric"
        mock_metric.evaluate = Mock(
            return_value=MetricResult(
                score=0.75,
                details={
                    "is_successful": True,
                    "reason": "Detailed reason",
                    "name": "detailed_metric",
                    "criteria_evaluations": [{"criterion": "A", "met": True}],
                    "all_criteria_met": True,
                    "confidence": 0.9,
                    "custom_field": "custom_value",
                },
            )
        )

        result = _evaluate_goal(mock_metric, test_state, "Test goal")

        assert result.score == 0.75
        assert result.details["is_successful"] is True
        assert result.details["reason"] == "Detailed reason"
        assert "criteria_evaluations" in result.details
        assert result.details["custom_field"] == "custom_value"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
