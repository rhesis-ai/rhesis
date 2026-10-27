"""The tool call trajectory metric compares the calls made with the calls expected."""

import pytest

from rhesis.sdk.metrics import Expectations, MetricFactory, ToolCallTrajectory


def calls(*names, **arguments):
    """Tool calls as a trace reports them; ``arguments`` gives a call's arguments by name."""
    return [{"name": n, "arguments": arguments.get(n, {}), "output": None} for n in names]


def expect(*names, **arguments):
    return {"tool_calls": [{"name": n, "arguments": arguments.get(n)} for n in names]}


def score(match, actual, expected, arguments="partial"):
    result = ToolCallTrajectory(match=match, arguments=arguments).evaluate(
        tool_calls=actual, expectations=expected
    )
    return result.details["is_successful"]


@pytest.mark.parametrize(
    ("match", "actual", "passed"),
    [
        ("exact", ("lookup", "refund"), True),
        ("exact", ("refund", "lookup"), False),
        ("exact", ("lookup", "log", "refund"), False),
        ("in_order", ("lookup", "log", "refund"), True),
        ("in_order", ("refund", "lookup"), False),
        ("any_order", ("refund", "lookup"), True),
        ("any_order", ("refund", "lookup", "log"), False),
        ("subset", ("lookup",), True),
        ("subset", ("lookup", "log"), False),
        ("superset", ("log", "refund", "lookup"), True),
        ("superset", ("lookup",), False),
    ],
)
def test_each_match_mode(match, actual, passed):
    assert score(match, calls(*actual), expect("lookup", "refund")) is passed


@pytest.mark.parametrize(
    ("mode", "actual_arguments", "passed"),
    [
        ("partial", {"order": 42, "note": "x"}, True),
        ("partial", {"order": 41}, False),
        ("exact", {"order": 42, "note": "x"}, False),
        ("exact", {"order": 42}, True),
        ("ignore", {"order": 41}, True),
    ],
)
def test_each_argument_mode(mode, actual_arguments, passed):
    actual = calls("refund", refund=actual_arguments)
    expected = expect("refund", refund={"order": 42})

    assert score("exact", actual, expected, arguments=mode) is passed


def test_an_expected_call_without_arguments_takes_any():
    assert score("exact", calls("refund", refund={"order": 1}), expect("refund"), "exact")


def test_arguments_recorded_as_text_never_match_listed_keys():
    actual = [{"name": "refund", "arguments": "order=42", "output": None}]

    assert not score("exact", actual, expect("refund", refund={"order": 42}))


@pytest.mark.parametrize("match", ["exact", "in_order", "any_order", "subset", "superset"])
def test_an_empty_expectation_means_no_calls_in_every_mode(match):
    assert score(match, [], {"tool_calls": []})
    assert not score(match, calls("refund"), {"tool_calls": []})


def test_true_is_not_one():
    actual = calls("notify", notify={"urgent": 1})

    assert not score("exact", actual, expect("notify", notify={"urgent": True}))


def test_listing_no_keys_matches_a_call_without_arguments():
    actual = [{"name": "ping", "arguments": None, "output": None}]

    assert score("exact", actual, expect("ping", ping={}))


def test_arguments_recorded_as_text_are_named_in_the_reason():
    actual = [{"name": "refund", "arguments": "order=42", "output": None}]
    result = ToolCallTrajectory().evaluate(
        tool_calls=actual, expectations=expect("refund", refund={"order": 42})
    )

    assert "recorded as text" in result.details["reason"]


def test_the_reason_names_the_first_call_that_differs():
    result = ToolCallTrajectory().evaluate(
        tool_calls=calls("refund"), expectations=expect("lookup", "refund")
    )

    assert result.score == 0.0
    assert result.details["reason"] == "Expected `lookup`; it was never called."
    assert result.details["recall"] == 0.5
    assert result.details["precision"] == 1.0


def test_a_call_out_of_order_names_the_one_it_should_follow():
    result = ToolCallTrajectory().evaluate(
        tool_calls=calls("lookup", "refund"), expectations=expect("refund", "lookup")
    )

    assert result.details["reason"] == (
        "Expected `lookup` after `refund`; it was called with other arguments or out of order."
    )


def test_an_unexpected_call_is_named():
    result = ToolCallTrajectory(match="any_order").evaluate(
        tool_calls=calls("lookup", "delete"), expectations=expect("lookup")
    )

    assert result.details["reason"] == "`delete` was called but not expected."


def test_no_recorded_calls_says_how_to_get_them():
    result = ToolCallTrajectory().evaluate(tool_calls=[], expectations=expect("lookup"))

    assert "map tool_calls" in result.details["reason"]


def test_partial_arguments_pair_each_expected_call_with_a_different_call():
    """Greedy pairing would give both expectations the first call and fail."""
    actual = calls("book", "book")
    actual[0]["arguments"] = {"room": 4, "night": 1}
    actual[1]["arguments"] = {"room": 4, "night": 2}
    expected = {
        "tool_calls": [
            {"name": "book", "arguments": {"room": 4}},
            {"name": "book", "arguments": {"night": 1}},
        ]
    }

    assert score("any_order", actual, expected)


def test_a_long_trace_is_judged_in_one_pass():
    names = [f"tool_{i}" for i in range(300)]
    result = ToolCallTrajectory(match="any_order").evaluate(
        tool_calls=calls(*names[1:], "extra"), expectations=expect(*names)
    )

    assert result.details["reason"] == "Expected `tool_0`; it was never called."


def test_a_test_without_expected_calls_is_refused():
    with pytest.raises(ValueError, match="no expected tool calls"):
        ToolCallTrajectory().evaluate(tool_calls=calls("x"), expectations=Expectations())


def test_it_needs_no_model():
    metric = ToolCallTrajectory()

    assert metric.model is None
    assert not metric.REQUIRES_MODEL
    assert metric.REQUIRED_EXPECTATIONS == ("tool_calls",)


def test_the_factory_builds_it_from_stored_settings():
    metric = MetricFactory.create(
        "rhesis", "ToolCallTrajectory", match="superset", arguments="ignore", model="ignored"
    )

    assert (metric.match.value, metric.arguments.value) == ("superset", "ignore")


def test_an_unknown_mode_is_refused():
    with pytest.raises(ValueError):
        ToolCallTrajectory(match="sometimes")
