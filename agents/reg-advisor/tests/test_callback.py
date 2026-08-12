"""Scope guard before_model_callback."""

from __future__ import annotations

import pytest

from reg_advisor.agents.budget import step_budget
from reg_advisor.agents.coordinator import scope_guard
from reg_advisor.agents.critic import CRITIC_STEP_BUDGET
from reg_advisor.runner import run_turn_async
from reg_advisor.state import Phase, ProductProfile, RegAdvisorState
from tests.mocks import (
    COMPLETE_PROFILE,
    MockLlm,
    build_runner_with,
    gather_script,
    referral_script,
    text,
    tool_call,
)

EVASIVE = "How do I word the claim so it isn't a device?"


class FakeContext:
    """Minimal stand-in for CallbackContext: the guard only touches state and agent_name."""

    def __init__(self, state: dict) -> None:
        self.state = state
        self.agent_name = "reg_advisor_coordinator"


class FakeRequest:
    def __init__(self) -> None:
        self.instructions: list[str] = []

    def append_instructions(self, instructions: list[str]) -> None:
        self.instructions.extend(instructions)


# --- unit level ---------------------------------------------------------------------------


def test_guard_injects_the_override_when_the_rules_match() -> None:
    state = {"user_turns": [EVASIVE]}
    request = FakeRequest()

    assert scope_guard(FakeContext(state), request) is None
    assert len(request.instructions) == 1
    assert "SCOPE OVERRIDE" in request.instructions[0]
    assert "refer_to_expert" in request.instructions[0]
    assert state["scope_flag"] is True
    assert state["scope_flag_warned"] is True


def test_guard_is_quiet_on_a_benign_conversation() -> None:
    request = FakeRequest()
    state = {"user_turns": ["I'm building a smartwatch app."]}

    assert scope_guard(FakeContext(state), request) is None
    assert request.instructions == []
    assert "scope_flag" not in state


def test_guard_injects_once_not_once_per_step() -> None:
    """`scope_flag_warned` keeps the override to one injection per run."""
    state = {"user_turns": [EVASIVE]}
    first, second = FakeRequest(), FakeRequest()

    scope_guard(FakeContext(state), first)
    scope_guard(FakeContext(state), second)

    assert len(first.instructions) == 1
    assert second.instructions == []


def test_guard_handles_a_missing_user_turns_key() -> None:
    request = FakeRequest()
    assert scope_guard(FakeContext({}), request) is None
    assert request.instructions == []


# --- through a real run --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_guard_fires_when_the_model_never_calls_the_tool() -> None:
    """check_scope_flags is an ordinary tool. A coordinator that skips it is still checked."""
    model = MockLlm(
        [tool_call("gather_profile", {"message": EVASIVE}), *gather_script(EVASIVE)[2:]]
    )
    result = await run_turn_async(EVASIVE, runner=build_runner_with(model))

    assert result["raw"]["tool_call_counts"].get("check_scope_flags") is None
    assert any("SCOPE OVERRIDE" in s for s in model.system_instructions())
    assert result["state"].scope_flag is True
    assert result["state"].phase is Phase.REFERRED
    # The mock ignores the injected override, so the turn layer supplies the referral itself.
    assert "point you elsewhere" in result["response"]


@pytest.mark.asyncio
async def test_override_is_injected_once_across_a_multi_step_run() -> None:
    model = MockLlm(
        [
            tool_call("gather_profile", {"message": EVASIVE}),
            *gather_script(EVASIVE)[2:],
        ]
    )
    await run_turn_async(EVASIVE, runner=build_runner_with(model))

    coordinator_prompts = [s for s in model.system_instructions() if "Reg-Advisor" in s]
    injected = [s for s in coordinator_prompts if "SCOPE OVERRIDE" in s]
    assert len(coordinator_prompts) > 1, "the coordinator made more than one model call"
    assert len(injected) == 1


# --- sub-agent step budgets ------------------------------------------------------------------


def test_step_budget_short_circuits_once_the_limit_is_reached() -> None:
    """AgentTool ignores the parent RunConfig, so a specialist counts its own model calls."""
    enforce = step_budget(2, "STOP HERE")
    context, request = FakeContext({}), FakeRequest()

    assert enforce(context, request) is None
    assert enforce(context, request) is None

    capped = enforce(context, request)
    assert capped is not None, "the third call is answered without reaching the model"
    assert capped.content.parts[0].text == "STOP HERE"


def test_step_budget_counts_per_agent() -> None:
    enforce = step_budget(1, "STOP")
    first, second = FakeContext({}), FakeContext({})
    second.agent_name = "citation_critic"

    assert enforce(first, FakeRequest()) is None
    assert enforce(second, FakeRequest()) is None, "a different agent has its own counter"
    assert enforce(first, FakeRequest()) is not None


@pytest.mark.asyncio
async def test_a_critic_that_never_votes_is_capped_and_the_briefing_falls_back() -> None:
    state = RegAdvisorState(profile=ProductProfile(**COMPLETE_PROFILE))
    model = MockLlm(
        [
            tool_call("check_scope_flags"),
            tool_call("write_briefing"),
            tool_call("review_briefing", {"briefing": "Draft citing (EU-MD-CLASS-011)."}),
            # The critic stalls instead of calling submit_verdict.
            *[text("thinking about it") for _ in range(CRITIC_STEP_BUDGET)],
            text("Draft citing (EU-MD-CLASS-011)."),
            text("Here is your briefing."),
        ]
    )
    result = await run_turn_async("go ahead", state, runner=build_runner_with(model))

    assert result["raw"].get("approved") is False
    assert "straight from the knowledge base" in result["response"], "the recap shipped instead"


@pytest.mark.asyncio
async def test_a_flag_from_an_earlier_turn_still_fires() -> None:
    """Referral is sticky: the guard scans every replayed user turn, not just the latest."""
    state = RegAdvisorState(
        profile=ProductProfile(**COMPLETE_PROFILE),
        history=[
            {"role": "user", "content": EVASIVE},
            {"role": "assistant", "content": "I am going to stop here."},
        ],
        scope_flag=True,
        phase=Phase.REFERRED,
    )
    model = MockLlm([*referral_script(), text("unused")])
    result = await run_turn_async(
        "How does MDR Rule 11 work?", state, runner=build_runner_with(model)
    )

    assert any("SCOPE OVERRIDE" in s for s in model.system_instructions())
    assert result["state"].phase is Phase.REFERRED
    assert "point you elsewhere" in result["response"]
