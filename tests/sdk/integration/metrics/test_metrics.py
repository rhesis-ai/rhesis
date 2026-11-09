"""Integration tests for SDK metrics (NumericJudge, ConversationalJudge, etc.)."""

import time

import pytest

from rhesis.sdk.metrics import (
    CategoricalJudge,
    DeepEvalTurnRelevancy,
    GoalAchievementJudge,
    NumericJudge,
)

# ---------------------------------------------------------------------------
# NumericJudge
# ---------------------------------------------------------------------------


class TestNumericJudgePush:
    """Tests for NumericJudge push lifecycle."""

    def test_push_sets_id(self, docker_compose_test_env, db_cleanup):
        """Push should assign a backend id to the metric."""
        name = f"numeric-{int(time.time() * 1000)}"
        judge = NumericJudge(name=name, evaluation_prompt="prompt")
        assert judge.id is None
        judge.push()
        assert judge.id is not None

    def test_push_pull_preserves_all_fields(self, docker_compose_test_env, db_cleanup):
        """All config fields should survive a push-pull round trip."""
        name = f"numeric-{int(time.time() * 1000)}"
        judge = NumericJudge(
            name=name,
            description="A test metric",
            evaluation_prompt="Evaluate correctness",
            evaluation_steps="Step 1\nStep 2",
            reasoning="Check factual accuracy",
            min_score=0.0,
            max_score=10.0,
            threshold=7.0,
        )
        judge.push()

        pulled = NumericJudge.pull(name=name)
        assert pulled.id == judge.id
        assert pulled.name == name
        assert pulled.config.description == "A test metric"
        assert pulled.config.evaluation_prompt == "Evaluate correctness"
        assert pulled.config.evaluation_steps == "Step 1\nStep 2"
        assert pulled.config.reasoning == "Check factual accuracy"
        assert pulled.config.min_score == 0.0
        assert pulled.config.max_score == 10.0
        assert pulled.config.threshold == 7.0

    def test_push_pull_preserves_the_target(self, docker_compose_test_env, db_cleanup):
        """The target should survive a push-pull round trip."""
        name = f"numeric-target-{int(time.time() * 1000)}"
        judge = NumericJudge(
            name=name,
            evaluation_prompt="prompt",
            target={"on": "tool_call", "name": "issue_refund"},
        )
        judge.push()

        pulled = NumericJudge.pull(name=name)
        assert pulled.config.target == {"on": "tool_call", "name": "issue_refund"}

    def test_push_update_persists_changes(self, docker_compose_test_env, db_cleanup):
        """Modifying a pushed metric and re-pushing should update, not create."""
        name = f"numeric-{int(time.time() * 1000)}"
        judge = NumericJudge(name=name, evaluation_prompt="original")
        judge.push()
        original_id = judge.id

        judge.config.evaluation_prompt = "updated"
        judge.push()
        assert judge.id == original_id

        pulled = NumericJudge.pull(name=name)
        assert pulled.id == original_id
        assert pulled.config.evaluation_prompt == "updated"

    def test_push_update_preserves_unchanged_fields(self, docker_compose_test_env, db_cleanup):
        """Fields not modified between pushes should be preserved."""
        name = f"numeric-{int(time.time() * 1000)}"
        judge = NumericJudge(
            name=name,
            description="keep me",
            evaluation_prompt="original",
            min_score=0.0,
            max_score=5.0,
            threshold=3.0,
        )
        judge.push()

        judge.config.evaluation_prompt = "changed"
        judge.push()

        pulled = NumericJudge.pull(name=name)
        assert pulled.config.description == "keep me"
        assert pulled.config.min_score == 0.0
        assert pulled.config.max_score == 5.0
        assert pulled.config.threshold == 3.0

    def test_pull_nonexistent_raises(self, docker_compose_test_env, db_cleanup):
        """Pulling a metric that doesn't exist should raise ValueError."""
        with pytest.raises(ValueError):
            NumericJudge.pull(name="does-not-exist")


# ---------------------------------------------------------------------------
# CategoricalJudge
# ---------------------------------------------------------------------------


