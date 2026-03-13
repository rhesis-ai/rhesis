"""
Tests for build_metric_evaluate_params parameter introspection.

Verifies that build_metric_evaluate_params correctly inspects metric
evaluate() signatures and returns only the kwargs each metric accepts.
"""

import inspect
from unittest.mock import MagicMock

from rhesis.backend.metrics.metric_config import build_metric_evaluate_params
from rhesis.sdk.metrics import MetricResult
from rhesis.sdk.metrics.conversational.types import ConversationHistory


class TestBuildMetricEvaluateParams:
    """Test that build_metric_evaluate_params filters kwargs by signature."""

    def test_metric_with_all_parameters(self):
        """All standard params are included when the signature accepts them."""
        mock_metric = MagicMock()

        def evaluate_all(input, output, expected_output, context):
            return MetricResult(score=0.9)

        mock_metric.evaluate = evaluate_all

        kwargs = build_metric_evaluate_params(
            mock_metric,
            input_text="test input",
            output_text="test output",
            expected_output="expected",
            context=["context1"],
        )

        assert kwargs == {
            "input": "test input",
            "output": "test output",
            "expected_output": "expected",
            "context": ["context1"],
        }

    def test_metric_without_output_parameter(self):
        """Output is excluded when the metric signature omits it."""
        mock_metric = MagicMock()

        def evaluate_no_output(input, context):
            return MetricResult(score=0.85)

        mock_metric.evaluate = evaluate_no_output

        kwargs = build_metric_evaluate_params(
            mock_metric,
            input_text="test input",
            output_text="test output",
            expected_output="expected",
            context=["context1"],
        )

        assert kwargs == {"input": "test input", "context": ["context1"]}
        assert "output" not in kwargs
        assert "expected_output" not in kwargs

    def test_metric_without_expected_output_parameter(self):
        """Expected output is excluded when the metric signature omits it."""
        mock_metric = MagicMock()

        def evaluate_no_expected(input, output):
            return MetricResult(score=0.75)

        mock_metric.evaluate = evaluate_no_expected

        kwargs = build_metric_evaluate_params(
            mock_metric,
            input_text="test input",
            output_text="test output",
            expected_output="expected",
            context=["context1"],
        )

        assert kwargs == {"input": "test input", "output": "test output"}
        assert "expected_output" not in kwargs
        assert "context" not in kwargs

    def test_metric_with_only_input_parameter(self):
        """Only input is returned for a minimal single-param metric."""
        mock_metric = MagicMock()

        def evaluate_only_input(input):
            return MetricResult(score=1.0)

        mock_metric.evaluate = evaluate_only_input

        kwargs = build_metric_evaluate_params(
            mock_metric,
            input_text="test input",
            output_text="test output",
            expected_output="expected",
            context=["context1"],
        )

        assert kwargs == {"input": "test input"}

    def test_deepeval_contextual_relevancy_signature(self):
        """Simulates the exact DeepEvalContextualRelevancy.evaluate() signature."""
        mock_metric = MagicMock()

        def contextual_relevancy_evaluate(input, context=None):
            return MetricResult(score=0.88)

        mock_metric.evaluate = contextual_relevancy_evaluate

        kwargs = build_metric_evaluate_params(
            mock_metric,
            input_text="What is AI?",
            output_text="AI is artificial intelligence",
            expected_output="A good answer",
            context=["AI context"],
        )

        assert kwargs == {"input": "What is AI?", "context": ["AI context"]}
        assert "output" not in kwargs

    def test_deepeval_answer_relevancy_signature(self):
        """Simulates the exact DeepEvalAnswerRelevancy.evaluate() signature."""
        mock_metric = MagicMock()

        def answer_relevancy_evaluate(input, output):
            return MetricResult(score=0.92)

        mock_metric.evaluate = answer_relevancy_evaluate

        kwargs = build_metric_evaluate_params(
            mock_metric,
            input_text="What is AI?",
            output_text="AI is artificial intelligence",
            expected_output="A good answer",
            context=["AI context"],
        )

        assert kwargs == {"input": "What is AI?", "output": "AI is artificial intelligence"}
        assert "expected_output" not in kwargs
        assert "context" not in kwargs

    def test_metadata_included_when_accepted_and_provided(self):
        """Metadata is included only when the metric accepts it and it's not None."""
        mock_metric = MagicMock()

        def evaluate_with_metadata(input, output, metadata=None):
            return MetricResult(score=0.9)

        mock_metric.evaluate = evaluate_with_metadata

        kwargs = build_metric_evaluate_params(
            mock_metric,
            input_text="test",
            output_text="response",
            expected_output="",
            context=[],
            metadata={"key": "value"},
        )

        assert kwargs["metadata"] == {"key": "value"}

    def test_metadata_excluded_when_none(self):
        """Metadata is excluded when None even if the signature accepts it."""
        mock_metric = MagicMock()

        def evaluate_with_metadata(input, output, metadata=None):
            return MetricResult(score=0.9)

        mock_metric.evaluate = evaluate_with_metadata

        kwargs = build_metric_evaluate_params(
            mock_metric,
            input_text="test",
            output_text="response",
            expected_output="",
            context=[],
            metadata=None,
        )

        assert "metadata" not in kwargs

    def test_tool_calls_included_when_accepted_and_provided(self):
        """Tool calls are included only when the metric accepts them and they're not None."""
        mock_metric = MagicMock()

        def evaluate_with_tool_calls(input, output, tool_calls=None):
            return MetricResult(score=0.9)

        mock_metric.evaluate = evaluate_with_tool_calls

        kwargs = build_metric_evaluate_params(
            mock_metric,
            input_text="test",
            output_text="response",
            expected_output="",
            context=[],
            tool_calls=[{"name": "search", "args": {}}],
        )

        assert kwargs["tool_calls"] == [{"name": "search", "args": {}}]

    def test_tool_calls_excluded_when_none(self):
        """Tool calls are excluded when None even if the signature accepts them."""
        mock_metric = MagicMock()

        def evaluate_with_tool_calls(input, output, tool_calls=None):
            return MetricResult(score=0.9)

        mock_metric.evaluate = evaluate_with_tool_calls

        kwargs = build_metric_evaluate_params(
            mock_metric,
            input_text="test",
            output_text="response",
            expected_output="",
            context=[],
            tool_calls=None,
        )

        assert "tool_calls" not in kwargs


