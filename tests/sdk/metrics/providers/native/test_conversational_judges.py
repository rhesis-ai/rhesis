"""Tests for native conversational judges."""

from unittest.mock import MagicMock

import pytest

from rhesis.sdk.metrics import ConversationHistory, GoalAchievementJudge
from rhesis.sdk.metrics.base import MetricType, ScoreType
from rhesis.sdk.models import BaseLLM


@pytest.fixture
def mock_model():
    """Create a mock LLM model for testing."""
    model = MagicMock(spec=BaseLLM)
    model.get_model_name.return_value = "mock-model"
    return model


@pytest.fixture
def sample_conversation():
    """Create a sample conversation for testing."""
    return ConversationHistory.from_messages(
        [
            {"role": "user", "content": "I need help finding a new insurance policy."},
            {
                "role": "assistant",
                "content": "I'd be happy to help! What type of insurance are you looking for?",
            },
            {"role": "user", "content": "Auto insurance for my new car."},
            {
                "role": "assistant",
                "content": "Great! I can help you compare our auto insurance plans. "
                "We offer liability, collision, and comprehensive coverage.",
            },
            {
                "role": "user",
                "content": "What's the difference between collision and comprehensive?",
            },
            {
                "role": "assistant",
                "content": "Collision covers damage from accidents with other vehicles or objects. "
                "Comprehensive covers non-collision events like theft, vandalism, or natural disasters.",
            },
        ]
    )


def test_goal_achievement_judge_initialization(mock_model):
    """Test GoalAchievementJudge initialization with default values."""
    judge = GoalAchievementJudge(model=mock_model)

    assert judge.name == "goal_achievement"
    assert judge.metric_type == MetricType.CONVERSATIONAL
    assert judge.score_type == ScoreType.NUMERIC
    assert judge.min_score == 0.0
    assert judge.max_score == 1.0
    assert judge.threshold == 0.5
    # When evaluation_prompt is None, template uses conditional rendering for defaults
    assert judge.evaluation_prompt is None
    assert judge.evaluation_steps is None
    assert judge.reasoning is None


def test_goal_achievement_judge_custom_initialization(mock_model):
    """Test GoalAchievementJudge with custom parameters."""
    judge = GoalAchievementJudge(
        name="custom_goal_metric",
        description="Custom goal achievement metric",
        min_score=0.0,
        max_score=10.0,
        threshold=7.0,
        evaluation_prompt="Custom evaluation prompt",
        model=mock_model,
    )

    assert judge.name == "custom_goal_metric"
    assert judge.description == "Custom goal achievement metric"
    assert judge.min_score == 0.0
    assert judge.max_score == 10.0
    assert judge.threshold == 7.0
    assert judge.evaluation_prompt == "Custom evaluation prompt"


def test_goal_achievement_judge_score_range_validation(mock_model):
    """Test that score range validation works correctly."""
    # Test with only min_score
    with pytest.raises(ValueError, match="Only min_score was set"):
        GoalAchievementJudge(min_score=0.0, model=mock_model)

    # Test with only max_score
    with pytest.raises(ValueError, match="Only max_score was set"):
        GoalAchievementJudge(max_score=1.0, model=mock_model)

    # Test with min_score == max_score
    with pytest.raises(ValueError, match="cannot be the same"):
        GoalAchievementJudge(min_score=0.5, max_score=0.5, model=mock_model)

    # Test with min_score > max_score
    with pytest.raises(ValueError, match="cannot be greater than"):
        GoalAchievementJudge(min_score=1.0, max_score=0.0, model=mock_model)


def test_goal_achievement_judge_threshold_validation(mock_model):
    """Test that threshold validation works correctly."""
    # Test with threshold outside range
    with pytest.raises(ValueError, match="Threshold must be between"):
        GoalAchievementJudge(min_score=0.0, max_score=1.0, threshold=2.0, model=mock_model)

    with pytest.raises(ValueError, match="Threshold must be between"):
        GoalAchievementJudge(min_score=0.0, max_score=1.0, threshold=-1.0, model=mock_model)


def test_goal_achievement_judge_validation(mock_model, sample_conversation):
    """Test input validation for evaluate method."""
    judge = GoalAchievementJudge(model=mock_model)

    # Test with invalid conversation_history type
    with pytest.raises(ValueError, match="must be a ConversationHistory instance"):
        judge.evaluate(conversation_history="not a conversation")  # type: ignore

    # Test with empty conversation
    empty_conversation = ConversationHistory.from_messages([])
    with pytest.raises(ValueError, match="cannot be empty"):
        judge.evaluate(conversation_history=empty_conversation)

    # Test with invalid goal type
    with pytest.raises(ValueError, match="goal must be a string"):
        judge.evaluate(conversation_history=sample_conversation, goal=123)  # type: ignore


