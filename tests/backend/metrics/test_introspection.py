"""
Tests for build_metric_evaluate_params parameter introspection.

Verifies that build_metric_evaluate_params inspects metric evaluate() signatures and passes
each metric only the names it declares: input, output, trace, expectations.
"""

import inspect
from unittest.mock import MagicMock

from rhesis.backend.metrics.inputs import EvaluationInputs, ResponseTrace
from rhesis.backend.metrics.metric_config import build_metric_evaluate_params
from rhesis.sdk.entities.trace import Trace
from rhesis.sdk.metrics import Expectations, MetricResult
from rhesis.sdk.metrics.arguments import EVALUATION_PARAMETERS


def _metric(evaluate, a_evaluate=None):
    metric = MagicMock()
    metric.requires_ground_truth = False
    metric.evaluate = evaluate
    if a_evaluate is not None:
        metric.a_evaluate = a_evaluate
    return metric


def _inputs(loader=None, expectations=None, **response):
    response = {"input": "test input", "output": "test output", **response}
    return EvaluationInputs(
        trace=ResponseTrace(loader=loader, **response), expectations=expectations
    )


class TestBuildMetricEvaluateParams:
    """build_metric_evaluate_params filters kwargs by signature."""

    def test_metric_with_all_parameters(self):
        def evaluate(input, output, trace, expectations):
            return MetricResult(score=0.9)

        expectations = Expectations(response="expected")
        kwargs = build_metric_evaluate_params(
            _metric(evaluate), _inputs(expectations=expectations, context=["context1"])
        )

        assert set(kwargs) == {"input", "output", "trace", "expectations"}
        assert (kwargs["input"], kwargs["output"]) == ("test input", "test output")
        assert kwargs["expectations"] is expectations
        assert kwargs["trace"].context == ["context1"]

    def test_metric_without_output_parameter(self):
        def evaluate(input, trace):
            return MetricResult(score=0.85)

        kwargs = build_metric_evaluate_params(_metric(evaluate), _inputs())

        assert set(kwargs) == {"input", "trace"}

    def test_metric_with_only_input_parameter(self):
        def evaluate(input):
            return MetricResult(score=0.5)

        assert build_metric_evaluate_params(_metric(evaluate), _inputs()) == {"input": "test input"}

    def test_expectations_are_none_in_production(self):
        def evaluate(output, expectations):
            return MetricResult(score=1.0)

        kwargs = build_metric_evaluate_params(_metric(evaluate), _inputs())

        assert kwargs == {"output": "test output", "expectations": None}

    def test_old_parameter_names_are_not_filled(self):
        """A metric that still declares a removed name gets nothing for it."""

        def evaluate(input, output, expected_output, context):
            return MetricResult(score=0.9)

        kwargs = build_metric_evaluate_params(
            _metric(evaluate), _inputs(expectations=Expectations(response="x"))
        )

        assert kwargs == {"input": "test input", "output": "test output"}

    def test_response_parts_reach_the_trace(self):
        def evaluate(trace):
            return MetricResult(score=1.0)

        kwargs = build_metric_evaluate_params(
            _metric(evaluate),
            _inputs(
                context=["doc"],
                tool_calls=[{"name": "lookup", "arguments": {"id": 1}}],
                metadata={"k": "v"},
            ),
        )

        trace = kwargs["trace"]
        assert trace.context == ["doc"]
        assert [call["name"] for call in trace.tool_calls] == ["lookup"]
        assert trace.metadata == {"k": "v"}


class TestConversationInputs:
    """A conversation's input is its goal and its output the transcript."""

    def test_conversation_input_output(self):
        trace = Trace.from_conversation(
            [
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "hello"},
            ]
        )

        def evaluate(input, output, trace):
            return MetricResult(score=1.0)

        kwargs = build_metric_evaluate_params(
            _metric(evaluate),
            EvaluationInputs(trace=trace, expectations=Expectations(goal="greet")),
        )

        assert kwargs["input"] == "greet"
        assert "User: hi" in kwargs["output"] and "Assistant: hello" in kwargs["output"]
        assert kwargs["trace"] is trace


class TestSignatureChoice:
    def test_a_evaluate_params_preferred_over_evaluate(self):
        """a_evaluate's signature is what the pipeline calls, so it wins."""

        def a_evaluate_impl(input, trace):
            return MetricResult(score=0.8)

        def evaluate_impl(input, output):
            return MetricResult(score=0.9)

        kwargs = build_metric_evaluate_params(_metric(evaluate_impl, a_evaluate_impl), _inputs())

        assert set(kwargs) == {"input", "trace"}

    def test_a_evaluate_fallback_to_evaluate_when_varargs_only(self):
        def a_evaluate_varargs(*args, **kwargs):
            pass

        def evaluate_impl(input, output):
            return MetricResult(score=0.9)

        kwargs = build_metric_evaluate_params(_metric(evaluate_impl, a_evaluate_varargs), _inputs())

        assert kwargs == {"input": "test input", "output": "test output"}


