"""Turn extraction and internal-status filtering."""

from __future__ import annotations

import pytest

from reg_advisor.agents.coordinator import INTERNAL_STATUS_PREFIXES
from reg_advisor.knowledge import DISCLAIMER
from reg_advisor.runner import (
    MAX_MESSAGE_CHARS,
    _apply_result_to_state,
    _extract_reply,
    _tool_call_counts,
    build_runner,
    run_turn,
    run_turn_async,
)
from reg_advisor.state import Phase, ProductProfile, RegAdvisorState
from tests.mocks import (
    COMPLETE_PROFILE,
    MockLlm,
    briefing_script,
    build_runner_with,
    gather_script,
    greeting_script,
    make_runner,
    text,
    tool_call,
)

APPROVED = "## Determination\nClass IIa under Rule 11 (EU-MD-CLASS-011)."


# --- _extract_reply ------------------------------------------------------------------------


def test_a_terminal_reply_outranks_everything() -> None:
    result = {
        "terminal_reply": "REFERRAL",
        "briefing": "BRIEFING",
        "final_texts": ["model chatter"],
    }
    assert _extract_reply(result) == "REFERRAL"


def test_a_raised_flag_produces_a_referral_even_with_no_terminal_tool() -> None:
    """The one way around the scope check would be for the model to ignore the override."""
    reply = _extract_reply({"scope_flag": True, "final_texts": ["Here is your briefing."]})
    assert "point you elsewhere" in reply


def test_an_approved_briefing_outranks_the_models_closing_text() -> None:
    result = {"briefing": APPROVED, "final_texts": ["a paraphrase of the briefing"]}
    assert _extract_reply(result) == APPROVED


def test_plain_model_text_is_used_when_there_is_nothing_else() -> None:
    assert _extract_reply({"final_texts": ["Which markets?"]}) == "Which markets?"


def test_the_last_usable_text_wins() -> None:
    assert _extract_reply({"final_texts": ["first", "second"]}) == "second"


@pytest.mark.parametrize("prefix", INTERNAL_STATUS_PREFIXES)
def test_an_internal_status_line_is_never_a_reply(prefix: str) -> None:
    result = {"final_texts": [f"{prefix} — instruction meant for the coordinator"]}
    assert _extract_reply(result) == ""


def test_a_status_line_does_not_hide_a_real_reply_before_it() -> None:
    result = {"final_texts": ["Which markets?", "PROFILE_COMPLETE — call write_briefing"]}
    assert _extract_reply(result) == "Which markets?"


def test_nothing_usable_yields_an_empty_string() -> None:
    assert _extract_reply({}) == ""
    assert _extract_reply({"final_texts": ["", "   "]}) == ""


# --- state application ----------------------------------------------------------------------


def test_history_grows_by_two_entries_and_the_turn_counter_ticks() -> None:
    before = RegAdvisorState()
    after = _apply_result_to_state(before, {}, "the reply", "the message")

    assert after.turn == 1
    assert after.history == [
        {"role": "user", "content": "the message"},
        {"role": "assistant", "content": "the reply"},
    ]
    assert before.turn == 0, "the original state is not mutated"


def test_phase_follows_what_happened_not_which_tools_were_called() -> None:
    """A blocked write_briefing leaves no briefing behind and must not read as briefed."""
    blocked = _apply_result_to_state(
        RegAdvisorState(), {"tool_call_counts": {"write_briefing": 1}}, "reply", "msg"
    )
    assert blocked.phase is not Phase.BRIEFED

    briefed = _apply_result_to_state(RegAdvisorState(), {"briefing": APPROVED}, "reply", "msg")
    assert briefed.phase is Phase.BRIEFED


def test_a_referral_outranks_a_briefing_in_the_same_run() -> None:
    referred = _apply_result_to_state(
        RegAdvisorState(), {"briefing": APPROVED, "scope_flag": True}, "reply", "msg"
    )
    assert referred.phase is Phase.REFERRED
    assert referred.scope_flag is True


