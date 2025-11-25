"""Integration tests for SDK metrics (NumericJudge, ConversationalJudge, etc.)."""

import time

import pytest

from rhesis.sdk.metrics import DeepEvalTurnRelevancy, GoalAchievementJudge, NumericJudge


def test_push_numeric_judge(docker_compose_test_env, db_cleanup):
    """Test pushing a NumericJudge to the backend."""
    # Use unique name to avoid conflicts with existing backend data
    unique_name = f"numeric-judge-{int(time.time() * 1000)}"
    judge = NumericJudge(name=unique_name, evaluation_prompt="test-evaluation-prompt")
    judge.push()


def test_push_pull_numeric_judge(docker_compose_test_env, db_cleanup):
    """Test pushing and pulling a NumericJudge from the backend."""
    # Use unique name to avoid conflicts with existing backend data
    unique_name = f"numeric-judge-{int(time.time() * 1000)}"
    judge = NumericJudge(name=unique_name, evaluation_prompt="test-evaluation-prompt")
    judge.push()

    judge = NumericJudge.pull(name=unique_name)

    with pytest.raises(ValueError):
        judge.pull(name="non-existent-name")


def test_push_conversational_judge(docker_compose_test_env, db_cleanup):
    """Test pushing a conversational judge (GoalAchievementJudge) to the backend."""
    # Use unique name to avoid conflicts with existing backend data
    unique_name = f"goal-judge-{int(time.time() * 1000)}"
    judge = GoalAchievementJudge(
        name=unique_name,
        description="Test goal achievement judge",
        evaluation_prompt="Evaluate if the conversation achieves its goal",
        threshold=0.7,
    )
    judge.push()


def test_push_pull_conversational_judge(docker_compose_test_env, db_cleanup):
    """Test pushing and pulling a conversational judge from the backend."""
    # Use unique name to avoid conflicts with existing backend data
    unique_name = f"goal-judge-{int(time.time() * 1000)}"

    # Create and push the judge
    judge = GoalAchievementJudge(
        name=unique_name,
        description="Test goal achievement judge for push/pull",
        evaluation_prompt="Evaluate conversation goal achievement",
        evaluation_steps="Step 1: Analyze goal\nStep 2: Evaluate progress",
        threshold=0.6,
        min_score=0.0,
        max_score=1.0,
    )
    judge.push()

    # Pull the judge back
    pulled_judge = GoalAchievementJudge.pull(name=unique_name)

    # Verify the pulled judge has the same configuration
    assert pulled_judge.name == unique_name
    assert pulled_judge.description == "Test goal achievement judge for push/pull"
    assert pulled_judge.threshold == 0.6
    assert pulled_judge.min_score == 0.0
    assert pulled_judge.max_score == 1.0

    # Test that pulling non-existent judge raises error
    with pytest.raises(ValueError):
        GoalAchievementJudge.pull(name="non-existent-conversational-judge")


@pytest.mark.skip(reason="Requires actual LLM interaction with DeepEval")
def test_turn_relevancy_evaluate(sample_conversation):
    """Test Turn Relevancy evaluation."""
    metric = DeepEvalTurnRelevancy(threshold=0.5)

    result = metric.evaluate(conversation_history=sample_conversation)

    assert result.score is not None
    assert isinstance(result.score, (int, float))
    assert "is_successful" in result.details
    assert "reason" in result.details
    assert "threshold" in result.details
    assert result.details["threshold"] == 0.5


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