class TestCategoricalJudgePush:
    """Tests for CategoricalJudge push lifecycle."""

    def test_push_sets_id(self, docker_compose_test_env, db_cleanup):
        """Push should assign a backend id to the metric."""
        name = f"categorical-{int(time.time() * 1000)}"
        judge = CategoricalJudge(
            name=name,
            evaluation_prompt="Classify quality",
            categories=["good", "bad"],
            passing_categories=["good"],
        )
        assert judge.id is None
        judge.push()
        assert judge.id is not None

    def test_push_pull_preserves_all_fields(self, docker_compose_test_env, db_cleanup):
        """All config fields should survive a push-pull round trip."""
        name = f"categorical-{int(time.time() * 1000)}"
        judge = CategoricalJudge(
            name=name,
            description="Quality classifier",
            evaluation_prompt="Rate the output",
            evaluation_steps="Step 1: Read\nStep 2: Judge",
            categories=["excellent", "good", "poor"],
            passing_categories=["excellent", "good"],
        )
        judge.push()

        pulled = CategoricalJudge.pull(name=name)
        assert pulled.id == judge.id
        assert pulled.name == name
        assert pulled.config.description == "Quality classifier"
        assert pulled.config.evaluation_prompt == "Rate the output"
        assert pulled.config.evaluation_steps == "Step 1: Read\nStep 2: Judge"
        assert pulled.config.categories == ["excellent", "good", "poor"]
        assert pulled.config.passing_categories == ["excellent", "good"]

    def test_push_pull_preserves_the_target(self, docker_compose_test_env, db_cleanup):
        """The target should survive a push-pull round trip."""
        name = f"categorical-target-{int(time.time() * 1000)}"
        judge = CategoricalJudge(
            name=name,
            evaluation_prompt="Classify",
            categories=["yes", "no"],
            passing_categories=["yes"],
            target="conversation",
        )
        judge.push()

        pulled = CategoricalJudge.pull(name=name)
        assert pulled.config.target == {"on": "conversation"}

    def test_push_update_persists_changes(self, docker_compose_test_env, db_cleanup):
        """Modifying a pushed metric and re-pushing should update."""
        name = f"categorical-{int(time.time() * 1000)}"
        judge = CategoricalJudge(
            name=name,
            evaluation_prompt="original",
            categories=["good", "bad"],
            passing_categories=["good"],
        )
        judge.push()
        original_id = judge.id

        judge.config.evaluation_prompt = "updated"
        judge.push()
        assert judge.id == original_id

        pulled = CategoricalJudge.pull(name=name)
        assert pulled.id == original_id
        assert pulled.config.evaluation_prompt == "updated"

    def test_pull_nonexistent_raises(self, docker_compose_test_env, db_cleanup):
        """Pulling a metric that doesn't exist should raise ValueError."""
        with pytest.raises(ValueError):
            CategoricalJudge.pull(name="does-not-exist")


# ---------------------------------------------------------------------------
# GoalAchievementJudge (conversational)
# ---------------------------------------------------------------------------