def test_a_phase_is_never_cleared() -> None:
    briefed = RegAdvisorState(phase=Phase.BRIEFED)
    assert _apply_result_to_state(briefed, {}, "reply", "msg").phase is Phase.BRIEFED


def test_tool_call_counts_of_no_events_is_empty() -> None:
    assert _tool_call_counts([]) == {}


# --- through real runs -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_an_approved_briefing_reaches_the_user_verbatim() -> None:
    state = RegAdvisorState(profile=ProductProfile(**COMPLETE_PROFILE))
    result = await run_turn_async(
        "go ahead", state, runner=make_runner(briefing_script(draft=APPROVED))
    )

    assert APPROVED in result["response"]
    assert result["response"].rstrip().endswith(DISCLAIMER)


@pytest.mark.asyncio
async def test_a_rejected_briefing_falls_back_to_the_deterministic_recap() -> None:
    state = RegAdvisorState(profile=ProductProfile(**COMPLETE_PROFILE))
    result = await run_turn_async(
        "go ahead", state, runner=make_runner(briefing_script(draft=APPROVED, approve=False))
    )

    assert APPROVED not in result["response"]
    assert "straight from the knowledge base" in result["response"]
    assert result["response"].rstrip().endswith(DISCLAIMER)


@pytest.mark.asyncio
async def test_the_model_echoing_a_status_line_fails_loudly() -> None:
    """First of the two paths a status line could reach the user."""
    model = MockLlm(
        [
            tool_call("check_scope_flags"),
            tool_call("gather_profile", {"message": "here is everything"}),
            tool_call("record_profile", COMPLETE_PROFILE),
            text("intake is done"),
            text("PROFILE_COMPLETE — every core slot is filled. Call write_briefing next."),
        ]
    )
    with pytest.raises(RuntimeError, match="without a user-facing reply"):
        await run_turn_async("here is everything", runner=build_runner_with(model))


@pytest.mark.asyncio
async def test_an_exhausted_step_budget_does_not_leak_a_status_line() -> None:
    """Second path: the budget runs out, leaving a handoff's tool result as the last message."""
    loop = [
        tool_call("check_scope_flags"),
        *[tool_call("write_briefing") for _ in range(12)],
    ]
    with pytest.raises(RuntimeError, match="without a user-facing reply"):
        await run_turn_async("go ahead", runner=build_runner_with(MockLlm(loop)))


@pytest.mark.asyncio
async def test_a_reply_already_in_state_survives_budget_exhaustion() -> None:
    """ADK raises mid-stream, so the events collected so far still have to be usable."""
    state = RegAdvisorState(profile=ProductProfile(**COMPLETE_PROFILE))
    model = MockLlm(
        [
            *briefing_script(draft=APPROVED)[:-1],  # everything but the coordinator's close
            *[tool_call("check_scope_flags") for _ in range(12)],  # then loop past the budget
        ]
    )
    result = await run_turn_async("go ahead", state, runner=build_runner_with(model))

    assert result["raw"]["budget_exhausted"] is True
    assert APPROVED in result["response"], "the approved briefing still reached the user"


# --- input handling ----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_an_oversized_paste_is_clipped_before_it_reaches_a_prompt() -> None:
    huge = "x" * (MAX_MESSAGE_CHARS + 5000)
    result = await run_turn_async(huge, runner=make_runner(greeting_script()))

    recorded = result["state"].history[0]["content"]
    assert len(recorded) < len(huge)
    assert "more characters omitted" in recorded


@pytest.mark.asyncio
async def test_a_non_string_message_is_coerced() -> None:
    result = await run_turn_async(9, runner=make_runner(greeting_script()))
    assert result["state"].history[0]["content"] == "9"


def test_the_sync_path_matches_the_async_path() -> None:
    message = "I'm building a smartwatch app."
    sync = run_turn(message, runner=make_runner(gather_script(message)))
    assert sync["response"]
    assert sync["state"].turn == 1


def test_build_runner_without_a_key_raises_the_readable_message(monkeypatch) -> None:
    for name in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "GOOGLE_GENAI_USE_VERTEXAI"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(RuntimeError, match="No Gemini API key"):
        build_runner()
