"""Tests for RhesisMetricFactory."""

import pytest

from rhesis.sdk.metrics.providers.native.categorical_judge import CategoricalJudge
from rhesis.sdk.metrics.providers.native.factory import RhesisMetricFactory
from rhesis.sdk.metrics.providers.native.goal_achievement_judge import GoalAchievementJudge
from rhesis.sdk.metrics.providers.native.numeric_judge import NumericJudge


@pytest.fixture
def factory():
    """Create a factory instance."""
    return RhesisMetricFactory()


@pytest.fixture
def setup_env(monkeypatch):
    """Set up test environment."""
    monkeypatch.setenv("GEMINI_API_KEY", "test_key")


class TestFactoryListMetrics:
    """Tests for listing available metrics."""

    def test_list_supported_metrics(self, factory):
        """Test that factory lists all supported metrics."""
        metrics = factory.list_supported_metrics()
        assert isinstance(metrics, list)
        assert len(metrics) == 3
        assert "NumericJudge" in metrics
        assert "CategoricalJudge" in metrics
        assert "GoalAchievementJudge" in metrics


class TestFactoryCreateNumericJudge:
    """Tests for creating NumericJudge instances."""

    def test_create_numeric_judge_with_required_params(self, factory, setup_env):
        """Test creating NumericJudge with only required parameters."""
        metric = factory.create(
            "NumericJudge",
            evaluation_prompt="Test prompt",
            model="gemini",
        )
        assert isinstance(metric, NumericJudge)
        assert metric.name == "numericjudge"
        assert metric.evaluation_prompt == "Test prompt"

    def test_create_numeric_judge_with_all_params(self, factory, setup_env):
        """Test creating NumericJudge with all parameters."""
        metric = factory.create(
            "NumericJudge",
            evaluation_prompt="Test prompt",
            evaluation_steps="Step 1\nStep 2",
            reasoning="Test reasoning",
            evaluation_examples="Example 1",
            min_score=0.0,
            max_score=10.0,
            threshold=5.0,
            threshold_operator=">=",
            name="custom_numeric",
            description="Custom numeric judge",
            metric_type="rag",
            metric_scope=["Single-Turn"],
            model="gemini",
        )
        assert isinstance(metric, NumericJudge)
        assert metric.name == "custom_numeric"
        assert metric.description == "Custom numeric judge"
        assert metric.min_score == 0.0
        assert metric.max_score == 10.0
        assert metric.threshold == 5.0
        assert metric.metric_scope == ["Single-Turn"]

    def test_create_numeric_judge_with_multi_turn_scope(self, factory, setup_env):
        """Test creating NumericJudge with Multi-Turn scope."""
        metric = factory.create(
            "NumericJudge",
            evaluation_prompt="Test prompt",
            name="multi_turn_numeric",
            metric_scope=["Multi-Turn"],
            model="gemini",
        )
        assert isinstance(metric, NumericJudge)
        assert metric.name == "multi_turn_numeric"
        assert metric.metric_scope == ["Multi-Turn"]

    def test_create_numeric_judge_with_both_scopes(self, factory, setup_env):
        """Test creating NumericJudge with both Single-Turn and Multi-Turn scopes."""
        metric = factory.create(
            "NumericJudge",
            evaluation_prompt="Test prompt",
            name="both_scopes_numeric",
            metric_scope=["Single-Turn", "Multi-Turn"],
            model="gemini",
        )
        assert isinstance(metric, NumericJudge)
        assert metric.name == "both_scopes_numeric"
        assert len(metric.metric_scope) == 2
        assert "Single-Turn" in metric.metric_scope
        assert "Multi-Turn" in metric.metric_scope

    def test_create_numeric_judge_missing_required_param(self, factory, setup_env):
        """Test that creating NumericJudge without required params raises error."""
        with pytest.raises(ValueError, match="Missing required parameters"):
            factory.create("NumericJudge", model="gemini")

    def test_create_numeric_judge_with_parameters_dict(self, factory, setup_env):
        """Test creating NumericJudge with parameters in a dict."""
        metric = factory.create(
            "NumericJudge",
            parameters={
                "evaluation_prompt": "Test prompt",
                "name": "dict_numeric",
            },
            model="gemini",
        )
        assert isinstance(metric, NumericJudge)
        assert metric.name == "dict_numeric"
        assert metric.evaluation_prompt == "Test prompt"

    def test_create_numeric_judge_kwargs_override_parameters(self, factory, setup_env):
        """Test that kwargs override parameters dict."""
        metric = factory.create(
            "NumericJudge",
            parameters={
                "evaluation_prompt": "From params",
                "name": "from_params",
            },
            evaluation_prompt="From kwargs",
            model="gemini",
        )
        assert isinstance(metric, NumericJudge)
        assert metric.evaluation_prompt == "From kwargs"


