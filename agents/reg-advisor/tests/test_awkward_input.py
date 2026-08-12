"""Awkward and non-string user input."""

from __future__ import annotations

import pytest

from reg_advisor.classify import classify
from reg_advisor.runner import MAX_MESSAGE_CHARS, run_turn_async
from reg_advisor.safety import text_suggests_scope_flag
from reg_advisor.state import ProductProfile, RegAdvisorState, apply_profile_updates
from reg_advisor.utils import as_text, as_tristate, conversation_transcript
from tests.mocks import MockLlm, build_runner_with, gather_script, greeting_script, make_runner


@pytest.mark.asyncio
async def test_an_empty_message_still_produces_a_turn() -> None:
    result = await run_turn_async("", runner=make_runner(greeting_script()))
    assert result["response"]
    assert result["state"].turn == 1
    assert result["state"].history[0] == {"role": "user", "content": ""}


@pytest.mark.asyncio
async def test_a_whitespace_only_message_is_handled() -> None:
    result = await run_turn_async("   \n\t  ", runner=make_runner(greeting_script()))
    assert result["response"]


@pytest.mark.asyncio
@pytest.mark.parametrize("message", [9, 2.5, True, None, 0, False])
async def test_a_non_string_message_is_coerced(message: object) -> None:
    """An HTTP client can send a bare JSON number, and everything downstream assumes text."""
    result = await run_turn_async(message, runner=make_runner(greeting_script()))
    expected = "" if message is None else str(message)
    assert result["state"].history[0]["content"] == expected


@pytest.mark.asyncio
async def test_a_ten_thousand_character_paste_is_clipped() -> None:
    huge = "Regulation text. " * 700
    assert len(huge) > 10_000

    result = await run_turn_async(huge, runner=make_runner(greeting_script()))
    recorded = result["state"].history[0]["content"]

    assert len(recorded) < len(huge)
    assert len(recorded) <= MAX_MESSAGE_CHARS + 100
    assert "more characters omitted" in recorded


@pytest.mark.asyncio
async def test_non_ascii_survives_the_round_trip() -> None:
    message = "Kann ich das Gerät in Europa verkaufen? 医療機器 — naïve café 🇪🇺"
    result = await run_turn_async(message, runner=make_runner(greeting_script()))
    assert result["state"].history[0]["content"] == message


@pytest.mark.asyncio
async def test_an_apostrophe_heavy_message_is_handled() -> None:
    message = "It's a device that doesn't diagnose — we'd call it 'wellness'."
    result = await run_turn_async(
        message, runner=build_runner_with(MockLlm(gather_script(message)))
    )
    assert result["state"].profile.intended_purpose == message


@pytest.mark.asyncio
async def test_a_slot_value_containing_template_syntax_passes_through_unrendered() -> None:
    """Nothing templates state into a prompt, so braces are ordinary characters."""
    message = "Our claim is {{ oops }} and {% raw %} and {profile_status}."
    result = await run_turn_async(
        message, runner=build_runner_with(MockLlm(gather_script(message)))
    )
    assert result["state"].profile.intended_purpose == message


@pytest.mark.asyncio
async def test_stale_non_string_history_survives_replay() -> None:
    """Pydantic validates on construction but not on assignment, so this can reach us."""
    state = RegAdvisorState()
    state.history = [{"role": "user", "content": 9}]

    result = await run_turn_async("hello", state, runner=make_runner(greeting_script()))
    assert result["state"].turn == 1


# --- the pure layers ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", [9, 2.5, True, None, [], {}, object()])
def test_scope_rules_never_crash_on_a_non_string(value: object) -> None:
    assert text_suggests_scope_flag(value) is False


@pytest.mark.parametrize("value", [9, 2.5, True, [], {"a": 1}])
def test_tristate_never_crashes_on_a_non_string(value: object) -> None:
    assert as_tristate(as_text(value)) in (True, False, None)


def test_a_non_scalar_slot_value_is_dropped_not_stringified() -> None:
    after = apply_profile_updates(
        RegAdvisorState(), {"target_markets": {"eu": True}, "contains_ai": ["yes"]}
    )
    assert after.profile.target_markets is None
    assert after.profile.contains_ai is None


def test_a_numeric_slot_value_is_kept_as_text() -> None:
    after = apply_profile_updates(RegAdvisorState(), {"duration_of_use": 30})
    assert after.profile.duration_of_use == "30"


def test_the_classifier_survives_a_profile_of_junk() -> None:
    determination = classify(
        ProductProfile(
            intended_purpose="🙂 {{ }} ??? ",
            product_description="   ",
            contains_software="maybe?",
        )
    )
    assert determination.regulated is None
    assert determination.unresolved


def test_the_transcript_tolerates_missing_keys() -> None:
    rendered = conversation_transcript([{"content": "no role"}, {"role": "user"}, {}])
    assert rendered == "user: no role"
