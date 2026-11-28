"""Targets on any span: conditions, presets as their short forms, what a unit reads, and the
target in words."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from pydantic import ValidationError

from rhesis.sdk.entities.trace import Span, Trace
from rhesis.sdk.metrics import FieldRule, NumericJudge
from rhesis.sdk.metrics.arguments import evaluation_arguments
from rhesis.sdk.metrics.base import BaseMetric, MetricConfig, MetricResult
from rhesis.sdk.metrics.conditions import Condition, check_portable_pattern
from rhesis.sdk.metrics.targets import TARGETS, Target, TargetKind, matching_units
from rhesis.sdk.metrics.utils import backend_config_to_sdk_config, sdk_config_to_backend_config

REPORTED = {"rhesis.span.source": "reported"}


def span(kind, name=None, children=(), events=(), duration=None, status=None, **attributes):
    attrs = {key.replace("__", "."): value for key, value in attributes.items()}
    if kind == "tool.invoke" and name:
        attrs.setdefault("ai.tool.name", name)
    if kind == "agent.invoke" and name:
        attrs.setdefault("ai.agent.name", name)
    if kind == "llm.invoke" and name:
        attrs.setdefault("ai.model.name", name)
    return Span(
        span_id=f"{kind}-{name}-{len(attrs)}-{id(attrs)}",
        span_name=f"ai.{kind}" if name is None else f"{kind} {name}",
        span_type=kind,
        attributes=attrs,
        events=list(events),
        duration_ms=duration,
        status_code=status,
        children=list(children),
    )


def support_trace() -> Trace:
    """A triage agent hands off to billing, which searches, calls tools and a model; a
    guardrail checks the reply; the endpoint also reported one tool call it made."""
    billing = span(
        "agent.invoke",
        "billing_agent",
        children=[
            span(
                "retrieval",
                "kb_search",
                events=[
                    {"name": "ai.retrieval.query", "attributes": {"ai.prompt.content": "refunds"}},
                    {
                        "name": "ai.retrieval.results",
                        "attributes": {"ai.completion.content": '["Refunds take 5 days."]'},
                    },
                ],
                duration=340,
            ),
            span(
                "tool.invoke",
                "lookup_order",
                duration=220,
                ai__tool__arguments='{"order_id": "ORD-1"}',
                ai__tool__output='{"total": 49}',
            ),
            span("llm.invoke", "claude-sonnet-4-5", duration=1900, ai__llm__tokens__total=812),
            span(
                "tool.invoke",
                "issue_refund",
                duration=412,
                ai__tool__arguments='{"order_id": "ORD-1", "amount": 49}',
                ai__tool__output='{"status": "refunded"}',
                ai__tool__type="http",
                app__customer_tier="gold",
            ),
            span(
                "tool.invoke",
                "issue_refund",
                duration=96,
                status="ERROR",
                ai__tool__arguments='{"order_id": "ORD-1", "amount": 49}',
                ai__tool__output='{"error": "duplicate refund"}',
                app__customer_tier="free",
            ),
        ],
    )
    triage = span(
        "agent.invoke",
        "triage_agent",
        children=[
            span("llm.invoke", "gpt-4.1-mini", duration=910),
            span("agent.handoff", "to billing_agent"),
            billing,
        ],
    )
    root = span(
        "endpoint.invoke",
        "POST /v1/chat",
        children=[
            triage,
            span("guardrail", "pii_filter", duration=38),
            span("tool.invoke", "cancel_order", **REPORTED, ai__tool__arguments="{}"),
        ],
        rhesis__conversation__input="I was charged twice",
        rhesis__conversation__output="I refunded the second charge.",
        rhesis__reported__metadata__channel="web",
    )
    trace = Trace(trace_id="t1", root_spans=[root])
    trace._detail_loaded = True
    return trace


def picked(target, trace=None):
    return [
        (unit.name, unit.span.duration_ms)
        for unit in matching_units(trace or support_trace(), Target.coerce(target))
    ]


# ---------------------------------------------------------------------------
# Conditions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("op", "value", "present", "met", "met_when_missing"),
    [
        ("==", "gold", "gold", True, False),
        ("==", 200, "200", True, False),
        ("!=", "internal", "web", True, True),
        ("<", 500, 412, True, False),
        ("<=", 412, "412", True, False),
        (">", 500, 412, False, False),
        (">=", 412, 412.0, True, False),
        ("in", ["a", "gold"], "gold", True, False),
        ("not_in", ["a", "b"], "gold", True, True),
        ("contains", "fund", "refund", True, False),
        ("matches", "^ORD-[0-9]+$", "ORD-104233", True, False),
        ("exists", None, "x", True, False),
        ("not_exists", None, "x", False, True),
    ],
)
def test_every_operator_with_the_field_set_and_missing(op, value, present, met, met_when_missing):
    condition = Condition(field="app.customer_tier", op=op, value=value)

    assert condition.met_by(present) is met
    assert condition.met_by(None) is met_when_missing


def test_a_number_condition_on_text_that_is_no_number_is_not_met():
    assert Condition(field="x", op="<", value=5).met_by("fast") is False


@pytest.mark.parametrize(
    ("condition", "message"),
    [
        ({"field": "x", "op": "~", "value": 1}, "op must be one of"),
        ({"field": "x", "op": "<", "value": "fast"}, "compares with a number"),
        ({"field": "x", "op": "in", "value": "a"}, "takes a list"),
        ({"field": "x", "op": "in", "value": []}, "takes a list"),
        ({"field": "x", "op": "exists", "value": 1}, "takes no value"),
        ({"field": "x", "op": "==", "value": None}, "needs a value"),
        ({"field": "x", "op": "matches", "value": "("}, "Invalid regular expression"),
        ({"field": "x", "op": "==", "value": {"nested": 1}}, "text, numbers or true/false"),
        ({"field": " ", "op": "exists"}, "needs a field"),
    ],
)
def test_a_malformed_condition_names_the_problem(condition, message):
    with pytest.raises(ValidationError, match=message):
        Condition.model_validate(condition)


# ---------------------------------------------------------------------------
# Patterns that mean the same in Python and Postgres
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("pattern", "named", "instead"),
    [
        (r"\brefund\b", r"\b", r"(^|[^A-Za-z0-9_])"),
        (r"\Bfund", r"\B", None),
        (r"\Arefund", r"\A", "^"),
        (r"refund\Z", r"\Z", "$"),
        (r"(?P<id>ORD-\d+)", "named group", "a plain group"),
        (r"(?<id>ORD)", "named group", "a plain group"),
        (r"(?<=ORD-)\d+", "lookbehind", None),
        (r"(?<!ORD-)\d+", "negative lookbehind", None),
        (r"(?i)refund", "inline flags", "[Rr]efund"),
        (r"(?i:refund)", "inline flags", None),
        (r"a++", "possessive quantifier", "a+"),
        (r"(?>ab)", "atomic group", None),
    ],
)
def test_a_pattern_that_differs_between_engines_is_refused(pattern, named, instead):
    with pytest.raises(ValueError, match="doesn't work the same everywhere") as caught:
        check_portable_pattern(pattern)
    assert named in str(caught.value)
    if instead:
        assert instead in str(caught.value)


@pytest.mark.parametrize(
    "pattern",
    [
        r"^ORD-[0-9]{6}$",
        r"[\b]",
        r"[0-9]+\.[0-9]{2}",
        r"(refund|cancel)_order",
        r"(?:refund|cancel)",
        r"(?=x)y",
        r"[]a]",
        r"[^]a]",
        r"\\b",
    ],
)
def test_a_portable_pattern_is_kept(pattern):
    check_portable_pattern(pattern)
    Condition(field="x", op="matches", value=pattern)


def test_a_field_rule_refuses_the_same_patterns_when_saved():
    with pytest.raises(ValueError, match="word boundary"):
        FieldRule.validate_config({"field": "output", "op": "matches", "value": r"\brefund\b"})


def test_a_stored_rule_with_a_non_portable_pattern_still_builds_and_runs():
    # Saved before the check existed: it keeps Python's meaning of \b.
    rule = FieldRule(field="output", op="matches", value=r"\brefund\b")

    assert rule.evaluate(output="Your refund is on its way.").details["is_successful"] is True
    assert rule.evaluate(output="Refunded.").details["is_successful"] is False


def test_a_target_condition_with_a_non_portable_pattern_is_refused_at_once():
    with pytest.raises(ValidationError, match="word boundary"):
        Condition(field="output", op="matches", value=r"\brefund\b")
    with pytest.raises(ValidationError, match="word boundary"):
        Target.spans(kind="tool_call", where=[("ai.tool.name", "matches", r"\brefund")])


# ---------------------------------------------------------------------------
# The target's shape
# ---------------------------------------------------------------------------


def test_the_older_where_becomes_conditions():
    target = Target.coerce({"on": "turn", "where": {"channel": ["web", "app"], "tier": "gold"}})

    assert target.to_config() == {
        "on": "turn",
        "where": [
            {"field": "channel", "op": "in", "value": ["web", "app"]},
            {"field": "tier", "op": "==", "value": "gold"},
        ],
    }


def test_an_older_where_key_named_like_a_special_field_reads_the_attribute():
    target = Target.coerce({"on": "turn", "where": {"status": 200}})

    assert target.where[0].field == "attributes.status"


def test_a_kind_written_as_a_preset_is_the_span_kind():
    target = Target.spans(kind="tool_call")

    assert target.where == [Condition(field="kind", op="==", value="tool.invoke")]


@pytest.mark.parametrize(
    ("target", "message"),
    [
        ({"on": "span"}, "needs conditions"),
        ({"on": "span", "where": []}, "use 'run'"),
        (
            {"on": "span", "name": "x", "where": [{"field": "kind", "op": "exists"}]},
            "add a condition on name",
        ),
        ({"on": "run", "read": {"input": "x"}}, "read is for a target with several units"),
        ({"on": "conversation", "where": [{"field": "x", "op": "exists"}]}, "where is for"),
        ({"on": "tool_call", "read": {}}, "names an input, an output or both"),
        ({"on": "tool_call", "read": {"input": "event:"}}, "needs an event name"),
    ],
)
def test_a_malformed_target_names_the_problem(target, message):
    with pytest.raises(ValidationError, match=message):
        Target.coerce(target)


def test_a_span_target_round_trips_through_its_config():
    target = Target.spans(
        kind="tool_call",
        name=["issue_refund", "cancel_order"],
        where=[("rhesis.reported.metadata.channel", "!=", "internal")],
        within="billing_agent",
        read=("ai.tool.arguments", "ai.tool.output"),
        aggregate="share",
        min_share=0.9,
    )

    config = target.to_config()

    assert config == {
        "on": "span",
        "within": "billing_agent",
        "where": [
            {"field": "kind", "op": "==", "value": "tool.invoke"},
            {"field": "name", "op": "in", "value": ["issue_refund", "cancel_order"]},
            {"field": "rhesis.reported.metadata.channel", "op": "!=", "value": "internal"},
        ],
        "read": {"input": "ai.tool.arguments", "output": "ai.tool.output"},
        "aggregate": "share",
        "min_share": 0.9,
    }
    assert Target.coerce(config) == target


# ---------------------------------------------------------------------------
# Presets are short forms of span targets
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", [k for k in TargetKind if TARGETS.get(k) and TARGETS[k].span_kind])
@pytest.mark.parametrize(
    "refinements",
    [
        {},
        {"within": "billing_agent"},
        {"where": [{"field": "app.customer_tier", "op": "==", "value": "gold"}]},
    ],
)
def test_a_preset_picks_what_its_span_target_picks(kind, refinements):
    preset = Target(on=kind, **refinements)

    assert preset.expand().on is TargetKind.SPAN
    assert picked(preset) == picked(preset.expand())


def test_a_named_preset_picks_what_its_span_target_picks():
    preset = Target(on="tool_call", name="issue_refund", within="billing_agent")
    written = Target.spans(kind="tool.invoke", name="issue_refund", within="billing_agent")

    assert preset.expand() == written
    assert picked(preset) == picked(written) == [("issue_refund", 412), ("issue_refund", 96)]


def test_turns_and_whole_traces_stay_as_they_are():
    for on in ("turn", "conversation", "run"):
        assert Target(on=on).expand() == Target(on=on)


# ---------------------------------------------------------------------------
# What a span target picks
# ---------------------------------------------------------------------------


def test_a_span_target_picks_by_attribute_across_kinds():
    target = Target.spans(where=[("duration_ms", ">", 1000)])

    assert picked(target) == [("claude-sonnet-4-5", 1900)]


def test_within_keeps_spans_inside_the_agent_at_any_depth():
    assert picked(Target.spans(kind="llm.invoke", within="triage_agent")) == [
        ("gpt-4.1-mini", 910),
        ("claude-sonnet-4-5", 1900),
    ]
    assert picked(Target.spans(kind="llm.invoke", within="billing_agent")) == [
        ("claude-sonnet-4-5", 1900)
    ]


def test_status_and_timing_read_as_missing_on_reported_spans():
    errors = Target.spans(kind="tool_call", where=[("status", "==", "error")])
    untimed = Target.spans(kind="tool_call", where=[("duration_ms", "not_exists")])

    assert picked(errors) == [("issue_refund", 96)]
    assert picked(untimed) == [("cancel_order", None)]


def test_a_reported_call_counts_only_where_none_of_its_kind_was_recorded():
    # The reported cancel_order is a tool call, and tool calls were recorded here.
    assert ("cancel_order", None) not in picked(Target.spans(kind="tool_call"))
    assert picked(Target.spans(name="cancel_order")) == [("cancel_order", None)]


def test_a_missing_attribute_meets_not_equal():
    target = Target.spans(kind="tool_call", where=[("app.customer_tier", "!=", "free")])

    assert picked(target) == [("lookup_order", 220), ("issue_refund", 412)]


def test_turn_conditions_read_the_turn_root():
    kept = Target.coerce(
        {
            "on": "turn",
            "where": [{"field": "rhesis.reported.metadata.channel", "op": "==", "value": "web"}],
        }
    )
    dropped = Target.coerce(
        {
            "on": "turn",
            "where": [{"field": "rhesis.reported.metadata.channel", "op": "==", "value": "app"}],
        }
    )

    assert len(matching_units(support_trace(), kept)) == 1
    assert matching_units(support_trace(), dropped) == []


def test_select_is_what_the_platform_judges():
    target, trace = Target.spans(kind="retrieval"), support_trace()

    selected = [u.span.span_id for u in target.select(trace)]

    assert selected == [u.span.span_id for u in matching_units(trace, target)]
    assert len(selected) == 1


# ---------------------------------------------------------------------------
# What a unit reads
# ---------------------------------------------------------------------------


def test_a_unit_reads_its_kind_s_input_and_output_by_default():
    [unit] = Target.spans(kind="retrieval").select(support_trace())

    assert unit.input == "refunds"
    assert unit.output == "Refunds take 5 days."


def test_read_names_attributes_events_and_the_turn():
    by_attribute = Target.spans(
        kind="tool_call", name="lookup_order", read=("ai.tool.output", None)
    )
    by_event = Target.spans(kind="retrieval", read={"output": "event:ai.retrieval.query"})
    turn = Target.coerce({"on": "turn", "read": {"input": "rhesis.reported.metadata.channel"}})

    [unit] = by_attribute.select(support_trace())
    assert (unit.input, unit.output) == ('{"total": 49}', '{"total": 49}')
    [unit] = by_event.select(support_trace())
    assert unit.output == "refunds"
    [unit] = turn.select(support_trace())
    assert (unit.input, unit.output) == ("web", "I refunded the second charge.")


def test_read_of_something_missing_gives_no_text():
    [unit] = Target.spans(kind="retrieval", read={"input": "ai.nothing.here"}).select(
        support_trace()
    )

    assert unit.input == ""


# ---------------------------------------------------------------------------
# The target in words
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("target", "words", "short"),
    [
        (
            Target.spans(
                kind="tool_call",
                name=["issue_refund", "cancel_order"],
                within="billing_agent",
                where=[("rhesis.reported.metadata.channel", "!=", "internal")],
            ),
            "each tool call named `issue_refund` or `cancel_order` inside `billing_agent`, "
            "where `rhesis.reported.metadata.channel` is not `internal`",
            "each tool call named `issue_refund` or `cancel_order` inside `billing_agent`, "
            "where `rhesis.reported.metadata.channel` is not `internal`",
        ),
        (
            Target.spans(where=[("app.customer_tier", "==", "gold")]),
            "each span where `app.customer_tier` is `gold`",
            "each span where `app.customer_tier` is `gold`",
        ),
        (Target(on="turn"), "each turn", "each turn"),
        (Target(on="conversation"), "the conversation", "the conversation"),
        (Target(on="run"), "the whole run", "the whole run"),
        (
            Target(on="tool_call", name="issue_refund"),
            "each tool call named `issue_refund`",
            "each tool call named `issue_refund`",
        ),
        (
            Target.spans(kind=["tool.invoke", "retrieval"]),
            "each span where `kind` is `tool.invoke` or `retrieval`",
            "each span where `kind` is `tool.invoke` or `retrieval`",
        ),
        (
            Target.spans(
                kind="retrieval",
                where=[("duration_ms", ">", 2000), ("ai.retrieval.backend", "exists")],
                read={"input": "event:ai.retrieval.query"},
            ),
            "each retrieval where `duration_ms` is over `2000` and `ai.retrieval.backend` is set",
            "each retrieval where `duration_ms` is over `2000`, and 1 more condition",
        ),
        (
            Target.spans(kind="agent", where=[("ai.agent.name", "not_in", ["a", "b"])]),
            "each agent run where `ai.agent.name` is neither `a` nor `b`",
            "each agent run where `ai.agent.name` is neither `a` nor `b`",
        ),
        (
            Target.spans(kind="tool_call", where=[("ai.tool.name", "in", ["a", "b"])]),
            "each tool call named `a` or `b`",
            "each tool call named `a` or `b`",
        ),
        (
            Target.spans(where=[("ai.tool.name", "==", "a")]),
            "each span where `ai.tool.name` is `a`",
            "each span where `ai.tool.name` is `a`",
        ),
    ],
)
def test_describe(target, words, short):
    assert target.describe() == words
    assert target.describe(short=True) == short


def test_a_target_matching_nothing_says_so_in_the_same_words():
    class Echo(BaseMetric):
        def __init__(self):
            super().__init__(MetricConfig(name="echo"), model=AsyncMock())

        def set_model(self, model):
            return model

        @evaluation_arguments
        def evaluate(self, input=None, output=None):
            return MetricResult(score=1.0, details={"is_successful": True})

    target = Target.spans(kind="tool_call", within="nobody")

    result = Echo().evaluate(trace=support_trace(), target=target)

    assert result.details["not_applicable"] is True
    assert result.details["reason"].startswith("No tool calls inside `nobody` were recorded.")
    assert "map tool_calls" in result.details["reason"]


# ---------------------------------------------------------------------------
# Metrics, push and pull
# ---------------------------------------------------------------------------


def _judge(**kwargs):
    with patch("rhesis.sdk.models.factory.get_model", return_value=Mock()):
        return NumericJudge(name="refunds", evaluation_prompt="p", model="gemini", **kwargs)


def test_a_judge_keeps_a_span_target_in_its_normalised_form():
    judge = _judge(target={"on": "tool_call", "where": {"app.customer_tier": "gold"}})

    assert judge.target == {
        "on": "tool_call",
        "where": [{"field": "app.customer_tier", "op": "==", "value": "gold"}],
    }


def test_push_and_pull_carry_a_span_target_unchanged():
    target = Target.spans(kind="tool_call", within="billing_agent").to_config()

    sent = sdk_config_to_backend_config({"name": "m", "target": target})
    read = backend_config_to_sdk_config({"name": "m", "config": sent["config"]})

    assert sent["config"] == {"target": target}
    assert MetricConfig(**read).target == target


def test_a_metric_evaluates_with_a_span_target():
    rule = FieldRule(field="duration_ms", op="<=", value=500)

    result = rule.evaluate(trace=support_trace(), target=Target.spans(kind="tool_call"))

    assert result.details["matched"] == 3
    assert result.details["is_successful"] is True
