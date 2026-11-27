"""Rules: metrics with no model that read the trace or the expected response and compare."""

from datetime import datetime, timedelta, timezone

import pytest

from rhesis.sdk.entities.trace import Span, Trace
from rhesis.sdk.metrics import FieldRule, ResponseRule, ToolCallTrajectory, TraceRule
from rhesis.sdk.metrics.base import MetricType
from rhesis.sdk.metrics.expectations import Expectations
from rhesis.sdk.metrics.providers.native.factory import RhesisMetricFactory
from rhesis.sdk.metrics.providers.native.rules import edit_similarity, rouge_l
from rhesis.sdk.metrics.targets import TargetKind, default_target, supported_targets

START = datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc)


def span(
    kind="endpoint.invoke",
    name=None,
    ms=None,
    status="OK",
    attributes=None,
    children=(),
    cost=None,
    offset_ms=0,
):
    attrs = {"ai.operation.type": kind, **(attributes or {})}
    if name and kind == "tool.invoke":
        attrs["ai.tool.name"] = name
    start = START + timedelta(milliseconds=offset_ms)
    return Span(
        span_id=f"s{id(attrs)}",
        span_name=name or kind,
        start_time=start,
        end_time=start + timedelta(milliseconds=ms or 0),
        duration_ms=ms,
        status_code=status,
        attributes=attrs,
        cost_usd=cost,
        children=list(children),
    )


def trace(*roots):
    t = Trace(root_spans=list(roots))
    t._detail_loaded = True
    return t


def turn(output="Hello", ms=1200, attributes=None, **kwargs):
    attributes = {"rhesis.conversation.output": output, **(attributes or {})}
    return span(attributes=attributes, ms=ms, **kwargs)


def model(input_tokens=None, output_tokens=None, total=None):
    attributes = {}
    if input_tokens is not None:
        attributes["ai.llm.tokens.input"] = input_tokens
    if output_tokens is not None:
        attributes["ai.llm.tokens.output"] = output_tokens
    if total is not None:
        attributes["ai.llm.tokens.total"] = total
    return span("llm.invoke", attributes=attributes, ms=10)


def judged(rule, t, **kwargs):
    return rule.evaluate(trace=t, **kwargs)


def verdict(result):
    return result.details["is_successful"]


# ── the classes ──────────────────────────────────────────────────


def test_rules_need_no_model_and_are_their_own_metric_type():
    for rule in (
        FieldRule(field="duration_ms", op="<=", value=5000),
        ResponseRule(),
        ToolCallTrajectory(),
    ):
        assert isinstance(rule, TraceRule)
        assert rule.model is None
        assert not rule.REQUIRES_MODEL
        assert rule.metric_type is MetricType.RULE


def test_default_and_supported_targets_follow_what_each_rule_compares():
    assert default_target(FieldRule) is TargetKind.TURN
    assert default_target(ResponseRule) is TargetKind.TURN
    assert default_target(ToolCallTrajectory) is TargetKind.RUN
    assert set(supported_targets(FieldRule)) == set(TargetKind)
    assert TargetKind.TOOL_CALL not in supported_targets(ResponseRule)
    assert TargetKind.CONVERSATION not in supported_targets(ResponseRule)


def test_a_field_rule_is_named_after_its_statement():
    assert FieldRule(field="duration_ms", op="<=", value=5000).name == "duration_ms <= 5000"
    rule = FieldRule(field="span_count", op="==", value=0, span_kind="tool_call", span_name="rm")
    assert rule.name == "span_count(tool.invoke, rm) == 0"
    assert FieldRule(field="output", op="is_json", negate=True).name == "not output is_json"


def test_the_factory_builds_rules_from_their_stored_settings():
    factory = RhesisMetricFactory()

    rule = factory.create("FieldRule", field="status", op="==", value="ok", name="No errors")
    response = factory.create("ResponseRule", match="similar", min_similarity=0.8)

    assert isinstance(rule, FieldRule) and rule.name == "No errors"
    assert isinstance(response, ResponseRule) and response.similarity == "rouge_l"


# ── field rules ──────────────────────────────────────────────────


def test_duration_passes_and_fails_with_the_measured_value():
    rule = FieldRule(field="duration_ms", op="<=", value=5000)

    fast = judged(rule, trace(turn(ms=4210)))
    slow = judged(rule, trace(turn(ms=6000)))

    assert verdict(fast) is True and fast.score == 1.0
    assert fast.details["measured"] == 4210 and fast.details["expected"] == 5000
    assert "4,210" in fast.details["reason"]
    assert verdict(slow) is False and slow.score == 0.0


def test_unknown_timing_is_not_applicable():
    rule = FieldRule(field="duration_ms", op="<=", value=5000)

    result = judged(rule, trace(turn(ms=None)))

    assert result.score is None
    assert result.details["not_applicable"] is True
    assert result.details["is_successful"] is None
    assert "timing" in result.details["reason"]


