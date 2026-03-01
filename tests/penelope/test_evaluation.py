"""Tests for goal evaluation logic (inlined in agent.py)."""

from unittest.mock import Mock

import pytest

from rhesis.penelope.context import TestContext, TestState
from rhesis.sdk.metrics.base import MetricResult
from rhesis.sdk.metrics.conversational import AssistantMessage, ConversationHistory, UserMessage


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
    """Create test state with conversation."""
    context = TestContext(
        target_id="test",
        target_type="test",
        instructions="Test instructions",
        goal="Test goal",
    )
    state = TestState(context=context)
    state.conversation = ConversationHistory.from_messages(
        [
            UserMessage(role="user", content="Hello"),
            AssistantMessage(role="assistant", content="Hi there"),
        ]
    )
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
    if len(state.conversation) < 1:
        return MetricResult(
            score=0.0,
            details={
                "is_successful": False,
                "confidence": 0.0,
                "reason": "Insufficient conversation (< 1 turn)",
            },
        )
    return goal_metric.evaluate(
        conversation_history=state.conversation,
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
        _evaluate_goal(
            mock_goal_metric, test_state, "Test goal", instructions="Do X then Y"
        )

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

        messages = []
        for i in range(100):
            messages.append(UserMessage(role="user", content=f"Message {i}"))
            messages.append(
                AssistantMessage(role="assistant", content=f"Response {i}")
            )
        state.conversation = ConversationHistory.from_messages(messages)

        _evaluate_goal(mock_goal_metric, state, "Test goal")

        mock_goal_metric.evaluate.assert_called_once()
        call_args = mock_goal_metric.evaluate.call_args
        assert len(call_args[1]["conversation_history"].messages) == 200

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
