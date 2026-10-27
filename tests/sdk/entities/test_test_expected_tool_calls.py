"""Tests carry the tool calls they expect, in either test type."""

from rhesis.sdk.entities import Prompt, Test, TestSet

CALLS = [{"name": "lookup_order", "arguments": {"order_id": 42}}, {"name": "issue_refund"}]


def test_a_single_turn_test_sends_only_its_expected_calls():
    test = Test(prompt=Prompt(content="Refund order 42"), expected_tool_calls=CALLS)

    assert test.model_dump()["test_configuration"] == {"expected_tool_calls": CALLS}


def test_a_multi_turn_test_keeps_its_goal_beside_them():
    test = Test(goal="Get a refund", expected_tool_calls=CALLS)

    config = test.model_dump()["test_configuration"]
    assert config["goal"] == "Get a refund"
    assert config["expected_tool_calls"] == CALLS


def test_a_single_turn_test_with_expected_calls_loads_from_the_api():
    test = Test(test_configuration={"expected_tool_calls": [{"name": "lookup_order"}]})

    assert test.test_configuration.goal is None
    assert test.test_configuration.expected_tool_calls[0].name == "lookup_order"


def test_they_join_a_configuration_passed_beside_them():
    test = Test(test_configuration={"goal": "Get a refund"}, expected_tool_calls=CALLS)

    assert test.model_dump()["test_configuration"]["expected_tool_calls"] == CALLS


def test_a_test_set_pushes_them():
    test = Test(
        category="c", requirement="r", prompt=Prompt(content="x"), expected_tool_calls=CALLS
    )

    payload = TestSet(name="Refunds", tests=[test])._test_to_dict(test)

    assert payload["test_configuration"] == {"expected_tool_calls": CALLS}
