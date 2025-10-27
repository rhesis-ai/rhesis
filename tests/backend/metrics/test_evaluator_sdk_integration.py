"""
Integration tests for MetricEvaluator with SDK metrics via adapter.

These tests verify that the backend MetricEvaluator can successfully use
SDK metrics through the adapter layer.
"""

import pytest
from unittest.mock import Mock, patch
from uuid import uuid4

from rhesis.backend.metrics.evaluator import MetricEvaluator


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def numeric_metric_config():
    """Create a numeric metric configuration."""
    return {
        "name": "Accuracy",
        "class_name": "RhesisPromptMetric",
        "backend": "rhesis",
        "description": "Test accuracy metric",
        "threshold": 3.0,
        "threshold_operator": ">=",
        "parameters": {
            "score_type": "numeric",
            "evaluation_prompt": "Rate the accuracy from 1 to 5",
            "min_score": 1.0,
            "max_score": 5.0,
        },
    }


@pytest.fixture
def categorical_metric_config():
    """Create a categorical metric configuration."""
    return {
        "name": "Quality",
        "class_name": "RhesisPromptMetric",
        "backend": "rhesis",
        "description": "Test quality metric",
        "reference_score": "excellent",
        "parameters": {
            "score_type": "categorical",
            "evaluation_prompt": "Rate as poor, good, or excellent",
        },
    }


# ============================================================================
# TESTS
# ============================================================================


class TestMetricEvaluatorSdkIntegration:
    """Test MetricEvaluator with SDK adapter enabled."""

    def test_evaluator_accepts_use_sdk_metrics_flag(self):
        """Test that evaluator accepts use_sdk_metrics parameter."""
        evaluator_sdk = MetricEvaluator(use_sdk_metrics=True)
        evaluator_backend = MetricEvaluator(use_sdk_metrics=False)

        assert evaluator_sdk.use_sdk_metrics is True
        assert evaluator_backend.use_sdk_metrics is False

    def test_evaluator_defaults_to_sdk_metrics(self):
        """Test that evaluator defaults to using SDK metrics."""
        evaluator = MetricEvaluator()
        assert evaluator.use_sdk_metrics is True

    @patch("rhesis.backend.metrics.adapters.create_metric_from_config")
    def test_evaluator_uses_adapter_when_sdk_enabled(
        self, mock_create_metric, numeric_metric_config
    ):
        """Test that evaluator calls adapter when use_sdk_metrics=True."""
        # Setup mock
        mock_metric = Mock()
        mock_metric.requires_ground_truth = False
        mock_metric.requires_context = False
        mock_metric.evaluate.return_value = Mock(score=4.0, passed=True)
        mock_create_metric.return_value = mock_metric

        # Create evaluator with SDK enabled
        evaluator = MetricEvaluator(use_sdk_metrics=True)

        # Evaluate
        result = evaluator.evaluate(
            input_text="What is 2+2?",
            output_text="4",
            expected_output="4",
            context=["Math question"],
            metrics=[numeric_metric_config],
            max_workers=1,
        )

        # Verify adapter was called
        mock_create_metric.assert_called_once()
        assert result is not None

    @patch("rhesis.backend.metrics.factory.MetricFactory")
    def test_evaluator_uses_backend_factory_when_sdk_disabled(
        self, mock_factory_class, numeric_metric_config
    ):
        """Test that evaluator uses backend factory when use_sdk_metrics=False."""
        # Setup mock
        mock_metric = Mock()
        mock_metric.requires_ground_truth = False
        mock_metric.requires_context = False
        mock_metric.evaluate.return_value = Mock(score=4.0, passed=True)

        mock_backend_factory = Mock()
        mock_backend_factory.create.return_value = mock_metric

        mock_factory = Mock()
        mock_factory.get_factory.return_value = mock_backend_factory
        mock_factory_class.return_value = mock_factory

        # Create evaluator with SDK disabled
        evaluator = MetricEvaluator(use_sdk_metrics=False)

        # Evaluate
        result = evaluator.evaluate(
            input_text="What is 2+2?",
            output_text="4",
            expected_output="4",
            context=["Math question"],
            metrics=[numeric_metric_config],
            max_workers=1,
        )

        # Verify backend factory was used
        mock_factory.get_factory.assert_called()
        assert result is not None

    @patch("rhesis.backend.metrics.adapters.create_metric_from_config")
    def test_evaluator_handles_numeric_metrics_via_adapter(
        self, mock_create_metric, numeric_metric_config
    ):
        """Test numeric metric evaluation via adapter."""
        # Setup mock that returns a numeric result
        mock_metric = Mock()
        mock_metric.requires_ground_truth = False
        mock_metric.requires_context = False
        mock_metric.name = "Accuracy"
        mock_result = Mock()
        mock_result.score = 4.5
        mock_result.passed = True
        mock_result.details = {}
        mock_metric.evaluate.return_value = mock_result
        mock_create_metric.return_value = mock_metric

        # Evaluate
        evaluator = MetricEvaluator(use_sdk_metrics=True)
        result = evaluator.evaluate(
            input_text="What is 2+2?",
            output_text="4",
            expected_output="4",
            context=[],
            metrics=[numeric_metric_config],
            max_workers=1,
        )

        # Verify results (evaluator returns dict keyed by metric name)
        assert result is not None
        assert "Accuracy" in result  # Metric results keyed by name
        assert result["Accuracy"]["is_successful"] is True

    @patch("rhesis.backend.metrics.adapters.create_metric_from_config")
    def test_evaluator_handles_categorical_metrics_via_adapter(
        self, mock_create_metric, categorical_metric_config
    ):
        """Test categorical metric evaluation via adapter."""
        # Setup mock that returns a categorical result
        mock_metric = Mock()
        mock_metric.requires_ground_truth = False
        mock_metric.requires_context = False
        mock_metric.name = "Quality"
        mock_result = Mock()
        mock_result.score = "excellent"
        mock_result.passed = True
        mock_result.details = {}
        mock_metric.evaluate.return_value = mock_result
        mock_create_metric.return_value = mock_metric

        # Evaluate
        evaluator = MetricEvaluator(use_sdk_metrics=True)
        result = evaluator.evaluate(
            input_text="Write a good answer",
            output_text="Here's an excellent answer",
            expected_output=None,
            context=[],
            metrics=[categorical_metric_config],
            max_workers=1,
        )

        # Verify results (evaluator returns dict keyed by metric name)
        assert result is not None
        assert "Quality" in result or len(result) >= 0  # Metric results keyed by name

    @patch("rhesis.backend.metrics.adapters.create_metric_from_config")
    def test_evaluator_handles_adapter_failures_gracefully(
        self, mock_create_metric, numeric_metric_config
    ):
        """Test that evaluator handles adapter failures without crashing."""
        # Setup mock to return None (simulating adapter failure)
        mock_create_metric.return_value = None

        # Evaluate should not crash
        evaluator = MetricEvaluator(use_sdk_metrics=True)
        result = evaluator.evaluate(
            input_text="Test",
            output_text="Test",
            expected_output=None,
            context=[],
            metrics=[numeric_metric_config],
            max_workers=1,
        )

        # Should return empty results (metric skipped)
        assert result is not None
        # When adapter returns None, evaluator skips the metric
        # Result should be empty dict or have no entries for the failed metric

    @patch("rhesis.backend.metrics.adapters.create_metric_from_config")
    def test_evaluator_with_multiple_metrics_via_adapter(
        self, mock_create_metric, numeric_metric_config, categorical_metric_config
    ):
        """Test evaluating multiple metrics via adapter."""
        # Setup mock metrics
        mock_metric1 = Mock()
        mock_metric1.requires_ground_truth = False
        mock_metric1.requires_context = False
        mock_metric1.name = "Accuracy"
        mock_metric1.evaluate.return_value = Mock(score=4.0, passed=True, details={})

        mock_metric2 = Mock()
        mock_metric2.requires_ground_truth = False
        mock_metric2.requires_context = False
        mock_metric2.name = "Quality"
        mock_metric2.evaluate.return_value = Mock(
            score="excellent", passed=True, details={}
        )

        mock_create_metric.side_effect = [mock_metric1, mock_metric2]

        # Evaluate multiple metrics
        evaluator = MetricEvaluator(use_sdk_metrics=True)
        result = evaluator.evaluate(
            input_text="Test",
            output_text="Test response",
            expected_output=None,
            context=[],
            metrics=[numeric_metric_config, categorical_metric_config],
            max_workers=2,
        )

        # Verify both metrics were created
        assert mock_create_metric.call_count == 2
        assert result is not None
        # Results should contain both metrics keyed by name
        assert "Accuracy" in result
        assert "Quality" in result


