"""Expected tool calls per turn: each turn of a conversation held to its own calls."""

from rhesis.sdk.entities.trace import Trace
from rhesis.sdk.metrics import Expectations, ToolCallTrajectory
from rhesis.sdk.metrics.targets import (
    Target,
    TargetKind,
    matching_units,
    unit_expectations,
)

LOOKUP = {"name": "lookup_order"}
REFUND = {"name": "issue_refund"}
CANCEL = {"name": "cancel_order"}


def conversation(*replies):
    """A conversation whose turn i made the tool calls in ``replies[i]``."""
    messages = []
    for index, calls in enumerate(replies):
        messages.append({"role": "user", "content": f"message {index + 1}"})
        messages.append({"role": "assistant", "content": f"reply {index + 1}", "tool_calls": calls})
    return Trace.from_conversation(messages)


class TestExpectations:
    def test_the_conversation_expects_its_turns_calls_in_order(self):
        expectations = Expectations(tool_calls_per_turn=[[LOOKUP], [], [REFUND]])

        assert [call.name for call in expectations.tool_calls] == ["lookup_order", "issue_refund"]

    def test_a_turn_left_open_leaves_the_conversation_open(self):
        # Joining would make turn 2 expect no calls, which the test never said.
        assert Expectations(tool_calls_per_turn=[[LOOKUP], None, [REFUND]]).tool_calls is None

    def test_a_list_of_its_own_wins(self):
        expectations = Expectations(tool_calls=[CANCEL], tool_calls_per_turn=[[LOOKUP]])

        assert [call.name for call in expectations.tool_calls] == ["cancel_order"]

    def test_no_turn_saying_anything_says_nothing(self):
        assert Expectations(tool_calls_per_turn=[None, None]).tool_calls is None

    def test_a_turn_reads_its_own_entry(self):
        expectations = Expectations(tool_calls_per_turn=[[LOOKUP], None])

        assert [call.name for call in expectations.turn_tool_calls(0)] == ["lookup_order"]
        assert expectations.turn_tool_calls(1) is None
        assert expectations.turn_tool_calls(5) is None


class TestUnitExpectations:
    def test_each_turn_is_held_to_its_own_calls(self):
        trace = conversation([LOOKUP], [REFUND], [])
        target = Target(on=TargetKind.TURN)
        expectations = Expectations(tool_calls_per_turn=[[LOOKUP], [REFUND], []])

        held_to = [
            unit_expectations(target, expectations, unit) for unit in matching_units(trace, target)
        ]

        assert [[c.name for c in e.tool_calls] for e in held_to] == [
            ["lookup_order"],
            ["issue_refund"],
            [],
        ]
        assert all(e.tool_calls_per_turn is None for e in held_to)

    def test_a_turn_the_test_says_nothing_about_has_no_calls_to_match(self):
        trace = conversation([LOOKUP], [REFUND])
        target = Target(on=TargetKind.TURN)
        [_, second] = matching_units(trace, target)

        held_to = unit_expectations(target, Expectations(tool_calls_per_turn=[[LOOKUP]]), second)

        assert held_to.tool_calls is None

    def test_one_turn_is_held_to_the_tests_list(self):
        trace = conversation([LOOKUP])
        target = Target(on=TargetKind.TURN)
        [unit] = matching_units(trace, target)

        held_to = unit_expectations(target, Expectations(tool_calls=[LOOKUP]), unit)

        assert [call.name for call in held_to.tool_calls] == ["lookup_order"]

    def test_a_turn_of_a_conversation_isnt_held_to_the_whole_conversations_list(self):
        trace = conversation([LOOKUP], [REFUND])
        target = Target(on=TargetKind.TURN)
        [first, _] = matching_units(trace, target)

        assert (
            unit_expectations(target, Expectations(tool_calls=[LOOKUP]), first).tool_calls is None
        )

    def test_a_span_answers_for_no_tool_calls(self):
        target = Target(on=TargetKind.TOOL_CALL)
        expectations = Expectations(tool_calls_per_turn=[[LOOKUP]])

        held_to = unit_expectations(target, expectations)

        assert held_to.tool_calls is None and held_to.tool_calls_per_turn is None


def test_the_turn_that_misses_its_calls_fails_the_conversation():
    trace = conversation([LOOKUP], [CANCEL], [])
    expectations = Expectations(tool_calls_per_turn=[[LOOKUP], [REFUND], []])

    result = ToolCallTrajectory(match="exact").evaluate(
        trace=trace, expectations=expectations, target="turn"
    )

    assert result.details["is_successful"] is False
    assert [row["is_successful"] for row in result.details["spans"]] == [True, False, True]


def test_the_whole_run_compares_every_turns_calls_in_order():
    trace = conversation([LOOKUP], [REFUND])
    expectations = Expectations(tool_calls_per_turn=[[LOOKUP], [REFUND]])

    result = ToolCallTrajectory(match="exact").evaluate(
        trace=trace, expectations=expectations, target="run"
    )

    assert result.details["is_successful"] is True