def test_a_conversation_lasts_from_its_first_turn_to_its_last():
    rule = FieldRule(field="duration_ms", op="<=", value=120000)
    conversation = trace(turn(ms=1000), turn(ms=1000, offset_ms=150000))

    result = judged(rule, conversation)

    assert result.details["measured"] == 151000
    assert verdict(result) is False


def test_status_and_errors():
    ok = FieldRule(field="status", op="==", value="ok")
    no_errors = FieldRule(field="error_count", op="==", value=0)
    failing = trace(turn(children=[span("tool.invoke", "lookup", ms=5, status="ERROR")]))

    assert verdict(judged(ok, trace(turn()))) is True
    assert verdict(judged(FieldRule(field="status", op="==", value="OK"), trace(turn()))) is True
    assert verdict(judged(ok, trace(turn(status="ERROR")))) is False
    assert verdict(judged(no_errors, failing)) is False
    assert judged(no_errors, failing).details["measured"] == 1


def test_span_count_by_kind_and_name():
    t = trace(
        turn(
            children=[
                span("tool.invoke", "lookup_order", ms=5),
                span("tool.invoke", "delete_account", ms=5),
                span("retrieval", ms=5),
            ]
        )
    )

    tools = FieldRule(field="span_count", op="==", value=2, span_kind="tool_call")
    raw_kind = FieldRule(field="span_count", op="==", value=2, span_kind="tool.invoke")
    deletes = FieldRule(
        field="span_count", op="==", value=0, span_kind="tool_call", span_name="delete_account"
    )
    everything = FieldRule(field="span_count", op=">=", value=4)

    assert verdict(judged(tools, t)) is True
    assert verdict(judged(raw_kind, t)) is True
    assert verdict(judged(deletes, t)) is False
    assert verdict(judged(everything, t)) is True


def test_tokens_are_summed_over_model_calls():
    t = trace(
        turn(
            children=[
                model(input_tokens=100, output_tokens=50),
                model(total=30),
                span("agent.invoke", attributes={"ai.llm.tokens.total": 999}),
            ]
        )
    )

    def measured(field):
        return judged(FieldRule(field=field, op=">=", value=0), t).details["measured"]

    assert measured("tokens.input") == 100
    assert measured("tokens.output") == 50
    assert measured("tokens.total") == 180


def test_tokens_nobody_reported_are_not_applicable():
    result = judged(FieldRule(field="tokens.total", op="<=", value=20000), trace(turn()))

    assert result.details["not_applicable"] is True
    assert "usage" in result.details["reason"]


def test_cost_is_summed_or_not_applicable():
    rule = FieldRule(field="cost_usd", op="<=", value=0.05)
    priced = trace(turn(children=[span("llm.invoke", cost=0.02), span("llm.invoke", cost=0.04)]))

    assert verdict(judged(rule, priced)) is False
    assert judged(rule, trace(turn())).details["not_applicable"] is True


def test_output_operators():
    def check(op, value=None, output="Order ORD-123456 is on its way.", negate=False):
        settings = {"field": "output", "op": op, "negate": negate}
        if value is not None:
            settings["value"] = value
        return verdict(FieldRule(**settings).evaluate(output=output))

    assert check("contains", "ORD-")
    assert not check("contains", "refund")
    assert check("matches", r"ORD-[0-9]{6}")
    assert not check("matches", r"^ORD-")
    assert check("is_json", output='{"a": 1}')
    assert not check("is_json")
    assert check("==", "Order ORD-123456 is on its way.")
    assert check("!=", "something else")
    assert check("in", ["a", "Order ORD-123456 is on its way."])
    assert check("not_in", ["a", "b"])
    assert check("matches", r"[\w.]+@[\w.]+", negate=True)
    assert not check("contains", "ORD-", negate=True)


def test_length():
    rule = FieldRule(field="length.output", op="<=", value=10)

    assert verdict(rule.evaluate(output="short")) is True
    assert verdict(rule.evaluate(output="far too long a reply")) is False


def test_attributes_compare_as_text_or_numbers():
    t = trace(
        turn(attributes={"endpoint.response.status": "200", "rhesis.reported.metadata.x": 0.9})
    )

    def check(field, op, value):
        return verdict(judged(FieldRule(field=field, op=op, value=value), t))

    assert check("attributes.endpoint.response.status", "==", 200)
    assert check("attributes.rhesis.reported.metadata.x", ">=", 0.7)
    assert check("attributes.endpoint.response.status", "in", [200, 201])


def test_a_missing_attribute_is_not_applicable_unless_asked_whether_it_exists():
    missing = judged(FieldRule(field="attributes.nope", op="==", value=1), trace(turn()))
    exists = judged(FieldRule(field="attributes.nope", op="exists"), trace(turn()))

    assert missing.details["not_applicable"] is True
    assert verdict(exists) is False


def test_a_value_that_is_not_a_number_fails_a_numeric_rule():
    t = trace(turn(attributes={"attributes_value": "fast"}))

    result = judged(FieldRule(field="attributes.attributes_value", op="<", value=3), t)

    assert verdict(result) is False
    assert "not a number" in result.details["reason"]


