"""Regression tests for span targets: stored data that must keep loading, values matched the
way Postgres matches them, and patterns refused where the two engines disagree or where
Python's matcher could take exponential time.

The pattern cases marked "on Postgres 16" were checked against a Postgres 16 database with
an en_US.utf8 locale."""

import pytest
from pydantic import ValidationError

from rhesis.sdk.agents.architect.plan import ArchitectPlan, MetricSpec
from rhesis.sdk.agents.architect.plan_check import _canonical
from rhesis.sdk.entities.project import Project
from rhesis.sdk.entities.trace import Span, Trace
from rhesis.sdk.metrics import FieldRule
from rhesis.sdk.metrics.conditions import (
    Condition,
    ConditionOp,
    check_backtracking,
    check_portable_pattern,
    number,
)
from rhesis.sdk.metrics.targets import Target, TargetKind

# ---------------------------------------------------------------------------
# The Architect's plan with a span target
# ---------------------------------------------------------------------------


def test_a_plan_with_a_span_target_renders():
    target = Target.spans(kind="tool_call", where=[("app.tier", "==", "gold")])
    plan = ArchitectPlan(metrics=[MetricSpec(name="Gold", description="d", target=target)])

    assert "judges: each tool call where `app.tier` is `gold`" in plan.to_markdown()


def test_a_bare_preset_shows_its_label_and_is_stored_as_its_kind():
    plan = ArchitectPlan(
        metrics=[MetricSpec(name="Calls", description="d", target=TargetKind.TOOL_CALL)]
    )

    assert "judges: Each tool call" in plan.to_markdown()
    assert plan.model_dump(mode="json")["metrics"][0]["target"] == "tool_call"
    assert Target(on=TargetKind.TOOL_CALL).is_bare
    assert not Target.spans(kind="tool_call").is_bare


# ---------------------------------------------------------------------------
# Stored rules keep loading
# ---------------------------------------------------------------------------


def test_a_stored_rule_with_an_empty_list_still_builds():
    rule = FieldRule(field="output", op="in", value=[])

    assert rule.evaluate(output="anything").details["is_successful"] is False
    with pytest.raises(ValueError, match="at least one value"):
        FieldRule.validate_config({"field": "output", "op": "in", "value": []})


def test_a_stored_rule_with_a_list_for_one_value_still_builds():
    FieldRule(field="output", op="==", value=["a"])

    with pytest.raises(ValueError, match="compares with one value"):
        FieldRule.validate_config({"field": "output", "op": "==", "value": ["a"]})


def test_a_stored_rule_with_a_nested_repeat_still_builds():
    rule = FieldRule(field="output", op="matches", value=r"(a+)+b")

    assert rule.evaluate(output="aab").details["is_successful"] is True
    with pytest.raises(ValueError, match="exponential time"):
        FieldRule.validate_config({"field": "output", "op": "matches", "value": r"(a+)+b"})


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("pattern", "named", "instead"),
    [
        # On Postgres 16: plain text, so "aa" doesn't match.
        (r"a{,3}", "{,3}", "{0,3}"),
        # On Postgres 16: a POSIX class, so "x" matches; Python reads a set of characters.
        (r"[[:alpha:]]", "POSIX class", "[A-Za-z]"),
        (r"[[.a.]]", "collating element", "the character itself"),
        (r"[[=e=]]", "equivalence class", None),
        # On Postgres 16: \x41B is one code point, so "AB" doesn't match.
        (r"\x41B", "another hex digit", "the character itself"),
        (r"(a)(?(1)b|c)", "conditional group", None),
        (r"\N{LATIN SMALL LETTER A}", "by name", "the character itself"),
        (r"a{300}", "repeat count", "at most 255"),
        (r"a{1,99999}", "repeat count", "at most 255"),
        # On Postgres 16: \d doesn't take "٣", \s doesn't take U+00A0, \w takes "é".
        (r"\d+", r"\d", "[0-9]"),
        (r"[\d.]", r"\d", "[0-9]"),
        (r"\w", r"\w", "[A-Za-z0-9_]"),
        (r"\s", r"\s", r"[ \t\n\r\f\v]"),
        (r"\S+", r"\S", None),
    ],
)
def test_a_pattern_postgres_reads_differently_is_refused(pattern, named, instead):
    with pytest.raises(ValueError, match="doesn't work the same everywhere") as caught:
        check_portable_pattern(pattern)

    assert named in str(caught.value)
    if instead:
        assert instead in str(caught.value)


# On Postgres 16: "}+" is one or more "}" in both engines.
@pytest.mark.parametrize("pattern", [r"}+", r"\x41", r"\x41-", r"a{255}", r"a{2,3}", r"[0-9]+"])
def test_a_portable_pattern_is_kept(pattern):
    check_portable_pattern(pattern)


@pytest.mark.parametrize(
    "pattern",
    [r"(a+)+", r"(a*)*", r"(a|a)*", r"(a|ab)+", r"((ab)+)*", r"(?:x+y)+", r"(a{2,})+"],
)
def test_a_repeated_group_containing_a_repeat_is_refused(pattern):
    with pytest.raises(ValueError, match="exponential time"):
        check_backtracking(pattern)


def test_a_nested_repeat_that_can_only_match_one_way_is_refused_too():
    # Each repeat ends at a dot, so this is safe, but a check that reads the pattern alone
    # can't tell it from (a+)+.
    with pytest.raises(ValueError, match="exponential time"):
        check_backtracking(r"([a-z]+\.)*com")


