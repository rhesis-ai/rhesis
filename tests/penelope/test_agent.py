"""Tests for Penelope agent module."""

from unittest.mock import Mock, patch

import pytest
from rhesis.penelope.agent import PenelopeAgent, _create_default_model
from rhesis.penelope.context import TestContext, TestState
from rhesis.penelope.targets.base import Target

from rhesis.sdk.metrics.providers.native import GoalAchievementJudge
from rhesis.sdk.models.base import BaseLLM


@pytest.fixture
def mock_model():
    """Mock LLM model for testing."""
    mock = Mock(spec=BaseLLM)
    mock.get_model_name.return_value = "mock-model"
    mock.generate.return_value = {
        "reasoning": "Test reasoning",
        "tool_name": "send_message_to_target",
        "parameters": {"message": "Hello"},
    }
    return mock


@pytest.fixture
def mock_target():
    """Mock target for testing."""

    class MockTarget(Target):
        @property
        def target_type(self) -> str:
            return "mock"

        @property
        def target_id(self) -> str:
            return "mock-123"

        @property
        def description(self) -> str:
            return "Mock target"

        def send_message(self, message: str, session_id=None, **kwargs):
            return {"success": True, "response": "Mock response", "session_id": session_id}

        def validate_configuration(self) -> tuple[bool, str]:
            return True, ""

    return MockTarget()


class TestDetermineGoalMetric:
    """Tests for PenelopeAgent._determine_goal_metric static method."""

    def test_explicit_goal_metric_provided(self, mock_model):
        """Test that explicit goal_metric is used when provided."""
        # Create explicit goal metric
        explicit_metric = GoalAchievementJudge(
            name="explicit_metric", model=mock_model, threshold=0.8
        )

        # Call _determine_goal_metric
        goal_metric, metrics = PenelopeAgent._determine_goal_metric(
            goal_metric=explicit_metric, metrics=[], model=mock_model
        )

        # Verify explicit metric is returned
        assert goal_metric == explicit_metric
        assert explicit_metric in metrics
        assert len(metrics) == 1

    def test_explicit_goal_metric_validation_fails(self, mock_model):
        """Test that invalid goal_metric raises ValueError."""
        # Create invalid metric (missing evaluate method)
        invalid_metric = Mock()
        del invalid_metric.evaluate  # Remove evaluate attribute

        # Should raise ValueError
        with pytest.raises(ValueError, match="must have an 'evaluate' method"):
            PenelopeAgent._determine_goal_metric(
                goal_metric=invalid_metric, metrics=[], model=mock_model
            )

    def test_auto_detect_goal_achievement_judge(self, mock_model):
        """Test auto-detection of GoalAchievementJudge in metrics list."""
        # Create metrics with GoalAchievementJudge
        goal_judge = GoalAchievementJudge(name="auto_detected", model=mock_model, threshold=0.7)
        other_metric = Mock()
        other_metric.name = "other_metric"
        metrics = [goal_judge, other_metric]

        # Call _determine_goal_metric
        goal_metric, result_metrics = PenelopeAgent._determine_goal_metric(
            goal_metric=None, metrics=metrics, model=mock_model
        )

        # Verify GoalAchievementJudge was auto-detected
        assert goal_metric == goal_judge
        assert goal_metric.name == "auto_detected"
        assert len(result_metrics) == 2

    def test_auto_create_goal_achievement_judge(self, mock_model):
        """Test auto-creation of GoalAchievementJudge when none provided."""
        # Empty metrics list
        metrics = []

        # Call _determine_goal_metric
        goal_metric, result_metrics = PenelopeAgent._determine_goal_metric(
            goal_metric=None, metrics=metrics, model=mock_model
        )

        # Verify GoalAchievementJudge was auto-created
        assert isinstance(goal_metric, GoalAchievementJudge)
        assert goal_metric.name == "penelope_goal_evaluation"
        assert goal_metric.config.threshold == 0.7
        assert len(result_metrics) == 1
        assert goal_metric in result_metrics

    def test_explicit_metric_added_to_metrics_list(self, mock_model):
        """Test that explicit goal_metric is added to metrics if not present."""
        # Create separate metrics
        goal_metric = GoalAchievementJudge(name="goal", model=mock_model)
        other_metric = Mock()
        other_metric.name = "other"
        metrics = [other_metric]

        # Call _determine_goal_metric
        result_metric, result_metrics = PenelopeAgent._determine_goal_metric(
            goal_metric=goal_metric, metrics=metrics, model=mock_model
        )

        # Verify goal_metric was added
        assert result_metric == goal_metric
        assert len(result_metrics) == 2
        assert goal_metric in result_metrics
        assert other_metric in result_metrics

    def test_explicit_metric_not_duplicated(self, mock_model):
        """Test that explicit goal_metric is not duplicated if already in metrics."""
        # Create goal metric already in list
        goal_metric = GoalAchievementJudge(name="goal", model=mock_model)
        metrics = [goal_metric]

        # Call _determine_goal_metric
        result_metric, result_metrics = PenelopeAgent._determine_goal_metric(
            goal_metric=goal_metric, metrics=metrics, model=mock_model
        )

        # Verify no duplication
        assert result_metric == goal_metric
        assert len(result_metrics) == 1