class TestFactoryCreateCategoricalJudge:
    """Tests for creating CategoricalJudge instances."""

    def test_create_categorical_judge_with_required_params(self, factory, setup_env):
        """Test creating CategoricalJudge with required parameters."""
        metric = factory.create(
            "CategoricalJudge",
            categories=["good", "bad", "neutral"],
            passing_categories=["good"],
            model="gemini",
        )
        assert isinstance(metric, CategoricalJudge)
        assert metric.name == "categoricaljudge"
        assert metric.categories == ["good", "bad", "neutral"]
        assert metric.passing_categories == ["good"]

    def test_create_categorical_judge_with_all_params(self, factory, setup_env):
        """Test creating CategoricalJudge with all parameters."""
        metric = factory.create(
            "CategoricalJudge",
            categories=["pass", "fail"],
            passing_categories="pass",  # String should be converted to list
            evaluation_prompt="Evaluate quality",
            evaluation_steps="Check criteria",
            reasoning="Use best judgment",
            name="quality_judge",
            description="Quality evaluation",
            requires_ground_truth=True,
            requires_context=False,
            model="gemini",
        )
        assert isinstance(metric, CategoricalJudge)
        assert metric.name == "quality_judge"
        assert metric.description == "Quality evaluation"
        assert metric.passing_categories == ["pass"]  # Should be normalized to list
        assert metric.requires_ground_truth is True
        assert metric.requires_context is False

    def test_create_categorical_judge_missing_categories(self, factory, setup_env):
        """Test that missing categories raises error."""
        with pytest.raises(ValueError, match="Missing required parameters"):
            factory.create(
                "CategoricalJudge",
                passing_categories=["good"],
                model="gemini",
            )

    def test_create_categorical_judge_missing_passing_categories(self, factory, setup_env):
        """Test that missing passing_categories raises error."""
        with pytest.raises(ValueError, match="Missing required parameters"):
            factory.create(
                "CategoricalJudge",
                categories=["good", "bad"],
                model="gemini",
            )


class TestFactoryCreateGoalAchievementJudge:
    """Tests for creating GoalAchievementJudge instances."""

    def test_create_goal_achievement_judge_minimal(self, factory, setup_env):
        """Test creating GoalAchievementJudge with minimal parameters."""
        metric = factory.create(
            "GoalAchievementJudge",
            model="gemini",
        )
        assert isinstance(metric, GoalAchievementJudge)
        assert metric.name == "goalachievementjudge"
        # Should have defaults
        assert metric.min_score == 0.0
        assert metric.max_score == 1.0
        assert metric.threshold == 0.5

    def test_create_goal_achievement_judge_with_custom_params(self, factory, setup_env):
        """Test creating GoalAchievementJudge with custom parameters."""
        metric = factory.create(
            "GoalAchievementJudge",
            evaluation_prompt="Custom prompt",
            min_score=0.0,
            max_score=5.0,
            threshold=3.0,
            name="custom_goal_judge",
            description="Custom goal achievement",
            model="gemini",
        )
        assert isinstance(metric, GoalAchievementJudge)
        assert metric.name == "custom_goal_judge"
        assert metric.min_score == 0.0
        assert metric.max_score == 5.0
        assert metric.threshold == 3.0

    def test_create_goal_achievement_judge_no_required_params(self, factory, setup_env):
        """Test that GoalAchievementJudge has no required params besides model."""
        # Should not raise any errors
        metric = factory.create("GoalAchievementJudge", model="gemini")
        assert isinstance(metric, GoalAchievementJudge)


