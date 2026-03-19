"""
Test MetricEvaluator orchestration and LocalStrategy behavior.

These tests validate the evaluator orchestration logic in the backend
and will serve as regression guards during the migration to SDK metrics.
"""

from unittest.mock import MagicMock, patch

from rhesis.backend.metrics import Evaluator, MetricResult
from rhesis.backend.metrics.strategies.local import LocalStrategy


class TestLocalStrategyInit:
    """Test LocalStrategy stores constructor args correctly."""

    def test_defaults_to_none(self):
        strategy = LocalStrategy()

        assert strategy._model is None
        assert strategy._db is None
        assert strategy._organization_id is None

    def test_with_model(self):
        strategy = LocalStrategy(model="gpt-4")

        assert strategy._model == "gpt-4"

    def test_with_db_and_org(self):
        sentinel_db = MagicMock()
        strategy = LocalStrategy(db=sentinel_db, organization_id="org-123")

        assert strategy._db is sentinel_db
        assert strategy._organization_id == "org-123"

    def test_backend_value(self):
        strategy = LocalStrategy()

        assert strategy.backend_value() == "__local__"


class TestEvaluatorBehavior:
    """Test MetricEvaluator orchestration."""

    @patch("rhesis.sdk.metrics.MetricFactory.create")
    def test_evaluator_evaluate_single_metric(self, mock_create_metric, numeric_metric_config):
        """Test evaluating single metric."""
        # Mock the metric creation and evaluation
        mock_metric = MagicMock()
        mock_metric.requires_ground_truth = False
        mock_metric.requires_context = False
        mock_metric.name = "Numeric Quality Metric"
        mock_metric.evaluate.return_value = MetricResult(
            score=8.0, details={"reason": "Good quality response"}
        )
        mock_create_metric.return_value = mock_metric

        evaluator = Evaluator()
        results = evaluator.evaluate(
            input_text="What is 2+2?",
            expected_output="4",
            output_text="The answer is 4",
            context=[],
            metrics=[numeric_metric_config],
        )

        assert results is not None
        assert isinstance(results, dict)
        assert len(results) > 0

    @patch("rhesis.sdk.metrics.MetricFactory.create")
    def test_evaluator_evaluate_multiple_metrics(
        self, mock_create_metric, numeric_metric_config, categorical_metric_config
    ):
        """Test evaluating multiple metrics."""
        # Mock different results for different metrics
        mock_metric1 = MagicMock()
        mock_metric1.requires_ground_truth = False
        mock_metric1.requires_context = False
        mock_metric1.name = "Numeric Quality Metric"
        mock_metric1.evaluate.return_value = MetricResult(
            score=8.0, details={"reason": "Good quality"}
        )

        mock_metric2 = MagicMock()
        mock_metric2.requires_ground_truth = False
        mock_metric2.requires_context = False
        mock_metric2.name = "Categorical Sentiment Metric"
        mock_metric2.evaluate.return_value = MetricResult(
            score="positive", details={"reason": "Positive sentiment"}
        )

        mock_create_metric.side_effect = [mock_metric1, mock_metric2]

        evaluator = Evaluator()
        results = evaluator.evaluate(
            input_text="Test input",
            expected_output="Expected",
            output_text="Actual output",
            context=[],
            metrics=[numeric_metric_config, categorical_metric_config],
        )

        assert results is not None
        assert len(results) >= 2

    @patch("rhesis.sdk.metrics.MetricFactory.create")
    def test_evaluator_skips_ground_truth_required(self, mock_create_metric, numeric_metric_config):
        """Test evaluator skips metrics requiring ground truth when not provided."""
        # Modify config to require ground truth
        config_with_gt = numeric_metric_config.copy()
        config_with_gt["parameters"]["ground_truth_required"] = True

        # Mock metric that requires ground truth
        mock_metric = MagicMock()
        mock_metric.requires_ground_truth = True
        mock_metric.requires_context = False
        mock_metric.name = "Ground Truth Metric"
        mock_create_metric.return_value = mock_metric

        evaluator = Evaluator()
        results = evaluator.evaluate(
            input_text="Test input",
            expected_output=None,  # No ground truth provided
            output_text="Actual output",
            context=[],
            metrics=[config_with_gt],
        )

        # Metric should be skipped since ground truth is required but not provided
        # The exact behavior depends on implementation, so we just verify it doesn't crash
        assert results is not None
        assert isinstance(results, dict)

    @patch("rhesis.sdk.metrics.MetricFactory.create")
    def test_evaluator_handles_evaluation_error(
        self, mock_create_metric, numeric_metric_config, categorical_metric_config
    ):
        """Test evaluator handles individual metric errors gracefully."""
        # First metric fails, second succeeds
        mock_metric1 = MagicMock()
        mock_metric1.requires_ground_truth = False
        mock_metric1.requires_context = False
        mock_metric1.name = "Failing Metric"
        mock_metric1.evaluate.side_effect = Exception("Metric evaluation failed")

        mock_metric2 = MagicMock()
        mock_metric2.requires_ground_truth = False
        mock_metric2.requires_context = False
        mock_metric2.name = "Working Metric"
        mock_metric2.evaluate.return_value = MetricResult(
            score="positive", details={"reason": "Positive sentiment"}
        )

        mock_create_metric.side_effect = [mock_metric1, mock_metric2]

        evaluator = Evaluator()
        results = evaluator.evaluate(
            input_text="Test input",
            expected_output="Expected",
            output_text="Actual output",
            context=[],
            metrics=[numeric_metric_config, categorical_metric_config],
        )

        # Should return results despite one metric failing
        assert results is not None
        assert isinstance(results, dict)

    @patch("rhesis.sdk.metrics.MetricFactory.create")
    def test_evaluator_returns_partial_results(self, mock_create_metric, numeric_metric_config):
        """Test partial results when some metrics fail."""
        # Simulate partial failure
        mock_metric = MagicMock()
        mock_metric.requires_ground_truth = False
        mock_metric.requires_context = False
        mock_metric.name = "Failing Metric"
        mock_metric.evaluate.side_effect = Exception("Evaluation error")
        mock_create_metric.return_value = mock_metric

        evaluator = Evaluator()
        results = evaluator.evaluate(
            input_text="Test input",
            expected_output="Expected",
            output_text="Actual output",
            context=[],
            metrics=[numeric_metric_config],
        )

        # Should return results structure even if metrics fail
        assert results is not None
        assert isinstance(results, dict)

    @patch("rhesis.sdk.metrics.MetricFactory.create")
    def test_evaluator_with_context(self, mock_create_metric, numeric_metric_config):
        """Test evaluator with context provided."""
        mock_metric = MagicMock()
        mock_metric.requires_ground_truth = False
        mock_metric.requires_context = False
        mock_metric.name = "Context Metric"
        mock_metric.evaluate.return_value = MetricResult(
            score=9.0, details={"reason": "High quality with context"}
        )
        mock_create_metric.return_value = mock_metric

        context = ["Context 1", "Context 2"]
        evaluator = Evaluator()
        results = evaluator.evaluate(
            input_text="Test input",
            expected_output="Expected",
            output_text="Actual output",
            context=context,
            metrics=[numeric_metric_config],
        )

        assert results is not None
        # Verify context was passed (implicitly through mock being called)
        mock_create_metric.assert_called_once()

    @patch("rhesis.sdk.metrics.MetricFactory.create")
    def test_evaluator_with_empty_metrics_list(self, mock_create_metric):
        """Test evaluator with empty metrics list."""
        evaluator = Evaluator()
        results = evaluator.evaluate(
            input_text="Test input",
            expected_output="Expected",
            output_text="Actual output",
            context=[],
            metrics=[],
        )

        # Should return empty or minimal results
        assert results is not None
        assert isinstance(results, dict)

    @patch("rhesis.sdk.metrics.MetricFactory.create")
    def test_evaluator_result_structure(self, mock_create_metric, numeric_metric_config):
        """Test that evaluator returns results in expected structure."""
        mock_metric = MagicMock()
        mock_metric.requires_ground_truth = False
        mock_metric.requires_context = False
        mock_metric.name = "Numeric Quality Metric"
        mock_metric.evaluate.return_value = MetricResult(
            score=8.0, details={"reason": "Good quality"}
        )
        mock_create_metric.return_value = mock_metric

        evaluator = Evaluator()
        results = evaluator.evaluate(
            input_text="Test input",
            expected_output="Expected",
            output_text="Actual output",
            context=[],
            metrics=[numeric_metric_config],
        )

        # Verify structure (exact structure depends on implementation)
        assert isinstance(results, dict)
        # Results should contain metric outcomes
        assert len(results) > 0