class TestPenelopeAgentInitialization:
    """Tests for PenelopeAgent initialization."""

    def test_init_with_defaults(self, mock_model):
        """Test PenelopeAgent initialization with default values."""
        agent = PenelopeAgent(model=mock_model)

        # Verify defaults
        assert agent.model == mock_model
        assert agent.max_iterations == 10  # Default from PenelopeConfig
        assert agent.timeout_seconds is None
        assert agent.enable_transparency is True
        assert agent.verbose is False
        assert len(agent.metrics) == 1  # Auto-created GoalAchievementJudge
        assert isinstance(agent.goal_metric, GoalAchievementJudge)

    def test_init_with_custom_max_iterations(self, mock_model):
        """Test initialization with custom max_iterations."""
        agent = PenelopeAgent(model=mock_model, max_iterations=20)

        assert agent.max_iterations == 20

    def test_init_with_explicit_goal_metric(self, mock_model):
        """Test initialization with explicit goal_metric parameter."""
        goal_metric = GoalAchievementJudge(name="custom_goal", model=mock_model, threshold=0.9)

        agent = PenelopeAgent(model=mock_model, goal_metric=goal_metric)

        assert agent.goal_metric == goal_metric
        assert agent.goal_metric.name == "custom_goal"
        assert agent.goal_metric.config.threshold == 0.9
        assert goal_metric in agent.metrics

    def test_init_with_metrics_list(self, mock_model):
        """Test initialization with metrics list containing GoalAchievementJudge."""
        goal_judge = GoalAchievementJudge(name="goal", model=mock_model)
        mock_metric = Mock()
        mock_metric.name = "other"
        metrics = [goal_judge, mock_metric]

        agent = PenelopeAgent(model=mock_model, metrics=metrics)

        # Verify GoalAchievementJudge was auto-detected
        assert agent.goal_metric == goal_judge
        assert len(agent.metrics) == 2
        assert goal_judge in agent.metrics
        assert mock_metric in agent.metrics

    def test_init_with_empty_metrics_creates_default(self, mock_model):
        """Test initialization with empty metrics list creates default judge."""
        agent = PenelopeAgent(model=mock_model, metrics=[])

        # Verify default GoalAchievementJudge was created
        assert isinstance(agent.goal_metric, GoalAchievementJudge)
        assert agent.goal_metric.name == "penelope_goal_evaluation"
        assert len(agent.metrics) == 1

    def test_init_with_metrics_and_explicit_goal_metric(self, mock_model):
        """Test initialization with both metrics list and explicit goal_metric."""
        mock_metric = Mock()
        mock_metric.name = "other"
        metrics = [mock_metric]

        goal_metric = GoalAchievementJudge(name="explicit", model=mock_model)

        agent = PenelopeAgent(model=mock_model, metrics=metrics, goal_metric=goal_metric)

        # Verify explicit goal_metric is used
        assert agent.goal_metric == goal_metric
        assert len(agent.metrics) == 2
        assert goal_metric in agent.metrics
        assert mock_metric in agent.metrics

    @patch("rhesis.penelope.agent._create_default_model")
    def test_init_without_model_creates_default(self, mock_create_default):
        """Test initialization without model creates default."""
        mock_default_model = Mock(spec=BaseLLM)
        mock_default_model.get_model_name.return_value = "default-model"
        mock_create_default.return_value = mock_default_model

        agent = PenelopeAgent()

        # Verify default model was created
        mock_create_default.assert_called_once()
        assert agent.model == mock_default_model

    def test_init_with_string_model(self, mock_model):
        """Test initialization with string model identifier."""
        with patch("rhesis.penelope.agent.get_model") as mock_get_model:
            mock_get_model.return_value = mock_model

            agent = PenelopeAgent(model="vertex_ai/gemini-2.0-flash")

            # Verify get_model was called
            mock_get_model.assert_called_once_with("vertex_ai/gemini-2.0-flash")
            assert agent.model == mock_model

    def test_init_invalid_goal_metric_raises_error(self, mock_model):
        """Test initialization with invalid goal_metric raises ValueError."""
        invalid_metric = Mock()
        del invalid_metric.evaluate

        with pytest.raises(ValueError, match="must have an 'evaluate' method"):
            PenelopeAgent(model=mock_model, goal_metric=invalid_metric)

    def test_evaluator_initialized_with_goal_metric(self, mock_model):
        """Test that GoalEvaluator is initialized with goal_metric."""
        goal_metric = GoalAchievementJudge(name="test", model=mock_model)

        agent = PenelopeAgent(model=mock_model, goal_metric=goal_metric)

        # Verify evaluator exists and has the goal_metric
        assert hasattr(agent, "evaluator")
        assert agent.evaluator.goal_metric == goal_metric

    def test_executor_initialized(self, mock_model):
        """Test that TurnExecutor is initialized."""
        agent = PenelopeAgent(model=mock_model, verbose=True, enable_transparency=False)

        # Verify executor exists
        assert hasattr(agent, "executor")