def test_goal_achievement_judge_prompt_generation(mock_model, sample_conversation):
    """Test that the goal-achievement-specific template is generated correctly with defaults."""
    judge = GoalAchievementJudge(model=mock_model)

    # Generate prompt (evaluation_prompt is None, so template uses defaults)
    prompt = judge._get_prompt_template(
        conversation_history=sample_conversation,
        goal="Customer finds suitable auto insurance",
    )

    # Check that prompt contains goal-achievement-specific template elements
    assert "evaluate whether the conversation successfully achieved its stated goal" in prompt
    assert "Customer finds suitable auto insurance" in prompt
    assert "6 turns" in prompt  # Sample conversation has 6 turns
    assert "Turn 1 [user]" in prompt
    assert "Turn 2 [assistant]" in prompt
    # Verify goal-achievement-specific defaults are rendered
    assert "Break down the goal into specific measurable criteria" in prompt
    assert "Understanding" in prompt  # From default evaluation criteria
    assert "Relevance" in prompt  # From default evaluation criteria
    assert "Progress" in prompt  # From default evaluation criteria
    assert "Completeness" in prompt  # From default evaluation criteria
    assert "Goal Clarity" in prompt  # From default reasoning guidelines
    assert "Criterion-based Assessment" in prompt  # From default reasoning guidelines


def test_goal_achievement_judge_format_conversation(mock_model, sample_conversation):
    """Test conversation formatting."""
    judge = GoalAchievementJudge(model=mock_model)

    formatted = judge._format_conversation(sample_conversation)

    # Check that formatting is correct
    assert "Turn 1 [user]:" in formatted
    assert "Turn 2 [assistant]:" in formatted
    assert "Turn 6 [assistant]:" in formatted
    assert "I need help finding a new insurance policy" in formatted


@pytest.mark.skip(reason="Requires actual LLM interaction")
def test_goal_achievement_judge_evaluate_real(sample_conversation):
    """Test evaluation with a real LLM (skipped in normal test runs)."""
    from rhesis.sdk.models import VertexAILLM

    judge = GoalAchievementJudge(
        model=VertexAILLM(model_name="gemini-2.0-flash"),
        threshold=0.7,
    )

    result = judge.evaluate(
        conversation_history=sample_conversation,
        goal="Customer learns about auto insurance options",
    )

    assert result.score is not None
    assert 0.0 <= result.score <= 1.0
    assert "reason" in result.details
    assert "is_successful" in result.details


def test_goal_achievement_judge_evaluate_with_mock(mock_model, sample_conversation):
    """Test evaluate method with mocked LLM response."""
    judge = GoalAchievementJudge(model=mock_model, threshold=0.7)

    # Mock the LLM response with all required fields
    mock_model.generate.return_value = {
        "score": 0.85,
        "reason": "The conversation successfully achieves the goal. "
        "The assistant provides clear information about auto insurance options.",
        "criteria_evaluations": [
            {
                "criterion": "Understanding customer needs",
                "met": True,
                "evidence": "Assistant asked clarifying questions about insurance needs",
                "relevant_turns": [1, 2],
            },
            {
                "criterion": "Providing comprehensive information",
                "met": True,
                "evidence": "Assistant explained auto insurance options clearly",
                "relevant_turns": [3, 4, 5],
            },
        ],
        "all_criteria_met": True,
        "confidence": 0.9,
    }

    result = judge.evaluate(
        conversation_history=sample_conversation,
        goal="Customer learns about auto insurance options",
    )

    assert result.score == 0.85
    assert result.details["is_successful"] is True
    assert result.details["reason"] == (
        "The conversation successfully achieves the goal. "
        "The assistant provides clear information about auto insurance options."
    )
    assert result.details["turn_count"] == 6
    assert result.details["goal"] == "Customer learns about auto insurance options"


def test_goal_achievement_judge_evaluate_below_threshold(mock_model, sample_conversation):
    """Test evaluation when score is below threshold."""
    judge = GoalAchievementJudge(model=mock_model, threshold=0.9)

    # Mock a lower score with partial criteria met
    mock_model.generate.return_value = {
        "score": 0.6,
        "reason": "The goal was only partially achieved.",
        "criteria_evaluations": [
            {
                "criterion": "Information provided",
                "met": True,
                "evidence": "Basic insurance information was provided",
                "relevant_turns": [1, 2],
            },
            {
                "criterion": "Purchase completion",
                "met": False,
                "evidence": "Customer did not complete the purchase process",
                "relevant_turns": [3, 4],
            },
        ],
        "all_criteria_met": False,
        "confidence": 0.8,
    }

    result = judge.evaluate(
        conversation_history=sample_conversation,
        goal="Customer completes insurance purchase",
    )

    assert result.score == 0.6
    assert result.details["is_successful"] is False


def test_goal_achievement_judge_evaluate_without_goal(mock_model, sample_conversation):
    """Test evaluation without explicit goal."""
    judge = GoalAchievementJudge(model=mock_model)

    mock_model.generate.return_value = {
        "score": 0.75,
        "reason": "The conversation shows good progress toward an implicit goal.",
        "criteria_evaluations": [
            {
                "criterion": "Conversational flow",
                "met": True,
                "evidence": "Natural conversation progression",
                "relevant_turns": [1, 2, 3],
            },
        ],
        "all_criteria_met": True,
        "confidence": 0.7,
    }

    result = judge.evaluate(conversation_history=sample_conversation)

    assert result.score == 0.75
    assert result.details["goal"] == "Infer from conversation"


def test_goal_achievement_judge_evaluate_error_handling(mock_model, sample_conversation):
    """Test error handling in evaluate method."""
    judge = GoalAchievementJudge(model=mock_model)

    # Mock an exception
    mock_model.generate.side_effect = Exception("LLM API error")

    result = judge.evaluate(conversation_history=sample_conversation)

    assert result.score == 0.0  # Default score on error
    assert result.details["is_successful"] is False
    assert "error" in result.details
    assert "LLM API error" in result.details["error"]
