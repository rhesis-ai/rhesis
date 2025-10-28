"""
Tests for parameter introspection in MetricEvaluator.

These tests verify that the evaluator correctly handles metrics with
different evaluate() signatures using introspection.
"""

from unittest.mock import MagicMock, patch

from rhesis.backend.metrics.evaluator import MetricEvaluator
from rhesis.sdk.metrics import MetricResult


class TestMetricIntrospection:
    """Test that evaluator correctly introspects metric signatures."""

    def test_metric_with_all_parameters(self):
        """Test a metric that accepts all parameters (input, output, expected_output, context)."""
        evaluator = MetricEvaluator()

        # Create a mock metric that accepts all parameters
        mock_metric = MagicMock()
        mock_metric.name = "AllParamsMetric"
        mock_metric.requires_ground_truth = False
        mock_metric.requires_context = False
        
        # Set up the evaluate method to accept all parameters
        def evaluate_all(input, output, expected_output, context):
            return MetricResult(score=0.9)
        
        mock_metric.evaluate = evaluate_all
        mock_metric.evaluate.return_value = MetricResult(score=0.9)

        result = evaluator._evaluate_metric(
            metric=mock_metric,
            input_text="test input",
            output_text="test output",
            expected_output="expected",
            context=["context1"],
        )

        assert result.score == 0.9

    def test_metric_without_output_parameter(self):
        """Test a metric that doesn't accept output (like DeepEval ContextualRelevancy)."""
        evaluator = MetricEvaluator()

        # Create a mock metric that only accepts input and context
        mock_metric = MagicMock()
        mock_metric.name = "ContextualRelevancy"
        mock_metric.requires_ground_truth = False
        mock_metric.requires_context = True
        
        # Set up the evaluate method to only accept input and context
        def evaluate_no_output(input, context):
            # This should NOT receive output parameter
            return MetricResult(score=0.85)
        
        mock_metric.evaluate = evaluate_no_output
        mock_metric.evaluate.return_value = MetricResult(score=0.85)

        # This should NOT raise TypeError even though we're passing output_text
        result = evaluator._evaluate_metric(
            metric=mock_metric,
            input_text="test input",
            output_text="test output",  # This should be filtered out by introspection
            expected_output="expected",
            context=["context1"],
        )

        assert result.score == 0.85

    def test_metric_without_expected_output_parameter(self):
        """Test a metric that doesn't accept expected_output."""
        evaluator = MetricEvaluator()

        # Create a mock metric that only accepts input and output
        mock_metric = MagicMock()
        mock_metric.name = "AnswerRelevancy"
        mock_metric.requires_ground_truth = False
        mock_metric.requires_context = False
        
        # Set up the evaluate method to only accept input and output
        def evaluate_no_expected(input, output):
            return MetricResult(score=0.75)
        
        mock_metric.evaluate = evaluate_no_expected
        mock_metric.evaluate.return_value = MetricResult(score=0.75)

        result = evaluator._evaluate_metric(
            metric=mock_metric,
            input_text="test input",
            output_text="test output",
            expected_output="expected",  # This should be filtered out
            context=["context1"],
        )

        assert result.score == 0.75

    def test_metric_with_only_input_parameter(self):
        """Test a metric that only accepts input."""
        evaluator = MetricEvaluator()

        # Create a minimal mock metric
        mock_metric = MagicMock()
        mock_metric.name = "MinimalMetric"
        mock_metric.requires_ground_truth = False
        mock_metric.requires_context = False
        
        def evaluate_only_input(input):
            return MetricResult(score=1.0)
        
        mock_metric.evaluate = evaluate_only_input
        mock_metric.evaluate.return_value = MetricResult(score=1.0)

        result = evaluator._evaluate_metric(
            metric=mock_metric,
            input_text="test input",
            output_text="test output",  # All these should be filtered out
            expected_output="expected",
            context=["context1"],
        )

        assert result.score == 1.0

    @patch("rhesis.backend.metrics.adapters.create_metric_from_config")
    def test_introspection_with_real_deepeval_contextual_relevancy_signature(
        self, mock_create_metric
    ):
        """
        Integration test: verify introspection works with actual DeepEval signature.
        
        This test simulates the exact signature of DeepEvalContextualRelevancy.evaluate()
        which only accepts (self, input, context) and not output.
        """
        evaluator = MetricEvaluator()

        # Create a metric with the exact signature of DeepEvalContextualRelevancy
        mock_metric = MagicMock()
        mock_metric.name = "DeepEvalContextualRelevancy"
        mock_metric.requires_ground_truth = False
        mock_metric.requires_context = True
        
        def contextual_relevancy_evaluate(input, context=None):
            """Matches the actual signature from sdk/metrics/providers/deepeval/metrics.py"""
            return MetricResult(score=0.88)
        
        mock_metric.evaluate = contextual_relevancy_evaluate
        mock_create_metric.return_value = mock_metric

        # Create metric config
        metric_config = {
            "class_name": "DeepEvalContextualRelevancy",
            "name": "Contextual Relevancy",
            "backend": "deepeval",
            "requires_context": True,
            "requires_ground_truth": False,
            "threshold": 0.7,
            "score_type": "numeric",
        }

        # Evaluate - this should NOT raise TypeError
        results = evaluator.evaluate(
            metrics=[metric_config],
            input_text="What is AI?",
            output_text="AI is artificial intelligence",  # Should be filtered out
            expected_output="A good answer",
            context=["AI context"],
        )

        # Results are keyed by metric name, not class_name
        assert "Contextual Relevancy" in results
        assert results["Contextual Relevancy"]["score"] == 0.88

    @patch("rhesis.backend.metrics.adapters.create_metric_from_config")
    def test_introspection_with_real_deepeval_answer_relevancy_signature(
        self, mock_create_metric
    ):
        """
        Integration test: verify introspection works with DeepEval AnswerRelevancy.
        
        This metric accepts (self, input, output) but not expected_output or context.
        """
        evaluator = MetricEvaluator()

        # Create a metric with the exact signature of DeepEvalAnswerRelevancy
        mock_metric = MagicMock()
        mock_metric.name = "DeepEvalAnswerRelevancy"
        mock_metric.requires_ground_truth = False
        mock_metric.requires_context = False
        
        def answer_relevancy_evaluate(input, output):
            """Matches the actual signature from sdk/metrics/providers/deepeval/metrics.py"""
            return MetricResult(score=0.92)
        
        mock_metric.evaluate = answer_relevancy_evaluate
        mock_create_metric.return_value = mock_metric

        # Create metric config
        metric_config = {
            "class_name": "DeepEvalAnswerRelevancy",
            "name": "Answer Relevancy",
            "backend": "deepeval",
            "requires_context": False,
            "requires_ground_truth": False,
            "threshold": 0.7,
            "score_type": "numeric",
        }

        # Evaluate - this should work fine with introspection
        results = evaluator.evaluate(
            metrics=[metric_config],
            input_text="What is AI?",
            output_text="AI is artificial intelligence",
            expected_output="A good answer",  # Should be filtered out
            context=["AI context"],  # Should be filtered out
        )

        # Results are keyed by metric name, not class_name
        assert "Answer Relevancy" in results
        assert results["Answer Relevancy"]["score"] == 0.92