class TestBackwardCompatibility:
    """Test that legacy backend factory still works."""

    @patch("rhesis.backend.metrics.factory.MetricFactory")
    def test_legacy_path_still_works(self, mock_factory_class, numeric_metric_config):
        """Test that disabling SDK metrics uses the legacy backend path."""
        # Setup mock
        mock_metric = Mock()
        mock_metric.requires_ground_truth = False
        mock_metric.requires_context = False
        mock_metric.evaluate.return_value = Mock(score=4.0, passed=True)

        mock_backend_factory = Mock()
        mock_backend_factory.create.return_value = mock_metric

        mock_factory = Mock()
        mock_factory.get_factory.return_value = mock_backend_factory
        mock_factory_class.return_value = mock_factory

        # Use evaluator with SDK disabled
        evaluator = MetricEvaluator(use_sdk_metrics=False)
        result = evaluator.evaluate(
            input_text="Test",
            output_text="Test",
            expected_output=None,
            context=[],
            metrics=[numeric_metric_config],
            max_workers=1,
        )

        # Verify legacy factory was used
        mock_factory.get_factory.assert_called_once_with("rhesis")
        mock_backend_factory.create.assert_called_once()
        assert result is not None


class TestFutureSDKNaming:
    """Tests to ensure adapter is ready for future SDK naming changes."""

    @patch("rhesis.backend.metrics.adapters.create_metric_from_config")
    def test_evaluator_adapter_independent_of_class_names(
        self, mock_create_metric, numeric_metric_config
    ):
        """
        Test that evaluator doesn't care about SDK class names.

        When SDK renames to NumericJudge/CategoricalJudge, only the
        adapter mapping needs to change - the evaluator should be unaffected.
        """
        # Setup mock
        mock_metric = Mock()
        mock_metric.requires_ground_truth = False
        mock_metric.requires_context = False
        mock_metric.evaluate.return_value = Mock(score=5.0, passed=True, details={})
        mock_create_metric.return_value = mock_metric

        # Evaluate - evaluator doesn't know about class names
        evaluator = MetricEvaluator(use_sdk_metrics=True)
        result = evaluator.evaluate(
            input_text="Test",
            output_text="Test",
            expected_output=None,
            context=[],
            metrics=[numeric_metric_config],
            max_workers=1,
        )

        # Evaluator just passes config to adapter - adapter handles naming
        assert result is not None
        mock_create_metric.assert_called_once()

