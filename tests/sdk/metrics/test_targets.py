"""A metric's target: what it judges in a trace, and how per-span verdicts combine."""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from rhesis.sdk.entities.trace import Span, Trace
from rhesis.sdk.metrics import NumericJudge, ToolCallTrajectory
from rhesis.sdk.metrics.arguments import evaluation_arguments
from rhesis.sdk.metrics.base import BaseMetric, MetricConfig, MetricResult
from rhesis.sdk.metrics.conversational.base import ConversationalMetricBase
from rhesis.sdk.metrics.targets import (
    MAX_JUDGED_SPANS,
    TARGETS,
    Target,
    TargetKind,
    check_target,
    default_target,
    evaluate_target,
    supported_targets,
)

CONVERSATION = [
    {"role": "user", "content": "Refund order 42."},
    {
        "role": "assistant",
        "content": "Refunded.",
        "tool_calls": [{"name": "issue_refund", "arguments": {"order": 42}}],
    },
    {"role": "user", "content": "And order 43?"},
    {"role": "assistant", "content": "Also refunded."},
]


class Longer(BaseMetric):
    """Passes when the output is longer than ``threshold`` characters; keeps every call."""

    def __init__(self, threshold=3):
        super().__init__(MetricConfig(name="longer"), model=AsyncMock())
        self.threshold = threshold
        self.calls = []

    def set_model(self, model):
        return model

    @evaluation_arguments
    def evaluate(self, input=None, output=None, expectations=None):
        self.calls.append((input, output))
        return MetricResult(score=float(len(output)), details={"reason": f"{len(output)} chars"})

    @evaluation_arguments
    async def a_evaluate(self, input=None, output=None, expectations=None):
        return self.evaluate(input=input, output=output, expectations=expectations)


class ReadsTrace(BaseMetric):
    def __init__(self):
        super().__init__(MetricConfig(name="reads_trace"), model=AsyncMock())
        self.traces = []

    def set_model(self, model):
        return model

    @evaluation_arguments
    def evaluate(self, trace=None, expectations=None):
        self.traces.append(trace)
        return MetricResult(score=1.0, details={"is_successful": True})


def span(kind, name=None, input=None, output=None, children=(), **attributes):
    attrs = dict(attributes)
    if input is not None:
        attrs["ai.tool.arguments" if kind == "tool.invoke" else "function.kwargs"] = input
    if output is not None:
        attrs["ai.tool.output" if kind == "tool.invoke" else "function.result"] = output
    if kind == "tool.invoke" and name:
        attrs["ai.tool.name"] = name
    if kind == "agent.invoke" and name:
        attrs["ai.agent.name"] = name
    return Span(
        span_id=f"{kind}-{name}-{id(attrs)}",
        span_name=name or kind,
        span_type=kind,
        attributes=attrs,
        children=list(children),
    )


def agent_trace():
    """A support agent that looks up and refunds, and a billing agent that refunds too."""
    support = span(
        "agent.invoke",
        "support",
        children=[
            span("tool.invoke", "lookup_order", '{"order": 42}', "found"),
            span("tool.invoke", "issue_refund", '{"order": 42}', "ok"),
        ],
    )
    billing = span(
        "agent.invoke", "billing", children=[span("tool.invoke", "issue_refund", "{}", "no")]
    )
    root = span("function", "function.endpoint_invoke", children=[support, billing])
    trace = Trace(root_spans=[root])
    trace._detail_loaded = True
    return trace


# ---------------------------------------------------------------------------
# The registry
# ---------------------------------------------------------------------------


def test_every_target_has_a_label_and_a_description():
    assert set(TARGETS) == set(TargetKind)
    assert all(preset.label and preset.description for preset in TARGETS.values())


@pytest.mark.parametrize(
    "config",
    [
        {"on": "conversation", "name": "x"},
        {"on": "turn", "within": "support"},
        {"on": "tool_call", "aggregate": "share"},
        {"on": "tool_call", "min_share": 0.5},
        {"on": "tool_call", "aggregate": "share", "min_share": 1.5},
        {"on": "span"},
        {"on": "tool_call", "tool": "x"},
        {"on": "run", "aggregate": "any"},
        {"on": "conversation", "aggregate": "share", "min_share": 0.5},
    ],
)
def test_malformed_targets_are_refused(config):
    with pytest.raises(ValidationError):
        Target.model_validate(config)


def test_a_target_is_stored_without_its_defaults():
    target = Target.coerce({"on": "tool_call", "name": "issue_refund", "aggregate": "all"})

    assert target.to_config() == {"on": "tool_call", "name": "issue_refund"}
    assert Target.coerce("retrieval").on is TargetKind.RETRIEVAL


# ---------------------------------------------------------------------------
# Which targets a metric takes
# ---------------------------------------------------------------------------