class TestPenelopeAgentHelperMethods:
    """Tests for PenelopeAgent helper methods."""

    def test_get_tools_for_test(self, mock_model, mock_target):
        """Test _get_tools_for_test creates default tools."""
        agent = PenelopeAgent(model=mock_model)

        tools = agent._get_tools_for_test(mock_target)

        # Verify default tools are created
        assert len(tools) >= 3  # TargetInteractionTool, AnalyzeTool, ExtractTool
        tool_names = [tool.name for tool in tools]
        assert "send_message_to_target" in tool_names
        assert "analyze_response" in tool_names
        assert "extract_information" in tool_names

    def test_get_tools_for_test_includes_custom_tools(self, mock_model, mock_target):
        """Test _get_tools_for_test includes custom tools."""
        custom_tool = Mock()
        custom_tool.name = "custom_tool"

        agent = PenelopeAgent(model=mock_model, tools=[custom_tool])

        tools = agent._get_tools_for_test(mock_target)

        # Verify custom tool is included
        assert custom_tool in tools
        assert len(tools) >= 4  # 3 default + 1 custom

    def test_generate_default_instructions(self, mock_model):
        """Test _generate_default_instructions generates instructions from goal."""
        agent = PenelopeAgent(model=mock_model)

        instructions = agent._generate_default_instructions("Test the chatbot")

        # Verify instructions contain the goal
        assert isinstance(instructions, str)
        assert len(instructions) > 0
        # Should contain some testing guidance
        assert "test" in instructions.lower() or "goal" in instructions.lower()

    def test_create_stopping_conditions(self, mock_model):
        """Test _create_stopping_conditions creates all conditions."""
        agent = PenelopeAgent(model=mock_model, max_iterations=15, timeout_seconds=120.0)

        conditions = agent._create_stopping_conditions()

        # Verify all conditions are created
        assert len(conditions) == 4  # MaxToolExecutions, MaxIterations, GoalAchieved, Timeout
        condition_types = [type(c).__name__ for c in conditions]
        assert "MaxToolExecutionsCondition" in condition_types
        assert "MaxIterationsCondition" in condition_types
        assert "GoalAchievedCondition" in condition_types
        assert "TimeoutCondition" in condition_types

    def test_create_stopping_conditions_without_timeout(self, mock_model):
        """Test _create_stopping_conditions without timeout."""
        agent = PenelopeAgent(model=mock_model, timeout_seconds=None)

        conditions = agent._create_stopping_conditions()

        # Verify 3 conditions (no timeout)
        assert len(conditions) == 3  # MaxToolExecutions, MaxIterations, GoalAchieved
        condition_types = [type(c).__name__ for c in conditions]
        assert "TimeoutCondition" not in condition_types
        assert "MaxToolExecutionsCondition" in condition_types

    def test_should_stop_returns_false_initially(self, mock_model, mock_target):
        """Test _should_stop returns False when no conditions met."""
        agent = PenelopeAgent(model=mock_model)

        # Create test state
        context = TestContext(
            target_id="test",
            target_type="mock",
            instructions="Test",
            goal="Test goal",
        )
        state = TestState(context=context)

        conditions = agent._create_stopping_conditions()
        should_stop, reason = agent._should_stop(state, conditions)

        assert should_stop is False
        assert reason == ""

    def test_should_stop_returns_true_when_condition_met(self, mock_model, mock_target):
        """Test _should_stop returns True when condition is met."""
        agent = PenelopeAgent(model=mock_model, max_iterations=1)

        # Create test state with 1 turn already
        context = TestContext(
            target_id="test",
            target_type="mock",
            instructions="Test",
            goal="Test goal",
        )
        state = TestState(context=context)
        state.current_turn = 1

        conditions = agent._create_stopping_conditions()
        should_stop, reason = agent._should_stop(state, conditions)

        assert should_stop is True
        assert "maximum iterations" in reason.lower() or "1" in reason


class TestCreateDefaultModel:
    """Tests for _create_default_model function."""

    @patch("rhesis.penelope.agent.get_model")
    @patch("rhesis.penelope.config.PenelopeConfig.get_default_model")
    @patch("rhesis.penelope.config.PenelopeConfig.get_default_model_name")
    def test_create_default_model(self, mock_get_model_name, mock_get_model, mock_get_model_func):
        """Test _create_default_model uses config defaults."""
        mock_get_model.return_value = "vertex_ai"
        mock_get_model_name.return_value = "gemini-2.0-flash"
        mock_model = Mock(spec=BaseLLM)
        mock_get_model_func.return_value = mock_model

        result = _create_default_model()

        # Verify get_model was called with defaults
        mock_get_model_func.assert_called_once_with(
            provider="vertex_ai", model_name="gemini-2.0-flash"
        )
        assert result == mock_model


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
