"""
Tests for parameter introspection in MetricEvaluator.

These tests verify that the evaluator correctly handles metrics with
different evaluate() signatures using introspection.
"""

import inspect
from unittest.mock import MagicMock, patch

from rhesis.backend.metrics.evaluator import MetricEvaluator
from rhesis.sdk.metrics import MetricResult
from rhesis.sdk.metrics.conversational.types import ConversationHistory


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

    @patch("rhesis.sdk.metrics.MetricFactory.create")
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

    @patch("rhesis.sdk.metrics.MetricFactory.create")
    def test_introspection_with_real_deepeval_answer_relevancy_signature(self, mock_create_metric):
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


class TestConversationalIntrospection:
    """Test that evaluator correctly handles conversational metric signatures."""

    def test_conversation_history_passed_when_accepted(self):
        """Metrics accepting conversation_history receive it via introspection."""
        evaluator = MetricEvaluator()
        history = ConversationHistory.from_messages(
            [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there"},
            ]
        )
        evaluator._conversation_history = history

        mock_metric = MagicMock()
        mock_metric.name = "ConversationalMetric"

        received = {}

        def evaluate_conv(conversation_history, goal=None):
            received["conversation_history"] = conversation_history
            received["goal"] = goal
            return MetricResult(score=0.8)

        mock_metric.evaluate = evaluate_conv

        result = evaluator._call_metric_with_introspection(
            metric=mock_metric,
            input_text="Achieve the goal",
            output_text="conversation text",
            expected_output="",
            context=[],
        )

        assert result.score == 0.8
        assert received["conversation_history"] is history
        assert received["goal"] == "Achieve the goal"

    def test_conversation_history_not_passed_to_single_turn(self):
        """Single-turn metrics do not receive conversation_history."""
        evaluator = MetricEvaluator()
        history = ConversationHistory.from_messages([{"role": "user", "content": "Hello"}])
        evaluator._conversation_history = history

        mock_metric = MagicMock()
        mock_metric.name = "SingleTurnMetric"

        def evaluate_single(input, output):
            return MetricResult(score=0.9)

        mock_metric.evaluate = evaluate_single

        # Should NOT raise TypeError — conversation_history is filtered out
        result = evaluator._call_metric_with_introspection(
            metric=mock_metric,
            input_text="test",
            output_text="response",
            expected_output="",
            context=[],
        )

        assert result.score == 0.9

    def test_conversation_history_none_not_passed(self):
        """When conversation_history is None, it is not passed even if accepted."""
        evaluator = MetricEvaluator()
        evaluator._conversation_history = None

        mock_metric = MagicMock()
        mock_metric.name = "ConversationalMetric"

        received_keys = []

        def evaluate_conv(conversation_history=None, goal=None):
            received_keys.extend(
                k
                for k, v in {
                    "conversation_history": conversation_history,
                    "goal": goal,
                }.items()
                if v is not None
            )
            return MetricResult(score=0.7)

        mock_metric.evaluate = evaluate_conv

        result = evaluator._call_metric_with_introspection(
            metric=mock_metric,
            input_text="goal text",
            output_text="output",
            expected_output="",
            context=[],
        )

        assert result.score == 0.7
        assert "conversation_history" not in received_keys
        assert "goal" in received_keys

    @patch("rhesis.sdk.metrics.MetricFactory.create")
    def test_evaluate_threads_conversation_history(self, mock_create):
        """Full evaluate() flow stores and threads conversation_history."""
        evaluator = MetricEvaluator()
        history = ConversationHistory.from_messages(
            [
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello!"},
            ]
        )

        mock_metric = MagicMock()
        mock_metric.name = "ConversationalJudge"
        mock_metric.requires_ground_truth = False
        mock_metric.requires_context = False

        received = {}

        def evaluate_conv(conversation_history, goal=None):
            received["conversation_history"] = conversation_history
            received["goal"] = goal
            return MetricResult(score=0.85, details={"reason": "Good conversation"})

        mock_metric.evaluate = evaluate_conv
        mock_create.return_value = mock_metric

        metric_config = {
            "class_name": "ConversationalJudge",
            "name": "Conv Judge",
            "backend": "rhesis",
            "threshold": 0.5,
            "score_type": "numeric",
        }

        results = evaluator.evaluate(
            input_text="Help the user",
            output_text="conversation text",
            expected_output="",
            context=[],
            metrics=[metric_config],
            conversation_history=history,
        )

        assert "Conv Judge" in results
        assert results["Conv Judge"]["score"] == 0.85
        assert received["conversation_history"] is history
        assert received["goal"] == "Help the user"


class TestIntrospectionCompleteness:
    """Guard against missing parameter support in introspection.

    Scans all concrete metric classes and verifies that every parameter
    in their evaluate() signature is handled by _call_metric_with_introspection.
    This prevents the class of bug where new metric types silently fail
    because the evaluator doesn't know about their parameters.
    """

    # Parameters that _call_metric_with_introspection knows how to provide
    SUPPORTED_PARAMS = {
        "self",
        "input",
        "output",
        "expected_output",
        "context",
        "conversation_history",
        "goal",
    }

    def _get_all_metric_classes(self):
        """Collect concrete metric classes from provider factory registries.

        Inspects the _metrics dicts directly to get the actual classes
        without instantiating them (which would require API keys).
        """
        from rhesis.sdk.metrics.providers.deepeval.factory import DeepEvalMetricFactory
        from rhesis.sdk.metrics.providers.native.factory import RhesisMetricFactory
        from rhesis.sdk.metrics.providers.ragas.factory import RagasMetricFactory

        classes = []
        factories = {
            "rhesis": RhesisMetricFactory,
            "deepeval": DeepEvalMetricFactory,
            "ragas": RagasMetricFactory,
        }
        for framework, factory_cls in factories.items():
            registry = getattr(factory_cls, "_metrics", {})
            for class_name, metric_cls in registry.items():
                classes.append((framework, class_name, metric_cls))
        return classes

    def test_all_evaluate_params_are_supported(self):
        """Every param in any metric's evaluate() must be supported.

        If this test fails, you need to update
        _call_metric_with_introspection() in evaluator.py to handle
        the new parameter, then add it to SUPPORTED_PARAMS above.
        """
        metric_classes = self._get_all_metric_classes()
        assert len(metric_classes) > 0, "Should find at least one metric class"

        unsupported = []
        for framework, class_name, metric_cls in metric_classes:
            sig = inspect.signature(metric_cls.evaluate)
            for param_name, param in sig.parameters.items():
                if param_name in self.SUPPORTED_PARAMS:
                    continue
                # Allow **kwargs and *args — they accept anything
                if param.kind in (
                    inspect.Parameter.VAR_KEYWORD,
                    inspect.Parameter.VAR_POSITIONAL,
                ):
                    continue
                # Optional params with defaults are acceptable to skip
                if param.default is not inspect.Parameter.empty:
                    continue
                # Required param not in SUPPORTED_PARAMS — this is a problem
                unsupported.append(
                    f"{framework}/{class_name}.evaluate() has required param "
                    f"'{param_name}' not in introspection"
                )

        assert unsupported == [], (
            "Unsupported required parameters found in metric evaluate() "
            "signatures. Update _call_metric_with_introspection() in "
            "evaluator.py and SUPPORTED_PARAMS in this test:\n"
            + "\n".join(f"  - {u}" for u in unsupported)
        )
