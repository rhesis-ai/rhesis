"""Tests for TestSetBulkCreate's set-vs-test type enforcement.

A test set and its tests cannot disagree about their turn type, and a payload
mixing both shapes must fail with an actionable message instead of persisting
silently.
"""

import pytest
from pydantic import ValidationError

from rhesis.backend.app.constants import TestSetType, TestType
from rhesis.backend.app.schemas.test_set import TestSetBulkCreate


def _single_turn_test(requirement="req", category="cat", topic="topic"):
    return {
        "requirement": requirement,
        "category": category,
        "topic": topic,
        "prompt": {"content": "A plain prompt"},
    }


def _multi_turn_test(requirement="req", category="cat", topic="topic"):
    return {
        "requirement": requirement,
        "category": category,
        "topic": topic,
        "test_configuration": {"goal": "Keep context across turns"},
    }


def _payload(test_set_type, tests):
    return {"name": "Test set", "test_set_type": test_set_type, "tests": tests}


def test_multi_turn_set_rejects_prompt_only_test():
    with pytest.raises(ValidationError) as exc_info:
        TestSetBulkCreate(**_payload(TestSetType.MULTI_TURN, [_single_turn_test()]))
    message = str(exc_info.value)
    assert "Single-Turn" in message
    assert "declared Multi-Turn" in message


def test_single_turn_set_rejects_goal_test():
    with pytest.raises(ValidationError) as exc_info:
        TestSetBulkCreate(**_payload(TestSetType.SINGLE_TURN, [_multi_turn_test()]))
    message = str(exc_info.value)
    assert "Multi-Turn" in message
    assert "declared Single-Turn" in message


def test_mixed_payload_rejected_as_single_turn():
    with pytest.raises(ValidationError) as exc_info:
        TestSetBulkCreate(
            **_payload(TestSetType.SINGLE_TURN, [_single_turn_test(), _multi_turn_test()])
        )
    assert "split" in str(exc_info.value)


def test_mixed_payload_rejected_as_multi_turn():
    with pytest.raises(ValidationError) as exc_info:
        TestSetBulkCreate(
            **_payload(TestSetType.MULTI_TURN, [_single_turn_test(), _multi_turn_test()])
        )
    assert "split" in str(exc_info.value)


def test_uniform_single_turn_payload_succeeds():
    test_set = TestSetBulkCreate(
        **_payload(TestSetType.SINGLE_TURN, [_single_turn_test(), _single_turn_test()])
    )
    assert test_set.test_set_type == TestSetType.SINGLE_TURN


def test_uniform_multi_turn_payload_succeeds():
    test_set = TestSetBulkCreate(
        **_payload(TestSetType.MULTI_TURN, [_multi_turn_test(), _multi_turn_test()])
    )
    assert test_set.test_set_type == TestSetType.MULTI_TURN


def test_explicit_test_type_wins_over_content():
    # Explicit test_type beats auto-detection, so this matches a Multi-Turn set
    # even though the test carries a prompt.
    test = _single_turn_test()
    test["test_type"] = TestType.MULTI_TURN
    test_set = TestSetBulkCreate(**_payload(TestSetType.MULTI_TURN, [test]))
    assert test_set.tests[0].test_type == TestType.MULTI_TURN


def test_explicit_mismatched_test_type_rejected():
    test = _multi_turn_test()
    test["test_type"] = TestType.SINGLE_TURN
    with pytest.raises(ValidationError) as exc_info:
        TestSetBulkCreate(**_payload(TestSetType.MULTI_TURN, [test]))
    message = str(exc_info.value)
    assert "test 0 is Single-Turn" in message
    assert "declared Multi-Turn" in message


def test_loose_casing_set_type_still_enforced():
    with pytest.raises(ValidationError):
        TestSetBulkCreate(**_payload("multi-turn", [_single_turn_test()]))


def test_error_names_offending_test_index():
    with pytest.raises(ValidationError) as exc_info:
        TestSetBulkCreate(
            **_payload(
                TestSetType.MULTI_TURN,
                [_multi_turn_test(), _multi_turn_test(), _single_turn_test()],
            )
        )
    assert "test 2 is Single-Turn" in str(exc_info.value)
