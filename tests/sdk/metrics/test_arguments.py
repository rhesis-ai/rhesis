"""What a metric's evaluate() receives: input, output, trace and expectations."""

import asyncio
import inspect
from unittest.mock import AsyncMock, patch

import pytest

from rhesis.sdk.entities.trace import Trace
from rhesis.sdk.metrics import Expectations, NumericJudge
from rhesis.sdk.metrics.arguments import evaluation_arguments, judged_input_output
from rhesis.sdk.metrics.base import BaseMetric, MetricConfig, MetricResult

CONVERSATION = [
    {"role": "user", "content": "Book a room in Paris."},
    {"role": "assistant", "content": "Which dates?"},
    {"role": "user", "content": "Next Friday."},
    {"role": "assistant", "content": "Booked for Friday."},
]


class Recorder(BaseMetric):
    """Returns nothing useful; keeps what evaluate() received."""

    def __init__(self):
        super().__init__(MetricConfig(name="recorder"), model=AsyncMock())
        self.received = {}

    def set_model(self, model):
        return model

    @evaluation_arguments
    def evaluate(self, input=None, output=None, trace=None, expectations=None):
        self.received = {
            "input": input,
            "output": output,
            "trace": trace,
            "expectations": expectations,
        }
        return MetricResult(score=1.0)

    @evaluation_arguments
    async def a_evaluate(self, input=None, output=None, trace=None, expectations=None):
        return self.evaluate(input=input, output=output, trace=trace, expectations=expectations)


class OutputOnly(BaseMetric):
    def __init__(self):
        super().__init__(MetricConfig(name="output_only"), model=AsyncMock())

    def set_model(self, model):
        return model

    @evaluation_arguments
    def evaluate(self, output=None, expectations=None):
        return MetricResult(score=float(output == expectations.response))


# ---------------------------------------------------------------------------
# Building the trace
# ---------------------------------------------------------------------------


def test_a_trace_is_built_from_input_and_output():
    metric = Recorder()

    metric.evaluate(input="Hi", output="Hello")

    trace = metric.received["trace"]
    assert isinstance(trace, Trace)
    assert (trace.input, trace.output) == ("Hi", "Hello")
    assert not trace.is_conversation


def test_shortcuts_become_part_of_the_trace():
    metric = Recorder()

    metric.evaluate(
        input="Refund order 42",
        output="Done.",
        context=["Refunds take 5 days."],
        tool_calls=[{"name": "issue_refund", "arguments": {"order": 42}}],
        metadata={"intent": "refund"},
    )

    trace = metric.received["trace"]
    assert trace.context == ["Refunds take 5 days."]
    assert trace.tool_calls == [
        {"name": "issue_refund", "arguments": {"order": 42}, "output": None}
    ]
    assert trace.metadata == {"intent": "refund"}


def test_conversation_builds_a_conversation_trace():
    metric = Recorder()

    metric.evaluate(conversation=CONVERSATION)

    trace = metric.received["trace"]
    assert trace.is_conversation
    assert len(trace.root_spans) == 2


def test_a_dict_trace_is_validated_into_a_trace():
    metric = Recorder()
    payload = Trace.from_response("Hi", "Hello").model_dump(mode="json")

    metric.evaluate(trace=payload)

    assert isinstance(metric.received["trace"], Trace)
    assert metric.received["output"] == "Hello"


def test_a_trace_passed_in_is_used_as_it_is():
    metric = Recorder()
    trace = Trace.from_response("Hi", "Hello")

    metric.evaluate(trace=trace)

    assert metric.received["trace"] is trace


# ---------------------------------------------------------------------------
# Input and output read from the trace
# ---------------------------------------------------------------------------


def test_input_and_output_are_read_from_a_single_turn_trace():
    metric = Recorder()

    metric.evaluate(trace=Trace.from_response("Hi", "Hello"))

    assert (metric.received["input"], metric.received["output"]) == ("Hi", "Hello")


def test_a_conversation_is_judged_as_its_goal_and_transcript():
    metric = Recorder()

    metric.evaluate(conversation=CONVERSATION, expectations={"goal": "Book a room"})

    trace = metric.received["trace"]
    assert metric.received["input"] == "Book a room"
    assert metric.received["output"] == trace.messages().format_conversation().strip()
    assert "Booked for Friday." in metric.received["output"]


def test_a_conversation_without_a_goal_has_an_empty_input():
    trace = Trace.from_conversation(CONVERSATION)

    assert judged_input_output(trace)[0] == ""