class TestFactoryErrorHandling:
    """Tests for factory error handling."""

    def test_create_unknown_metric_class(self, factory, setup_env):
        """Test that creating unknown metric class raises error."""
        with pytest.raises(ValueError, match="Unknown metric class: UnknownMetric"):
            factory.create("UnknownMetric", model="gemini")

    def test_error_message_includes_available_classes(self, factory, setup_env):
        """Test that error message lists available classes."""
        try:
            factory.create("UnknownMetric", model="gemini")
        except ValueError as e:
            error_msg = str(e)
            assert "NumericJudge" in error_msg
            assert "CategoricalJudge" in error_msg
            assert "GoalAchievementJudge" in error_msg


class TestFactoryParameterFiltering:
    """Tests for parameter filtering behavior."""

    def test_unsupported_params_are_filtered(self, factory, setup_env):
        """Test that unsupported parameters are filtered out."""
        # Should not raise error even with unsupported param
        metric = factory.create(
            "NumericJudge",
            evaluation_prompt="Test",
            unsupported_param="should_be_ignored",
            another_bad_param=123,
            model="gemini",
        )
        assert isinstance(metric, NumericJudge)
        assert not hasattr(metric, "unsupported_param")
        assert not hasattr(metric, "another_bad_param")

    def test_common_params_work_for_all_metrics(self, factory, setup_env):
        """Test that common parameters (model) work for all metrics."""
        # NumericJudge
        metric1 = factory.create(
            "NumericJudge",
            evaluation_prompt="Test",
            model="gemini",
        )
        assert metric1.model is not None

        # CategoricalJudge
        metric2 = factory.create(
            "CategoricalJudge",
            categories=["a", "b"],
            passing_categories=["a"],
            model="gemini",
        )
        assert metric2.model is not None

        # GoalAchievementJudge
        metric3 = factory.create(
            "GoalAchievementJudge",
            model="gemini",
        )
        assert metric3.model is not None


class TestFactoryDefaultNaming:
    """Tests for default naming behavior."""

    def test_default_name_from_class_name(self, factory, setup_env):
        """Test that name defaults to lowercase class name."""
        metric = factory.create(
            "NumericJudge",
            evaluation_prompt="Test",
            model="gemini",
        )
        assert metric.name == "numericjudge"

    def test_explicit_name_overrides_default(self, factory, setup_env):
        """Test that explicit name overrides default."""
        metric = factory.create(
            "NumericJudge",
            evaluation_prompt="Test",
            name="my_custom_name",
            model="gemini",
        )
        assert metric.name == "my_custom_name"


class TestFactoryIntegration:
    """Integration tests for factory."""

    def test_create_all_metric_types_sequentially(self, factory, setup_env):
        """Test creating all metric types in sequence."""
        # Create NumericJudge
        numeric = factory.create(
            "NumericJudge",
            evaluation_prompt="Numeric test",
            model="gemini",
        )
        assert isinstance(numeric, NumericJudge)

        # Create CategoricalJudge
        categorical = factory.create(
            "CategoricalJudge",
            categories=["yes", "no"],
            passing_categories=["yes"],
            model="gemini",
        )
        assert isinstance(categorical, CategoricalJudge)

        # Create GoalAchievementJudge
        goal = factory.create(
            "GoalAchievementJudge",
            model="gemini",
        )
        assert isinstance(goal, GoalAchievementJudge)

        # All should be different instances
        assert numeric != categorical
        assert categorical != goal
        assert numeric != goal

    def test_factory_instances_are_independent(self, factory, setup_env):
        """Test that created instances are independent."""
        metric1 = factory.create(
            "NumericJudge",
            evaluation_prompt="Test 1",
            name="metric1",
            model="gemini",
        )
        metric2 = factory.create(
            "NumericJudge",
            evaluation_prompt="Test 2",
            name="metric2",
            model="gemini",
        )

        # Different names
        assert metric1.name != metric2.name
        # Different prompts
        assert metric1.evaluation_prompt != metric2.evaluation_prompt
        # Different instances
        assert metric1 is not metric2