def test_a_metric_reading_input_and_output_judges_turns_and_spans():
    assert default_target(Longer) is TargetKind.TURN
    assert TargetKind.TOOL_CALL in supported_targets(Longer)
    assert TargetKind.RUN not in supported_targets(Longer)


def test_a_metric_reading_the_trace_judges_turns_conversations_and_runs():
    assert default_target(ReadsTrace) is TargetKind.RUN
    assert supported_targets(ReadsTrace) == [
        TargetKind.TURN,
        TargetKind.CONVERSATION,
        TargetKind.RUN,
    ]
    assert default_target(ToolCallTrajectory) is TargetKind.RUN


def test_judges_read_both():
    supported = supported_targets(NumericJudge)

    assert default_target(NumericJudge) is TargetKind.TURN
    assert TargetKind.RETRIEVAL in supported and TargetKind.RUN in supported


def test_a_conversational_metric_judges_conversations():
    class Conversational(ConversationalMetricBase):
        pass

    assert default_target(Conversational) is TargetKind.CONVERSATION
    assert TargetKind.TOOL_CALL not in supported_targets(Conversational)


def test_a_target_the_metric_cannot_take_names_the_choices():
    with pytest.raises(ValueError, match=r"Choices: Each turn \(turn\)"):
        check_target(ReadsTrace, "tool_call")


# ---------------------------------------------------------------------------
# Per-span targets
# ---------------------------------------------------------------------------


def test_each_tool_call_is_judged_and_the_verdicts_combine():
    metric = Longer(threshold=3)

    result = metric.evaluate(trace=agent_trace(), target="tool_call")

    assert [call[1] for call in metric.calls] == ["found", "ok", "no"]
    assert result.details["is_successful"] is False
    assert result.details["matched"] == 3 and result.details["passed"] == 1
    assert result.score == 2.0
    assert result.details["reason"].startswith("1 of 3 tool calls passed. `issue_refund`: 2 chars")


def test_a_name_and_an_agent_narrow_the_spans():
    metric = Longer(threshold=1)

    result = metric.evaluate(
        trace=agent_trace(), target={"on": "tool_call", "name": "issue_refund", "within": "support"}
    )

    assert metric.calls == [('{"order": 42}', "ok")]
    assert result.details["is_successful"] is True
    assert result.details["spans"][0]["name"] == "issue_refund"


@pytest.mark.parametrize(
    ("aggregate", "extra", "passed", "score"),
    [("any", {}, True, 5.0), ("share", {"min_share": 0.3}, True, 1 / 3)],
)
def test_other_aggregations(aggregate, extra, passed, score):
    result = Longer(threshold=3).evaluate(
        trace=agent_trace(), target={"on": "tool_call", "aggregate": aggregate, **extra}
    )

    assert result.details["is_successful"] is passed
    assert result.score == pytest.approx(score)


def test_a_target_matching_nothing_is_not_applicable():
    result = Longer().evaluate(input="Hi", output="Hello", target="retrieval")

    assert result.score is None
    assert result.details["not_applicable"] is True
    assert result.details["reason"].startswith("No retrievals were recorded. If the endpoint")


def test_a_reported_retrieval_is_judged_with_the_turns_input_as_its_query():
    metric = Longer()

    metric.evaluate(input="Q", output="A", context=["doc one", "doc two"], target="retrieval")

    assert metric.calls == [("Q", "doc one\n\ndoc two")]


def test_a_recorded_retrieval_keeps_its_own_query_and_counts_once():
    trace = Trace.from_response("Q", "A", context=["reported doc"])
    trace.root_spans[0].children.append(
        Span(
            span_id="r1",
            span_name="retrieve",
            span_type="retrieval",
            attributes={"function.kwargs": "refund policy", "function.result": '["recorded doc"]'},
        )
    )
    metric = Longer()

    metric.evaluate(trace=trace, target="retrieval")

    assert metric.calls == [("refund policy", "recorded doc")]


class SeesExpectations(Longer):
    @evaluation_arguments
    def evaluate(self, input=None, output=None, expectations=None):
        self.calls.append(expectations)
        return MetricResult(score=1.0, details={"is_successful": True})


def test_a_span_is_held_to_the_goal_but_not_the_whole_tests_answer_or_calls():
    metric = SeesExpectations()
    expectations = {
        "response": "Refunded.",
        "goal": "Refund the order",
        "tool_calls": [{"name": "issue_refund"}],
    }

    metric.evaluate(trace=agent_trace(), target="tool_call", expectations=expectations)

    seen = metric.calls[0]
    assert (seen.goal, seen.response, seen.tool_calls) == ("Refund the order", None, None)


def test_a_turn_keeps_the_expected_answer_but_not_the_conversations_calls():
    metric = SeesExpectations()

    metric.evaluate(
        conversation=CONVERSATION,
        target="turn",
        expectations={"response": "Done.", "tool_calls": [{"name": "issue_refund"}]},
    )

    assert {(seen.response, seen.tool_calls) for seen in metric.calls} == {("Done.", None)}