@pytest.mark.parametrize(
    "settings, message",
    [
        ({"field": "speed", "op": "<", "value": 1}, "field must be one of"),
        ({"field": "output", "op": "~", "value": 1}, "op must be one of"),
        ({"field": "output", "op": "contains"}, "needs a value"),
        ({"field": "duration_ms", "op": "<", "value": "fast"}, "compares with a number"),
        ({"field": "output", "op": "in", "value": "a"}, "takes a list"),
        ({"field": "output", "op": "matches", "value": "("}, "Invalid regular expression"),
        ({"field": "output", "op": "exists", "value": 1}, "takes no value"),
        ({"field": "output", "op": "exists", "span_kind": "tool_call"}, "only narrow span_count"),
        ({"field": "span_count", "op": "==", "value": 0, "span_kind": "run"}, "not a kind"),
        ({"field": "output", "op": "exists", "extra": 1}, "Unknown settings"),
    ],
)
def test_bad_settings_are_refused(settings, message):
    with pytest.raises(ValueError, match=message):
        FieldRule.validate_config(settings)


def test_validate_config_accepts_stored_settings():
    settings = {"field": "duration_ms", "op": "<=", "value": 5000, "negate": False}

    assert FieldRule.validate_config(settings) == settings


# ── response rules ───────────────────────────────────────────────


def test_response_matches():
    reply = "The capital of France is Paris."

    def check(match, expected, **kwargs):
        rule = ResponseRule(match=match, **kwargs)
        return rule.evaluate(output=reply, expectations=Expectations(response=expected))

    assert verdict(check("exact", " The capital of France is Paris. ")) is True
    assert verdict(check("exact", "Paris.")) is False
    assert verdict(check("contains", "Paris")) is True
    assert verdict(check("matches", r"capital of \w+ is Paris")) is True
    assert verdict(check("matches", r"^Paris")) is False
    similar = check("similar", "the capital of france is paris", min_similarity=0.9)
    assert verdict(similar) is True and similar.details["measured"] == 1.0
    assert verdict(check("similar", "Berlin", min_similarity=0.5)) is False
    edit = check("similar", reply[:-1], similarity="edit_distance", min_similarity=0.9)
    assert verdict(edit) is True


def test_a_response_rule_without_an_expected_response_is_not_applicable():
    result = ResponseRule().evaluate(output="hi", expectations=Expectations())

    assert result.details["not_applicable"] is True


def test_an_invalid_expected_pattern_is_not_applicable():
    result = ResponseRule(match="matches").evaluate(output="hi", expectations="(")

    assert result.details["not_applicable"] is True


@pytest.mark.parametrize(
    "settings, message",
    [
        ({"match": "fuzzy"}, "match must be one of"),
        ({"match": "exact", "min_similarity": 0.5}, "only go with match 'similar'"),
        ({"match": "similar"}, "needs min_similarity"),
        ({"match": "similar", "min_similarity": 2}, "needs min_similarity"),
        ({"match": "similar", "min_similarity": 0.5, "similarity": "cosine"}, "similarity must"),
    ],
)
def test_bad_response_settings_are_refused(settings, message):
    with pytest.raises(ValueError, match=message):
        ResponseRule.validate_config(settings)


def test_similarities():
    assert edit_similarity("kitten", "sitting") == pytest.approx(1 - 3 / 7)
    assert edit_similarity("", "") == 1.0
    assert rouge_l("a b c d", "a c d") == pytest.approx(2 * (3 / 4) * 1 / (3 / 4 + 1))
    assert rouge_l("x", "y") == 0.0
    long = "word " * 600
    assert edit_similarity(long, long + "more") > 0.99


# ── per-unit targets ─────────────────────────────────────────────


def test_each_unit_is_judged_and_units_without_data_are_left_out():
    untimed = span("tool.invoke", "refund", ms=None)
    t = trace(turn(children=[span("tool.invoke", "lookup", ms=300), untimed]))
    rule = FieldRule(field="duration_ms", op="<=", value=2000)

    result = rule.evaluate(trace=t, target="tool_call")

    assert verdict(result) is True
    assert result.details["passed"] == 1
    assert "could not be judged" in result.details["reason"]
    assert [row.get("not_applicable") for row in result.details["spans"]] == [None, True]


def test_when_no_unit_has_the_data_the_rule_is_not_applicable():
    reported = span("tool.invoke", "lookup", attributes={"rhesis.span.source": "reported"})
    rule = FieldRule(field="duration_ms", op="<=", value=2000)

    result = rule.evaluate(trace=trace(turn(children=[reported])), target="tool_call")

    assert result.score is None
    assert result.details["not_applicable"] is True
    assert result.details["is_successful"] is None


def test_every_tool_call_must_succeed():
    t = trace(
        turn(
            children=[
                span("tool.invoke", "lookup", ms=5),
                span("tool.invoke", "refund", ms=5, status="ERROR"),
            ]
        )
    )

    result = FieldRule(field="status", op="==", value="ok").evaluate(trace=t, target="tool_call")

    assert verdict(result) is False
    assert result.details["passed"] == 1