def test_input_and_output_passed_in_win_over_the_trace():
    metric = Recorder()

    metric.evaluate(input="Asked", output="Answered", trace=Trace.from_response("Hi", "Hello"))

    assert (metric.received["input"], metric.received["output"]) == ("Asked", "Answered")


def test_a_string_expectation_is_the_expected_response():
    metric = Recorder()

    metric.evaluate(input="Capital of France?", output="Paris", expectations="Paris")

    assert metric.received["expectations"] == Expectations(response="Paris")


def test_async_evaluate_prepares_its_arguments_too():
    metric = Recorder()

    asyncio.run(metric.a_evaluate(input="Hi", output="Hello", context=["doc"]))

    assert metric.received["trace"].context == ["doc"]


# ---------------------------------------------------------------------------
# Refusals
# ---------------------------------------------------------------------------


def test_a_trace_and_a_shortcut_together_are_refused():
    with pytest.raises(ValueError, match="either trace or context"):
        Recorder().evaluate(trace=Trace.from_response("Hi", "Hello"), context=["doc"])


def test_a_trace_that_is_not_a_trace_is_refused():
    with pytest.raises(TypeError, match="trace must be a Trace"):
        Recorder().evaluate(trace=CONVERSATION)


def test_a_shortcut_to_a_metric_that_does_not_read_the_trace_is_refused():
    with pytest.raises(TypeError, match="does not read the trace.*context"):
        OutputOnly().evaluate(output="Paris", expectations="Paris", context=["doc"])


def test_parts_beside_a_conversation_are_refused():
    with pytest.raises(ValueError, match="assistant messages"):
        Recorder().evaluate(conversation=CONVERSATION, context=["doc"])


# ---------------------------------------------------------------------------
# Signatures
# ---------------------------------------------------------------------------


def test_the_signature_still_shows_only_the_four_parameters():
    """The backend reads a metric's signature to decide what to pass it."""
    params = inspect.signature(Recorder().evaluate).parameters
    async_params = inspect.signature(Recorder().a_evaluate).parameters

    assert list(params) == ["input", "output", "trace", "expectations"]
    assert list(async_params) == ["input", "output", "trace", "expectations"]


def test_judges_declare_only_the_four_parameters():
    judge = NumericJudge(evaluation_prompt="Judge", min_score=0, max_score=1, threshold=0.5)

    assert list(inspect.signature(judge.evaluate).parameters) == [
        "input",
        "output",
        "trace",
        "expectations",
    ]


# ---------------------------------------------------------------------------
# The five-line check: common checks need no Trace or Expectations import
# ---------------------------------------------------------------------------


@pytest.fixture
def judge():
    return NumericJudge(
        evaluation_prompt="Is the answer correct?", min_score=0, max_score=1, threshold=0.5
    )


def _prompt_for(judge, **kwargs):
    with patch.object(judge.model, "a_generate", new_callable=AsyncMock) as generate:
        generate.return_value = {"score": 1.0, "reason": "Right"}
        result = judge.evaluate(**kwargs)
    return result, generate.call_args.args[0]


def test_five_lines_exact_match():
    metric = OutputOnly()

    assert metric.evaluate(output="Paris", expectations="Paris").score == 1.0
    assert metric.evaluate(output="Rome", expectations="Paris").score == 0.0


def test_five_lines_judge_with_a_reference_answer(judge):
    result, prompt = _prompt_for(
        judge, input="Capital of France?", output="Paris.", expectations="Paris"
    )

    assert result.score == 1.0
    assert "Paris" in prompt


def test_five_lines_rag_check_with_context(judge):
    result, prompt = _prompt_for(
        judge,
        input="How long do refunds take?",
        output="Five days.",
        context=["Refunds take 5 days."],
        expectations="Five days",
    )

    assert result.score == 1.0
    assert "Refunds take 5 days." in prompt


def test_five_lines_tool_order_check():
    class LooksUpBeforeRefunding(Recorder):
        @evaluation_arguments
        def evaluate(self, trace=None):
            tools = [call["name"] for call in trace.tool_calls]
            ok = "lookup_order" in tools[: tools.index("issue_refund")]
            return MetricResult(score=float(ok))

    metric = LooksUpBeforeRefunding()
    good = [{"name": "lookup_order"}, {"name": "issue_refund"}]
    bad = [{"name": "issue_refund"}, {"name": "lookup_order"}]

    assert metric.evaluate(tool_calls=good).score == 1.0
    assert metric.evaluate(tool_calls=bad).score == 0.0
