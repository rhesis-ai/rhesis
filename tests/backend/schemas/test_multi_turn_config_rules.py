"""The rules a saved multi-turn configuration meets, and the SDK's copy of them.

Generated multi-turn tests are checked in the SDK (``multi_turn_config_problem``)
so one that would not save is dropped and regenerated; the parity test keeps that
check in step with ``MultiTurnTestConfig``.
"""

import pytest
from pydantic import ValidationError

from rhesis.backend.app.schemas.multi_turn_test_config import MultiTurnTestConfig
from rhesis.sdk.synthesizers.utils import multi_turn_config_problem

CONFIG = {
    "goal": "Get a refund for a late order",
    "instructions": "Ask politely, then insist.",
    "restrictions": "Never promise a refund without checking the order.",
    "scenario": "A customer whose order is two weeks late.",
    "min_turns": 3,
    "max_turns": 8,
}

CASES = [
    CONFIG,
    {**CONFIG, "goal": "   "},
    {**CONFIG, "goal": ""},
    {**CONFIG, "goal": "x" * 5001},
    {**CONFIG, "instructions": "x" * 10001},
    {**CONFIG, "scenario": "x" * 5001},
    {**CONFIG, "min_turns": 9, "max_turns": 8},
    {**CONFIG, "max_turns": 51},
    {**CONFIG, "min_turns": None, "max_turns": None},
]


@pytest.mark.unit
class TestMultiTurnTestConfigRules:
    def test_a_blank_goal_is_refused_not_stored_as_none(self):
        with pytest.raises(ValidationError):
            MultiTurnTestConfig(**{**CONFIG, "goal": "   "})

    def test_min_turns_above_max_turns_is_refused(self):
        with pytest.raises(ValidationError, match="min_turns cannot be above max_turns"):
            MultiTurnTestConfig(**{**CONFIG, "min_turns": 9, "max_turns": 8})

    def test_whitespace_around_text_is_stripped(self):
        assert MultiTurnTestConfig(**{**CONFIG, "goal": "  a goal  "}).goal == "a goal"

    def test_a_blank_optional_field_becomes_none(self):
        assert MultiTurnTestConfig(**{**CONFIG, "scenario": "  "}).scenario is None


@pytest.mark.unit
class TestTheSdkMirrorsTheRules:
    @pytest.mark.parametrize("config", CASES)
    def test_the_sdk_check_agrees_with_the_save_schema(self, config):
        try:
            MultiTurnTestConfig(**config)
            saves = True
        except ValidationError:
            saves = False

        assert (multi_turn_config_problem(config) is None) == saves
