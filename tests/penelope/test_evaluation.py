"""Tests for Penelope evaluation module."""

from unittest.mock import Mock

import pytest

from rhesis.penelope.context import TestContext, TestState
from rhesis.penelope.evaluation import GoalEvaluator
from rhesis.sdk.metrics.base import MetricResult
from rhesis.sdk.metrics.conversational import AssistantMessage, ConversationHistory, UserMessage
from rhesis.sdk.metrics.providers.native import GoalAchievementJudge


@pytest.fixture
def mock_model():
    """Mock LLM model for testing."""
    from rhesis.sdk.models.base import BaseLLM

    mock = Mock(spec=BaseLLM)
    mock.get_model_name.return_value = "mock-model"
    return mock


@pytest.fixture
def mock_goal_metric(mock_model):
    """Mock goal metric for testing."""
    mock_metric = Mock(spec=GoalAchievementJudge)
    mock_metric.name = "test_metric"
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

    # Add conversation history
    state.conversation = ConversationHistory.from_messages(
        [
            UserMessage(role="user", content="Hello"),
            AssistantMessage(role="assistant", content="Hi there"),
        ]
    )

    return state


class TestGoalEvaluatorInitialization:
    """Tests for GoalEvaluator initialization."""

    def test_init_with_goal_metric(self, mock_goal_metric):
        """Test GoalEvaluator initialization with goal_metric."""
        evaluator = GoalEvaluator(goal_metric=mock_goal_metric)

        assert evaluator.goal_metric == mock_goal_metric

    def test_init_requires_goal_metric(self):
        """Test GoalEvaluator requires goal_metric parameter."""
        # Should work with positional arg
        mock_metric = Mock()
        evaluator = GoalEvaluator(mock_metric)
        assert evaluator.goal_metric == mock_metric


class TestGoalEvaluatorEvaluate:
    """Tests for GoalEvaluator.evaluate method."""

    def test_evaluate_calls_goal_metric(self, mock_goal_metric, test_state):
        """Test evaluate calls goal_metric.evaluate with conversation."""
        evaluator = GoalEvaluator(goal_metric=mock_goal_metric)

        result = evaluator.evaluate(test_state, "Test goal")

        # Verify goal_metric.evaluate was called
        mock_goal_metric.evaluate.assert_called_once()
        call_args = mock_goal_metric.evaluate.call_args

        # Check conversation_history was passed
        assert "conversation_history" in call_args[1]
        assert isinstance(call_args[1]["conversation_history"], ConversationHistory)

        # Check goal was passed
        assert "goal" in call_args[1]
        assert call_args[1]["goal"] == "Test goal"

    def test_evaluate_returns_metric_result(self, mock_goal_metric, test_state):
        """Test evaluate returns MetricResult from goal_metric."""
        evaluator = GoalEvaluator(goal_metric=mock_goal_metric)

        result = evaluator.evaluate(test_state, "Test goal")

        # Verify result is MetricResult with expected values
        assert isinstance(result, MetricResult)
        assert result.score == 0.85
        assert result.details["is_successful"] is True
        assert result.details["reason"] == "Goal achieved"

    def test_evaluate_with_empty_conversation(self, mock_goal_metric):
        """Test evaluate with empty conversation returns insufficient data result."""
        context = TestContext(
            target_id="test",
            target_type="test",
            instructions="Test",
            goal="Test goal",
        )
        state = TestState(context=context)
        # state.conversation is empty ConversationHistory by default

        evaluator = GoalEvaluator(goal_metric=mock_goal_metric)

        result = evaluator.evaluate(state, "Test goal")

        # Should not call evaluate with insufficient data
        mock_goal_metric.evaluate.assert_not_called()
        assert isinstance(result, MetricResult)
        assert result.score == 0.0
        assert result.details["is_successful"] is False
        assert "Insufficient conversation" in result.details["reason"]

    def test_evaluate_with_no_goal(self, mock_goal_metric, test_state):
        """Test evaluate with None as goal (infer from conversation)."""
        evaluator = GoalEvaluator(goal_metric=mock_goal_metric)

        result = evaluator.evaluate(test_state, None)

        # Verify evaluate was called with None goal
        mock_goal_metric.evaluate.assert_called_once()
        call_args = mock_goal_metric.evaluate.call_args
        assert call_args[1]["goal"] is None

    def test_evaluate_with_real_goal_achievement_judge(self, mock_model, test_state):
        """Test evaluate with real GoalAchievementJudge instance."""
        # Create real GoalAchievementJudge
        goal_judge = GoalAchievementJudge(
            name="real_judge",
            model=mock_model,
            threshold=0.7,
        )

        # Mock the model's generate method to return structured response
        mock_model.generate.return_value = {
            "score": 0.8,
            "reason": "Goal partially achieved",
            "criteria_evaluations": [
                {
                    "criterion": "Test criterion",
                    "met": True,
                    "evidence": "Test evidence",
                    "relevant_turns": [1],
                }
            ],
            "all_criteria_met": True,
            "confidence": 0.85,
        }

        evaluator = GoalEvaluator(goal_metric=goal_judge)

        # Should not raise errors
        result = evaluator.evaluate(test_state, "Test goal")

        assert isinstance(result, MetricResult)
        assert hasattr(result, "score")
        assert hasattr(result, "details")


class TestGoalEvaluatorEdgeCases:
    """Tests for edge cases in GoalEvaluator."""

    def test_evaluate_handles_metric_errors_gracefully(self, mock_goal_metric, test_state):
        """Test evaluate handles errors from goal_metric gracefully."""
        # Make goal_metric raise an exception
        mock_goal_metric.evaluate.side_effect = RuntimeError("Metric error")

        evaluator = GoalEvaluator(goal_metric=mock_goal_metric)

        # Should propagate the error (or handle it if error handling is added)
        with pytest.raises(RuntimeError, match="Metric error"):
            evaluator.evaluate(test_state, "Test goal")

    def test_evaluate_with_long_conversation(self, mock_goal_metric):
        """Test evaluate with long conversation history."""
        context = TestContext(
            target_id="test",
            target_type="test",
            instructions="Test",
            goal="Test goal",
        )
        state = TestState(context=context)

        # Create long conversation
        messages = []
        for i in range(100):
            messages.append(UserMessage(role="user", content=f"Message {i}"))
            messages.append(AssistantMessage(role="assistant", content=f"Response {i}"))

        state.conversation = ConversationHistory.from_messages(messages)

        evaluator = GoalEvaluator(goal_metric=mock_goal_metric)

        result = evaluator.evaluate(state, "Test goal")

        # Should handle long conversation
        mock_goal_metric.evaluate.assert_called_once()
        call_args = mock_goal_metric.evaluate.call_args
        assert len(call_args[1]["conversation_history"].messages) == 200

    def test_evaluate_preserves_metric_details(self, mock_model, test_state):
        """Test evaluate preserves all details from metric result."""
        # Create metric with detailed response
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

        evaluator = GoalEvaluator(goal_metric=mock_metric)

        result = evaluator.evaluate(test_state, "Test goal")

        # Verify all details are preserved
        assert result.score == 0.75
        assert result.details["is_successful"] is True
        assert result.details["reason"] == "Detailed reason"
        assert "criteria_evaluations" in result.details
        assert result.details["custom_field"] == "custom_value"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

