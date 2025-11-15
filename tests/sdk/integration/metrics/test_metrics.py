"""Integration tests for SDK metrics (NumericJudge, ConversationalJudge, etc.)."""

import time

import pytest

from rhesis.sdk.metrics import GoalAchievementJudge, NumericJudge


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