def test_metrics_comparing_whole_test_expectations_take_no_per_span_target():
    assert supported_targets(ToolCallTrajectory) == [TargetKind.CONVERSATION, TargetKind.RUN]
    assert TargetKind.TOOL_CALL not in supported_targets(Longer, compares=["response"])
    assert TargetKind.TURN in supported_targets(Longer, compares=["response"])


def test_only_so_many_spans_are_judged():
    calls = [{"name": f"tool_{i}", "arguments": {}} for i in range(MAX_JUDGED_SPANS + 5)]
    metric = Longer(threshold=0)

    result = metric.evaluate(input="Q", output="A", tool_calls=calls, target="tool_call")

    assert len(metric.calls) == MAX_JUDGED_SPANS
    assert result.details["matched"] == MAX_JUDGED_SPANS + 5
    assert f"Only the first {MAX_JUDGED_SPANS} of" in result.details["reason"]


def test_async_judges_each_span_too():
    metric = Longer(threshold=1)

    result = asyncio.run(metric.a_evaluate(trace=agent_trace(), target="tool_call"))

    assert len(metric.calls) == 3 and result.details["is_successful"] is True


# ---------------------------------------------------------------------------
# Turns, conversations and the whole run
# ---------------------------------------------------------------------------


def test_each_turn_of_a_conversation_is_judged():
    metric = Longer(threshold=10)

    result = metric.evaluate(conversation=CONVERSATION, target="turn")

    assert metric.calls == [
        ("Refund order 42.", "Refunded."),
        ("And order 43?", "Also refunded."),
    ]
    assert result.details["passed"] == 1


def test_a_turn_reads_as_a_turn_and_not_a_conversation():
    metric = ReadsTrace()

    metric.evaluate(conversation=CONVERSATION, target="turn")

    first, second = metric.traces
    assert not first.is_conversation
    assert [call["name"] for call in first.tool_calls] == ["issue_refund"]
    assert second.tool_calls == []


def test_a_single_turn_gives_the_metrics_own_result():
    result = Longer().evaluate(input="Hi", output="Hello", target="turn")

    assert result.details == {"reason": "5 chars"}


def test_the_whole_run_is_judged_once():
    metric = ReadsTrace()
    trace = agent_trace()

    result = evaluate_target(metric, trace, "run")

    assert metric.traces == [trace]
    assert result.details["is_successful"] is True


class NoVerdictOnShort(Longer):
    """No verdict for outputs under three characters."""

    @evaluation_arguments
    def evaluate(self, input=None, output=None, expectations=None):
        if len(output) < 3:
            return MetricResult(score=None, details={"is_successful": None})
        return MetricResult(score=float(len(output)), details={"is_successful": True})


def test_spans_without_a_verdict_neither_count_nor_give_the_score():
    result = NoVerdictOnShort().evaluate(trace=agent_trace(), target="tool_call")

    assert result.details["is_successful"] is True
    assert result.score == 5.0
    assert result.details["reason"] == "1 of 1 tool call passed."


def test_no_verdict_for_any_span_is_inconclusive():
    result = NoVerdictOnShort().evaluate(
        trace=agent_trace(), target={"on": "tool_call", "name": "issue_refund"}
    )

    assert result.score is None
    assert result.details["is_successful"] is None and result.details["inconclusive"] is True


def test_async_reads_what_a_evaluate_declares():
    class AsyncOnly(BaseMetric):
        def __init__(self):
            super().__init__(MetricConfig(name="async_only"), model=AsyncMock())
            self.calls = []

        def set_model(self, model):
            return model

        def evaluate(self, *args, **kwargs):
            raise AssertionError("the sync path was used")

        @evaluation_arguments
        async def a_evaluate(self, output=None):
            self.calls.append(output)
            return MetricResult(score=1.0, details={"is_successful": True})

    metric = AsyncOnly()

    asyncio.run(metric.a_evaluate(trace=agent_trace(), target="tool_call"))

    assert metric.calls == ["found", "ok", "no"]


def test_a_pass_does_not_name_the_spans_that_failed():
    result = Longer(threshold=3).evaluate(
        trace=agent_trace(), target={"on": "tool_call", "aggregate": "any"}
    )

    assert result.details["reason"] == "1 of 3 tool calls passed."


def test_a_reference_answer_rules_out_the_conversation():
    """A conversation has no expected response to compare with."""
    from rhesis.sdk.metrics.providers.deepeval.metrics import DeepEvalContextualRecall

    assert TargetKind.CONVERSATION not in supported_targets(Longer, compares=["response"])
    assert TargetKind.CONVERSATION not in supported_targets(DeepEvalContextualRecall)
    assert TargetKind.TURN in supported_targets(DeepEvalContextualRecall)
