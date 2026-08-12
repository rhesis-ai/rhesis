"""Coordinator routing and terminal-tool behaviour."""

from __future__ import annotations

import pytest

from reg_advisor.agents.coordinator import (
    INTERNAL_STATUS_PREFIXES,
    TERMINAL_TOOLS,
    build_coordinator_instruction,
    is_internal_status,
)
from reg_advisor.runner import build_coordinator_agent, run_turn_async
from reg_advisor.state import Phase, ProductProfile, RegAdvisorState
from reg_advisor.tools import NO_SCOPE_FLAG, SCOPE_FLAG_DETECTED, check_scope_flags
from tests.mocks import (
    COMPLETE_PROFILE,
    MockLlm,
    briefing_script,
    build_runner_with,
    gather_script,
    greeting_script,
    make_runner,
    redirect_script,
    referral_script,
    text,
    tool_call,
)


class FakeToolContext:
    def __init__(self, state: dict) -> None:
        self.state = state


class FakeReadonlyContext:
    def __init__(self, state: dict) -> None:
        self.state = state


# --- wiring -----------------------------------------------------------------------------


def test_coordinator_exposes_exactly_the_six_expected_tools() -> None:
    agent = build_coordinator_agent(MockLlm([]))
    assert sorted(tool.name for tool in agent.tools) == [
        "check_scope_flags",
        "gather_profile",
        "greet_and_explain",
        "redirect_to_scope",
        "refer_to_expert",
        "write_briefing",
    ]


def test_handoffs_are_not_terminal_tools() -> None:
    """The coordinator has to see what a specialist returned to decide what comes next."""
    assert "gather_profile" not in TERMINAL_TOOLS
    assert "write_briefing" not in TERMINAL_TOOLS
    assert set(TERMINAL_TOOLS) == {"greet_and_explain", "redirect_to_scope", "refer_to_expert"}


def test_specialists_are_handoffs_not_sub_agents() -> None:
    """AgentTool, never LLM-driven transfer: control has to come back to the coordinator."""
    assert build_coordinator_agent(MockLlm([])).sub_agents == []


def test_instruction_renders_the_profile_picture() -> None:
    state = RegAdvisorState(profile=ProductProfile(intended_purpose="Detects AF."))
    rendered = build_coordinator_instruction(FakeReadonlyContext(state.model_dump()))

    assert "Reg-Advisor" in rendered
    assert "Detects AF." in rendered
    assert "Still missing:" in rendered


# --- the scope tool ------------------------------------------------------------------------


def test_scope_tool_reports_a_clean_conversation() -> None:
    state = {"user_turns": ["I'm building a smartwatch app."]}
    assert check_scope_flags(FakeToolContext(state)) == NO_SCOPE_FLAG
    assert "scope_flag" not in state


def test_scope_tool_detects_and_records_a_flag() -> None:
    state = {"user_turns": ["How do I word the claim so it isn't a device?"]}
    reply = check_scope_flags(FakeToolContext(state))

    assert reply.startswith(SCOPE_FLAG_DETECTED)
    assert "refer_to_expert" in reply
    assert state["scope_flag"] is True


def test_scope_tool_handles_an_empty_conversation() -> None:
    assert "No user message" in check_scope_flags(FakeToolContext({}))


# --- internal status lines ------------------------------------------------------------------


@pytest.mark.parametrize("prefix", INTERNAL_STATUS_PREFIXES)
def test_status_prefixes_are_recognised(prefix: str) -> None:
    assert is_internal_status(f"{prefix} — some instruction for the coordinator")
    assert is_internal_status(f"   {prefix} with leading space")


def test_ordinary_text_is_not_a_status_line() -> None:
    assert not is_internal_status("Here is your regulatory briefing.")
    assert not is_internal_status("")


# --- routing, through real runs ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_greeting_route() -> None:
    result = await run_turn_async("hello", runner=make_runner(greeting_script()))

    assert result["raw"]["tool_call_counts"] == {"check_scope_flags": 1, "greet_and_explain": 1}
    assert "I help product teams" in result["response"]
    assert result["state"].turn == 1


@pytest.mark.asyncio
async def test_redirect_route() -> None:
    result = await run_turn_async(
        "What is the capital of France?", runner=make_runner(redirect_script())
    )
    assert result["raw"]["tool_call_counts"].get("redirect_to_scope") == 1
    assert "outside what I cover" in result["response"]


@pytest.mark.asyncio
async def test_referral_route_sets_the_phase_and_the_flag() -> None:
    result = await run_turn_async(
        "Can you sign off on this?", runner=make_runner(referral_script())
    )
    assert result["raw"]["tool_call_counts"].get("refer_to_expert") == 1
    assert result["state"].phase is Phase.REFERRED
    assert result["state"].scope_flag is True


@pytest.mark.asyncio
async def test_gather_route_reaches_the_intake_specialist() -> None:
    """A specialist's own tool calls run in a separate runner, so assert on what it wrote."""
    message = "I'm building a smartwatch app that flags atrial fibrillation."
    result = await run_turn_async(message, runner=make_runner(gather_script(message)))

    assert result["raw"]["tool_call_counts"].get("gather_profile") == 1
    assert result["state"].profile.intended_purpose == message, "nested record_profile ran"
    assert result["state"].phase is Phase.SCOPING


@pytest.mark.asyncio
async def test_briefing_route_reaches_the_critic() -> None:
    state = RegAdvisorState(profile=ProductProfile(**COMPLETE_PROFILE))
    result = await run_turn_async("go ahead", state, runner=make_runner(briefing_script()))

    assert result["raw"]["tool_call_counts"].get("write_briefing") == 1
    assert result["raw"]["approved"] is True, "the nested critic ran and approved"
    assert result["raw"]["approved_briefing"], "the approved draft was captured at review time"
    assert result["state"].phase is Phase.BRIEFED


# --- terminal tools end the run; handoffs do not --------------------------------------------


@pytest.mark.asyncio
async def test_a_terminal_tool_ends_the_run_immediately() -> None:
    """The scripted replies after the terminal tool must go unused."""
    model = MockLlm([*greeting_script(), tool_call("write_briefing"), text("never reached")])
    result = await run_turn_async("hello", runner=build_runner_with(model))

    assert model.remaining == 2, "nothing after the terminal tool was consumed"
    assert result["raw"]["tool_call_counts"].get("write_briefing") is None


@pytest.mark.asyncio
async def test_a_handoff_does_not_end_the_run() -> None:
    """gather_profile returns to the coordinator, which then closes the turn itself."""
    message = "I'm building a smartwatch app."
    model = MockLlm(gather_script(message, coordinator_reply="So, one question:"))
    result = await run_turn_async(message, runner=build_runner_with(model))

    assert model.remaining == 0, "the coordinator consumed its closing turn after the handoff"
    assert result["response"] == "So, one question:"


@pytest.mark.asyncio
async def test_a_premature_briefing_is_recoverable_not_fatal() -> None:
    """BRIEFING_BLOCKED steers the model back and leaves no briefing behind."""
    message = "I'm building something."
    model = MockLlm(
        [
            tool_call("check_scope_flags"),
            tool_call("write_briefing"),
            *gather_script(message)[1:],
        ]
    )
    result = await run_turn_async(message, runner=build_runner_with(model))

    assert result["raw"].get("briefing") in (None, "")
    assert result["state"].phase is not Phase.BRIEFED
    assert not is_internal_status(result["response"])