class TestTraceParam:
    """The trace is read only for a metric that declares it, and only once."""

    def test_a_metric_declaring_trace_receives_it(self):
        trace = Trace(trace_id="a" * 32, root_spans=[{"span_id": "b" * 16, "span_name": "x"}])

        def evaluate(input, output, trace):
            return MetricResult(score=1.0)

        kwargs = build_metric_evaluate_params(_metric(evaluate), _inputs(loader=lambda: trace))

        assert kwargs["trace"] is trace

    def test_a_metric_without_it_never_triggers_a_read(self):
        def evaluate(input, output, expectations):
            return MetricResult(score=1.0)

        def loader():
            raise AssertionError("the trace was read for a metric that did not ask for it")

        kwargs = build_metric_evaluate_params(_metric(evaluate), _inputs(loader=loader))

        assert "trace" not in kwargs

    def test_the_trace_is_read_once_for_all_metrics(self):
        calls = []

        def loader():
            calls.append(1)
            return Trace(trace_id="a" * 32)

        def evaluate(input, output, trace):
            return MetricResult(score=1.0)

        inputs = _inputs(loader=loader)
        for _ in range(3):
            build_metric_evaluate_params(_metric(evaluate), inputs)

        assert calls == [1]

    def test_a_trace_that_cannot_be_read_is_built_from_the_response(self):
        def loader():
            raise RuntimeError("database gone")

        def evaluate(input, output, trace):
            return MetricResult(score=1.0)

        kwargs = build_metric_evaluate_params(
            _metric(evaluate), _inputs(loader=loader, input="in", output="out")
        )

        assert (kwargs["trace"].input, kwargs["trace"].output) == ("in", "out")


class TestIntrospectionCompleteness:
    """Every built-in metric declares only the four evaluation parameters."""

    def _get_all_metric_classes(self):
        from rhesis.sdk.metrics.providers.deepeval.factory import DeepEvalMetricFactory
        from rhesis.sdk.metrics.providers.native.factory import RhesisMetricFactory

        classes = []
        for framework, factory_cls in {
            "rhesis": RhesisMetricFactory,
            "deepeval": DeepEvalMetricFactory,
        }.items():
            for class_name, metric_cls in getattr(factory_cls, "_metrics", {}).items():
                classes.append((framework, class_name, metric_cls))
        return classes

    def test_all_evaluate_params_are_the_four_names(self):
        metric_classes = self._get_all_metric_classes()
        assert metric_classes, "Should find at least one metric class"

        unknown = []
        for framework, class_name, metric_cls in metric_classes:
            for method in (metric_cls.evaluate, metric_cls.a_evaluate):
                for name, param in inspect.signature(method).parameters.items():
                    if name == "self" or param.kind in (
                        inspect.Parameter.VAR_KEYWORD,
                        inspect.Parameter.VAR_POSITIONAL,
                    ):
                        continue
                    if name not in EVALUATION_PARAMETERS:
                        unknown.append(f"{framework}/{class_name}.{method.__name__}: {name}")

        assert unknown == [], "Metrics declare parameters outside the four:\n" + "\n".join(unknown)


class TestReferenceAnswer:
    """A metric that requires a reference answer gets an empty one when the test has none."""

    @staticmethod
    def _expectations(requires_ground_truth, expectations):
        def evaluate(output, expectations):
            return MetricResult(score=1.0)

        metric = _metric(evaluate)
        metric.requires_ground_truth = requires_ground_truth
        kwargs = build_metric_evaluate_params(metric, _inputs(expectations=expectations))
        return kwargs["expectations"]

    def test_no_expectations_become_an_empty_reference(self):
        assert self._expectations(True, None) == Expectations(response="")

    def test_missing_response_is_filled_and_the_rest_kept(self):
        given = Expectations(goal="Book a room")

        assert self._expectations(True, given) == Expectations(goal="Book a room", response="")

    def test_a_given_reference_is_passed_unchanged(self):
        given = Expectations(response="4")

        assert self._expectations(True, given) is given

    def test_other_metrics_get_expectations_as_they_are(self):
        assert self._expectations(False, None) is None
        given = Expectations(goal="g")
        assert self._expectations(False, given) is given