@pytest.mark.parametrize(
    "pattern",
    [r"(ab)+", r"(cat|dog)+", r"([0-9]{3}-)?[0-9]{4}", r"(a+)?", r"(ab){2}", r"^ORD-[0-9]+$"],
)
def test_common_patterns_are_kept(pattern):
    check_backtracking(pattern)
    Condition("output", "matches", pattern)


def test_a_target_condition_refuses_a_catastrophic_pattern():
    with pytest.raises(ValidationError, match="exponential time"):
        Condition("output", "matches", r"(a+)+$")


# ---------------------------------------------------------------------------
# Values
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("op", [ConditionOp.EQ, ConditionOp.NE, ConditionOp.CONTAINS])
def test_a_one_value_operator_refuses_a_list(op):
    with pytest.raises(ValidationError, match="compares with one value"):
        Condition("app.tier", op, ["gold", "silver"])


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1_000", None),
        ("٣", None),
        (" 1", None),
        ("1 ", None),
        ("inf", None),
        ("nan", None),
        (" 1 ", 1.0),
        ("\t-2.5e3\n", -2500.0),
        (".5", 0.5),
        ("5.", 5.0),
        ("1e99999", None),
        (10**400, None),
        (True, None),
        (200, 200.0),
    ],
)
def test_number_reads_only_what_postgres_casts(value, expected):
    assert number(value) == expected


def test_a_huge_integer_is_not_a_number_to_compare_with():
    with pytest.raises(ValidationError, match="compares with a number"):
        Condition("duration_ms", "<", 10**400)


def test_a_huge_integer_matches_without_overflowing():
    condition = Condition("app.count", "==", 10**400)

    assert condition.met_by(10**400) is True
    assert condition.met_by(1) is False
    assert Condition("app.count", "in", [10**400]).met_by(str(10**400)) is True


@pytest.mark.parametrize("where", [5, True, "app.tier"])
def test_a_where_that_is_no_list_or_dict_is_a_value_error(where):
    with pytest.raises(ValueError, match="where is a list of conditions"):
        Target.coerce({"on": "tool_call", "where": where})


# ---------------------------------------------------------------------------
# Kinds, where and positional conditions
# ---------------------------------------------------------------------------


def test_a_kind_written_as_a_preset_is_rewritten_only_where_compared_as_a_value():
    target = Target.spans(
        where=[
            ("kind", "!=", "tool_call"),
            ("kind", "not_in", ["retrieval"]),
            ("kind", "contains", "tool_call"),
            ("kind", "matches", "^tool_call$"),
        ]
    )

    assert [c.value for c in target.where] == [
        "tool.invoke",
        ["retrieval"],
        "tool_call",
        "^tool_call$",
    ]


@pytest.mark.parametrize("on", ["turn", "tool_call"])
def test_a_stored_empty_where_loads_as_none(on):
    assert Target.coerce({"on": on, "where": {}}).where is None


def test_a_span_target_with_an_empty_where_list_is_refused():
    with pytest.raises(ValidationError, match="needs conditions"):
        Target.coerce({"on": "span", "where": []})


def test_a_condition_takes_its_parts_in_order():
    assert Condition("app.tier", "==", "gold") == Condition(field="app.tier", op="==", value="gold")
    assert Condition("app.tier", "exists").value is None


# ---------------------------------------------------------------------------
# What a unit reads
# ---------------------------------------------------------------------------


def _span(kind, name, children=(), **attributes):
    attrs = {key.replace("__", "."): value for key, value in attributes.items()}
    return Span(
        span_id=f"{kind}-{name}-{id(attrs)}",
        span_name=name,
        span_type=kind,
        attributes=attrs,
        children=list(children),
    )


def _trace(*roots):
    trace = Trace(trace_id="t1", root_spans=list(roots))
    trace._detail_loaded = True
    return trace


def test_a_conversation_reader_falls_back_to_the_turn_root_s_own_input():
    refund = _span("tool.invoke", "issue_refund", ai__tool__name="issue_refund")
    root = _span(
        "function",
        "chat",
        [refund],
        function__kwargs="Refund my order",
        function__result="Refunded.",
    )
    target = Target.spans(
        kind="tool_call", read={"input": "conversation.input", "output": "conversation.output"}
    )

    [unit] = target.select(_trace(root))

    assert (unit.input, unit.output) == ("Refund my order", "Refunded.")


def test_reading_a_retrieval_s_own_output_gives_the_default_text():
    retrieval = _span(
        "retrieval",
        "kb_search",
        function__kwargs="refunds",
        function__result='["Refunds take 5 days.", "Within 30 days."]',
    )
    trace = _trace(_span("function", "chat", [retrieval]))

    [default] = Target.spans(kind="retrieval").select(trace)
    [explicit] = Target.spans(kind="retrieval", read={"output": "output"}).select(trace)

    assert explicit.output == default.output == "Refunds take 5 days.\n\nWithin 30 days."


# ---------------------------------------------------------------------------
# Clients and the plan check
# ---------------------------------------------------------------------------


def test_trace_attributes_needs_a_project_with_an_id():
    with pytest.raises(ValueError, match="needs a project with an id"):
        Project().trace_attributes()


def test_the_plan_check_compares_values_the_way_matching_does():
    numbers = Target.spans(kind="tool_call", where=[("app.code", "==", 200)])
    texts = Target.spans(kind="tool_call", where=[("app.code", "==", "200")])
    repeated = Target.spans(kind="tool_call", where=[("app.tier", "in", ["x", "x"])])
    single = Target.spans(kind="tool_call", where=[("app.tier", "==", "x")])

    assert _canonical(numbers) == _canonical(texts)
    assert _canonical(repeated) == _canonical(single)
