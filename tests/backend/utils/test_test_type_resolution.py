"""Tests for the shared test-type resolution helper."""

from rhesis.backend.app.constants import TestSetType, TestType
from rhesis.backend.app.utils.test_type_resolution import resolve_effective_test_type


def test_explicit_type_wins():
    result = resolve_effective_test_type(
        explicit_test_type="Single-Turn",
        test_configuration={"goal": "g"},
        prompt={"content": "p"},
        test_set_type="Multi-Turn",
        default_test_type="Multi-Turn",
    )
    assert result == "Single-Turn"


def test_explicit_enum_wins():
    result = resolve_effective_test_type(
        explicit_test_type=TestType.MULTI_TURN, test_set_type="Single-Turn"
    )
    assert result == "Multi-Turn"


def test_goal_config_detects_multi_turn():
    result = resolve_effective_test_type(test_configuration={"goal": "g"})
    assert result == "Multi-Turn"


def test_prompt_detects_single_turn():
    result = resolve_effective_test_type(prompt={"content": "p"})
    assert result == "Single-Turn"


def test_prompt_beats_empty_config():
    result = resolve_effective_test_type(
        test_configuration={}, prompt={"content": "p"}, test_set_type="Multi-Turn"
    )
    assert result == "Single-Turn"


def test_falls_back_to_set_then_default():
    assert (
        resolve_effective_test_type(test_set_type="Multi-Turn", default_test_type="Single-Turn")
        == "Multi-Turn"
    )
    assert resolve_effective_test_type(default_test_type="Single-Turn") == "Single-Turn"


def test_set_type_enum_accepted():
    result = resolve_effective_test_type(test_set_type=TestSetType.MULTI_TURN)
    assert result == "Multi-Turn"


def test_nothing_pins_type_returns_none():
    assert resolve_effective_test_type() is None