class TestConversationalParams:
    """Test conversation_history and goal parameter handling."""

    def test_conversation_history_included_when_accepted(self):
        """Metrics accepting conversation_history receive it; goal maps to input_text."""
        history = ConversationHistory.from_messages(
            [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there"},
            ]
        )

        mock_metric = MagicMock()

        def evaluate_conv(conversation_history, goal=None):
            return MetricResult(score=0.8)

        mock_metric.evaluate = evaluate_conv

        kwargs = build_metric_evaluate_params(
            mock_metric,
            input_text="Achieve the goal",
            output_text="conversation text",
            expected_output="",
            context=[],
            conversation_history=history,
        )

        assert kwargs["conversation_history"] is history
        assert kwargs["goal"] == "Achieve the goal"

    def test_conversation_history_excluded_from_single_turn(self):
        """Single-turn metrics do not receive conversation_history."""
        history = ConversationHistory.from_messages(
            [{"role": "user", "content": "Hello"}]
        )

        mock_metric = MagicMock()

        def evaluate_single(input, output):
            return MetricResult(score=0.9)

        mock_metric.evaluate = evaluate_single

        kwargs = build_metric_evaluate_params(
            mock_metric,
            input_text="test",
            output_text="response",
            expected_output="",
            context=[],
            conversation_history=history,
        )

        assert "conversation_history" not in kwargs
        assert kwargs == {"input": "test", "output": "response"}

    def test_conversation_history_none_not_passed(self):
        """When conversation_history is None, it is not passed even if accepted."""
        mock_metric = MagicMock()

        def evaluate_conv(conversation_history=None, goal=None):
            return MetricResult(score=0.7)

        mock_metric.evaluate = evaluate_conv

        kwargs = build_metric_evaluate_params(
            mock_metric,
            input_text="goal text",
            output_text="output",
            expected_output="",
            context=[],
            conversation_history=None,
        )

        assert "conversation_history" not in kwargs
        assert kwargs["goal"] == "goal text"


class TestIntrospectionCompleteness:
    """Guard against missing parameter support in introspection.

    Scans all concrete metric classes and verifies that every required
    parameter in their evaluate() signature is handled by
    build_metric_evaluate_params.
    """

    SUPPORTED_PARAMS = {
        "self",
        "input",
        "output",
        "expected_output",
        "context",
        "conversation_history",
        "goal",
        "metadata",
        "tool_calls",
    }

    def _get_all_metric_classes(self):
        """Collect concrete metric classes from provider factory registries."""
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
        """Every required param in any metric's evaluate() must be in SUPPORTED_PARAMS.

        If this test fails, update build_metric_evaluate_params() in
        metric_config.py to handle the new parameter, then add it to
        SUPPORTED_PARAMS above.
        """
        metric_classes = self._get_all_metric_classes()
        assert len(metric_classes) > 0, "Should find at least one metric class"

        unsupported = []
        for framework, class_name, metric_cls in metric_classes:
            sig = inspect.signature(metric_cls.evaluate)
            for param_name, param in sig.parameters.items():
                if param_name in self.SUPPORTED_PARAMS:
                    continue
                if param.kind in (
                    inspect.Parameter.VAR_KEYWORD,
                    inspect.Parameter.VAR_POSITIONAL,
                ):
                    continue
                if param.default is not inspect.Parameter.empty:
                    continue
                unsupported.append(
                    f"{framework}/{class_name}.evaluate() has required param "
                    f"'{param_name}' not in introspection"
                )

        assert unsupported == [], (
            "Unsupported required parameters found in metric evaluate() "
            "signatures. Update build_metric_evaluate_params() in "
            "metric_config.py and SUPPORTED_PARAMS in this test:\n"
            + "\n".join(f"  - {u}" for u in unsupported)
        )