class TestGoalAchievementJudgePush:
    """Tests for GoalAchievementJudge push lifecycle."""

    def test_push_sets_id(self, docker_compose_test_env, db_cleanup):
        """Push should assign a backend id to the metric."""
        name = f"goal-{int(time.time() * 1000)}"
        judge = GoalAchievementJudge(
            name=name,
            evaluation_prompt="Evaluate goal",
            threshold=0.7,
        )
        assert judge.id is None
        judge.push()
        assert judge.id is not None

    def test_push_pull_preserves_all_fields(self, docker_compose_test_env, db_cleanup):
        """All config fields should survive a push-pull round trip."""
        name = f"goal-{int(time.time() * 1000)}"
        judge = GoalAchievementJudge(
            name=name,
            description="Goal achievement evaluator",
            evaluation_prompt="Evaluate conversation goal achievement",
            evaluation_steps="Step 1: Analyze\nStep 2: Score",
            threshold=0.6,
            min_score=0.0,
            max_score=1.0,
        )
        judge.push()

        pulled = GoalAchievementJudge.pull(name=name)
        assert pulled.id == judge.id
        assert pulled.name == name
        assert pulled.description == "Goal achievement evaluator"
        assert pulled.config.evaluation_prompt == "Evaluate conversation goal achievement"
        assert pulled.config.evaluation_steps == "Step 1: Analyze\nStep 2: Score"
        assert pulled.threshold == 0.6
        assert pulled.min_score == 0.0
        assert pulled.max_score == 1.0

    def test_push_pull_preserves_the_target(self, docker_compose_test_env, db_cleanup):
        """The target should survive a push-pull round trip."""
        name = f"goal-target-{int(time.time() * 1000)}"
        judge = GoalAchievementJudge(
            name=name,
            evaluation_prompt="Evaluate",
            threshold=0.5,
            target="run",
        )
        judge.push()

        pulled = GoalAchievementJudge.pull(name=name)
        assert pulled.config.target == {"on": "run"}

    def test_push_update_persists_changes(self, docker_compose_test_env, db_cleanup):
        """Modifying a pushed metric and re-pushing should update."""
        name = f"goal-{int(time.time() * 1000)}"
        judge = GoalAchievementJudge(
            name=name,
            description="Original",
            evaluation_prompt="Evaluate goal",
            threshold=0.5,
        )
        judge.push()
        original_id = judge.id

        judge.config.description = "Updated"
        judge.push()
        assert judge.id == original_id

        pulled = GoalAchievementJudge.pull(name=name)
        assert pulled.id == original_id
        assert pulled.description == "Updated"

    def test_push_update_preserves_unchanged_fields(self, docker_compose_test_env, db_cleanup):
        """Fields not modified between pushes should be preserved."""
        name = f"goal-{int(time.time() * 1000)}"
        judge = GoalAchievementJudge(
            name=name,
            description="keep me",
            evaluation_prompt="Evaluate",
            threshold=0.8,
            min_score=0.0,
            max_score=1.0,
        )
        judge.push()

        judge.config.description = "changed"
        judge.push()

        pulled = GoalAchievementJudge.pull(name=name)
        assert pulled.config.evaluation_prompt == "Evaluate"
        assert pulled.threshold == 0.8
        assert pulled.min_score == 0.0
        assert pulled.max_score == 1.0

    def test_pull_nonexistent_raises(self, docker_compose_test_env, db_cleanup):
        """Pulling a metric that doesn't exist should raise ValueError."""
        with pytest.raises(ValueError):
            GoalAchievementJudge.pull(name="does-not-exist")


# ---------------------------------------------------------------------------
# Cross-type pull safety
# ---------------------------------------------------------------------------


class TestPullTypeSafety:
    """Pulling a metric with the wrong class should raise."""

    def test_pull_wrong_class_raises(self, docker_compose_test_env, db_cleanup):
        """Pulling a NumericJudge as a CategoricalJudge should raise ValueError."""
        name = f"numeric-wrong-{int(time.time() * 1000)}"
        judge = NumericJudge(name=name, evaluation_prompt="prompt")
        judge.push()

        with pytest.raises(ValueError):
            CategoricalJudge.pull(name=name)


# ---------------------------------------------------------------------------
# Default targets
# ---------------------------------------------------------------------------


class TestDefaultTargets:
    """A metric pushed without a target is stored with its class's default."""

    def test_a_judge_judges_each_turn(self, docker_compose_test_env, db_cleanup):
        name = f"numeric-default-target-{int(time.time() * 1000)}"
        NumericJudge(name=name, evaluation_prompt="prompt").push()

        assert NumericJudge.pull(name=name).config.target == {"on": "turn"}

    def test_a_conversational_metric_judges_the_conversation(
        self, docker_compose_test_env, db_cleanup
    ):
        name = f"goal-default-target-{int(time.time() * 1000)}"
        GoalAchievementJudge(name=name, evaluation_prompt="prompt", threshold=0.5).push()

        assert GoalAchievementJudge.pull(name=name).config.target == {"on": "conversation"}

    def test_a_categorical_judge_judges_each_turn(self, docker_compose_test_env, db_cleanup):
        name = f"cat-default-target-{int(time.time() * 1000)}"
        CategoricalJudge(
            name=name,
            evaluation_prompt="prompt",
            categories=["a", "b"],
            passing_categories=["a"],
        ).push()

        assert CategoricalJudge.pull(name=name).config.target == {"on": "turn"}


# ---------------------------------------------------------------------------
# LLM evaluation tests (require actual LLM, skipped by default)
# ---------------------------------------------------------------------------


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
        model=VertexAILLM(model_name="gemini-3.1-flash-lite"),
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
