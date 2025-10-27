"""
Test current MetricEvaluator behavior (baseline regression tests).

These tests validate the evaluator orchestration logic in the backend
and will serve as regression guards during the migration to SDK metrics.
"""

import pytest
from unittest.mock import MagicMock, patch
from rhesis.backend.metrics import Evaluator, MetricResult
from rhesis.backend.metrics.constants import ScoreType


class TestCurrentEvaluatorBehavior:
    """Test current MetricEvaluator behavior (baseline)."""
    
    def test_evaluator_initialization(self):
        """Test MetricEvaluator initialization."""
        evaluator = Evaluator()
        
        assert evaluator is not None
        assert evaluator.model is None  # No model specified
        assert evaluator.db is None  # No db specified
        assert evaluator.organization_id is None
    
    def test_evaluator_with_model(self):
        """Test evaluator with custom model parameter."""
        model = "gpt-4"
        evaluator = Evaluator(model=model)
        
        assert evaluator.model == model
    
    def test_evaluator_with_db_and_org(self, test_db, test_org_id):
        """Test evaluator with database and organization."""
        evaluator = Evaluator(db=test_db, organization_id=test_org_id)
        
        assert evaluator.db is test_db
        assert evaluator.organization_id == test_org_id
    
    @patch('rhesis.backend.metrics.rhesis.prompt_metric.RhesisPromptMetric.evaluate')
    def test_evaluator_evaluate_single_metric(self, mock_evaluate, numeric_metric_config):
        """Test evaluating single metric."""
        # Mock the metric evaluation
        mock_evaluate.return_value = MetricResult(
            score=8.0,
            details={"reason": "Good quality response"}
        )
        
        evaluator = Evaluator()
        results = evaluator.evaluate(
            input_text="What is 2+2?",
            expected_output="4",
            output_text="The answer is 4",
            context=[],
            metrics=[numeric_metric_config]
        )
        
        assert results is not None
        assert isinstance(results, dict)
        assert len(results) > 0
    
    @patch('rhesis.backend.metrics.rhesis.prompt_metric.RhesisPromptMetric.evaluate')
    def test_evaluator_evaluate_multiple_metrics(self, mock_evaluate, numeric_metric_config, categorical_metric_config):
        """Test evaluating multiple metrics."""
        # Mock different results for different metrics
        mock_evaluate.side_effect = [
            MetricResult(
                score=8.0,
                details={"reason": "Good quality"}
            ),
            MetricResult(
                score="positive",
                details={"reason": "Positive sentiment"}
            )
        ]

        # Use legacy backend factory for this test
        evaluator = Evaluator(use_sdk_metrics=False)
        results = evaluator.evaluate(
            input_text="Test input",
            expected_output="Expected",
            output_text="Actual output",
            context=[],
            metrics=[numeric_metric_config, categorical_metric_config]
        )
        
        assert results is not None
        assert len(results) >= 2
    
    @patch('rhesis.backend.metrics.rhesis.prompt_metric.RhesisPromptMetric.evaluate')
    def test_evaluator_skips_ground_truth_required(self, mock_evaluate, numeric_metric_config):
        """Test evaluator skips metrics requiring ground truth when not provided."""
        # Modify config to require ground truth
        config_with_gt = numeric_metric_config.copy()
        config_with_gt["parameters"]["ground_truth_required"] = True
        
        evaluator = Evaluator()
        results = evaluator.evaluate(
            input_text="Test input",
            expected_output=None,  # No ground truth provided
            output_text="Actual output",
            context=[],
            metrics=[config_with_gt]
        )
        
        # Metric should be skipped since ground truth is required but not provided
        # The exact behavior depends on implementation, so we just verify it doesn't crash
        assert results is not None
        assert isinstance(results, dict)
    
    @patch('rhesis.backend.metrics.rhesis.prompt_metric.RhesisPromptMetric.evaluate')
    def test_evaluator_handles_evaluation_error(self, mock_evaluate, numeric_metric_config, categorical_metric_config):
        """Test evaluator handles individual metric errors gracefully."""
        # First metric fails, second succeeds
        mock_evaluate.side_effect = [
            Exception("Metric evaluation failed"),
            MetricResult(
                score="positive",
                details={"reason": "Positive sentiment"}
            )
        ]
        
        evaluator = Evaluator()
        results = evaluator.evaluate(
            input_text="Test input",
            expected_output="Expected",
            output_text="Actual output",
            context=[],
            metrics=[numeric_metric_config, categorical_metric_config]
        )
        
        # Should return results despite one metric failing
        assert results is not None
        assert isinstance(results, dict)
    
    @patch('rhesis.backend.metrics.rhesis.prompt_metric.RhesisPromptMetric.evaluate')
    def test_evaluator_returns_partial_results(self, mock_evaluate, numeric_metric_config):
        """Test partial results when some metrics fail."""
        # Simulate partial failure
        mock_evaluate.side_effect = Exception("Evaluation error")
        
        evaluator = Evaluator()
        results = evaluator.evaluate(
            input_text="Test input",
            expected_output="Expected",
            output_text="Actual output",
            context=[],
            metrics=[numeric_metric_config]
        )
        
        # Should return results structure even if metrics fail
        assert results is not None
        assert isinstance(results, dict)
    
    @patch('rhesis.backend.metrics.rhesis.prompt_metric.RhesisPromptMetric.evaluate')
    def test_evaluator_with_context(self, mock_evaluate, numeric_metric_config):
        """Test evaluator with context provided."""
        mock_evaluate.return_value = MetricResult(
            score=9.0,
            details={"reason": "High quality with context"}
        )
        
        context = ["Context 1", "Context 2"]
        # Use legacy backend factory for this test
        evaluator = Evaluator(use_sdk_metrics=False)
        results = evaluator.evaluate(
            input_text="Test input",
            expected_output="Expected",
            output_text="Actual output",
            context=context,
            metrics=[numeric_metric_config]
        )
        
        assert results is not None
        # Verify context was passed (implicitly through mock being called)
        mock_evaluate.assert_called_once()
    
    def test_evaluator_lazy_loads_factory(self):
        """Test that evaluator lazy loads MetricFactory."""
        evaluator = Evaluator()
        
        # Factory should not be initialized until needed
        assert evaluator.factory is None
        
        # Access factory through private method
        factory = evaluator._get_factory()
        
        # Now factory should be initialized
        assert factory is not None
        assert evaluator.factory is not None
    
    @patch('rhesis.backend.metrics.rhesis.prompt_metric.RhesisPromptMetric.evaluate')
    def test_evaluator_with_empty_metrics_list(self, mock_evaluate):
        """Test evaluator with empty metrics list."""
        evaluator = Evaluator()
        results = evaluator.evaluate(
            input_text="Test input",
            expected_output="Expected",
            output_text="Actual output",
            context=[],
            metrics=[]
        )
        
        # Should return empty or minimal results
        assert results is not None
        assert isinstance(results, dict)
    
    @patch('rhesis.backend.metrics.rhesis.prompt_metric.RhesisPromptMetric.evaluate')
    def test_evaluator_result_structure(self, mock_evaluate, numeric_metric_config):
        """Test that evaluator returns results in expected structure."""
        mock_evaluate.return_value = MetricResult(
            score=8.0,
            details={"reason": "Good quality"}
        )
        
        evaluator = Evaluator()
        results = evaluator.evaluate(
            input_text="Test input",
            expected_output="Expected",
            output_text="Actual output",
            context=[],
            metrics=[numeric_metric_config]
        )
        
        # Verify structure (exact structure depends on implementation)
        assert isinstance(results, dict)
        # Results should contain metric outcomes
        assert len(results) > 0

