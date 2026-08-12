"""Intake specialist question and slot merging."""

from __future__ import annotations

import pytest

from reg_advisor.agents.intake import build_intake_instruction, create_intake_agent
from reg_advisor.runner import run_turn_async
from reg_advisor.state import ProductProfile, RegAdvisorState
from reg_advisor.tools import record_profile
from tests.mocks import (
    COMPLETE_PROFILE,
    MockLlm,
    build_runner_with,
    gather_script,
    text,
    tool_call,
)


class FakeToolContext:
    def __init__(self, state: dict | None = None) -> None:
        self._state = _FakeState(state or {})

    @property
    def state(self) -> "_FakeState":
        return self._state


class _FakeState(dict):
    def to_dict(self) -> dict:
        return dict(self)


class FakeReadonlyContext:
    def __init__(self, state: dict) -> None:
        self.state = state


# --- record_profile ---------------------------------------------------------------------


def test_record_profile_merges_only_what_was_supplied() -> None:
    context = FakeToolContext()
    reply = record_profile(
        intended_purpose="Detects atrial fibrillation.",
        contains_software="yes",
        tool_context=context,
    )

    profile = context.state["profile"]
    assert profile["intended_purpose"] == "Detects atrial fibrillation."
    assert profile["contains_software"] == "yes"
    assert profile["target_markets"] is None
    assert "Recorded: contains_software, intended_purpose" in reply
    assert "Still missing:" in reply


def test_record_profile_never_overwrites_with_a_blank() -> None:
    context = FakeToolContext(
        {"profile": ProductProfile(intended_purpose="Detects AF.").model_dump()}
    )
    record_profile(intended_purpose="   ", target_markets="EU", tool_context=context)

    assert context.state["profile"]["intended_purpose"] == "Detects AF."
    assert context.state["profile"]["target_markets"] == "EU"


def test_record_profile_normalises_a_non_string_scalar() -> None:
    """A model answering a string parameter with a bare number is common enough to keep."""
    context = FakeToolContext()
    record_profile(contains_ai=True, duration_of_use=30, tool_context=context)

    assert context.state["profile"]["contains_ai"] == "True"
    assert context.state["profile"]["duration_of_use"] == "30"


def test_record_profile_drops_a_non_scalar() -> None:
    context = FakeToolContext()
    record_profile(target_markets=["EU", "US"], tool_context=context)
    assert context.state["profile"]["target_markets"] is None


def test_record_profile_reports_completeness_when_nothing_is_missing() -> None:
    context = FakeToolContext()
    reply = record_profile(tool_context=context, **COMPLETE_PROFILE)
    assert "the profile is complete" in reply


# --- the prompt --------------------------------------------------------------------------


def test_instruction_carries_the_profile_and_the_unresolved_list() -> None:
    state = RegAdvisorState(profile=ProductProfile(intended_purpose="Detects AF."))
    payload = {**state.model_dump(), "unresolved": ["contains_ai", "target_markets"]}
    rendered = build_intake_instruction(FakeReadonlyContext(payload))

    assert "exactly ONE question" in rendered
    assert "Detects AF." in rendered
    assert "The classifier stopped on these fields" in rendered
    assert "- contains_ai" in rendered


def test_instruction_omits_the_unresolved_block_when_there_is_none() -> None:
    rendered = build_intake_instruction(FakeReadonlyContext(RegAdvisorState().model_dump()))
    assert "The classifier stopped" not in rendered


def test_intake_agent_exposes_only_its_two_tools() -> None:
    agent = create_intake_agent(MockLlm([]))
    assert sorted(tool.name for tool in agent.tools) == ["classify_product", "record_profile"]


# --- through a real run --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_one_question_per_turn() -> None:
    message = "I'm building a smartwatch app."
    question = "Does it examine specimens taken from the body?"
    result = await run_turn_async(
        message, runner=build_runner_with(MockLlm(gather_script(message, question=question)))
    )
    assert result["response"] == question
    assert result["response"].count("?") == 1


@pytest.mark.asyncio
async def test_slots_merge_back_into_the_conversation_state() -> None:
    """AgentTool forwards the child's state delta, so the coordinator sees what intake wrote."""
    message = "It analyses dermoscopy images for clinicians."
    model = MockLlm(
        gather_script(
            message,
            profile={"product_description": message, "contains_software": "yes"},
        )
    )
    result = await run_turn_async(message, runner=build_runner_with(model))

    assert result["state"].profile.product_description == message
    assert result["state"].profile.contains_software == "yes"


@pytest.mark.asyncio
async def test_profile_complete_is_emitted_only_when_the_conditional_check_passes() -> None:
    """Completeness is recomputed in Python after the specialist runs, never taken on trust."""
    partial = MockLlm(gather_script("something", profile={"intended_purpose": "Detects AF."}))
    await run_turn_async("something", runner=build_runner_with(partial))
    assert partial.remaining == 0, "the coordinator relayed a question, so it kept its turn"

    complete = MockLlm(
        [
            tool_call("check_scope_flags"),
            tool_call("gather_profile", {"message": "here is everything"}),
            tool_call("record_profile", COMPLETE_PROFILE),
            text("Anything else?"),
            tool_call("write_briefing"),
            text("BRIEFING TEXT (EU-MD-CLASS-011)"),
            text("Here is your briefing."),
        ]
    )
    result = await run_turn_async("here is everything", runner=build_runner_with(complete))

    # The intake agent's trailing question is dropped: PROFILE_COMPLETE routed to write_briefing.
    assert result["response"] != "Anything else?"
    assert result["raw"]["tool_call_counts"].get("write_briefing") == 1


@pytest.mark.asyncio
async def test_the_unresolved_list_is_seeded_before_the_specialist_runs() -> None:
    """Computed in Python, not left to a classify_product call the model may never make.

    Without this the unresolved block is always empty and the intake agent falls back to
    declaration order, which is the opposite of what the design claims.
    """
    message = "I'm building a smartwatch app."
    model = MockLlm(gather_script(message))
    result = await run_turn_async(message, runner=build_runner_with(model))

    assert result["raw"]["unresolved"], "the classifier's blockers reached state"

    intake_prompts = [
        str(request.config.system_instruction or "")
        for request in model.requests
        if "exactly ONE question" in str(request.config.system_instruction or "")
    ]
    assert intake_prompts, "the intake agent ran"
    assert "The classifier stopped on these fields" in intake_prompts[0]


@pytest.mark.asyncio
async def test_the_seeded_list_tracks_what_the_classifier_actually_blocked_on() -> None:
    """A profile that only lacks the AI answer must be asked about the AI answer."""
    state = RegAdvisorState(
        profile=ProductProfile(**{**COMPLETE_PROFILE, "contains_ai": "not decided yet"})
    )
    model = MockLlm(gather_script("here you go"))
    result = await run_turn_async("here you go", state, runner=build_runner_with(model))

    assert result["raw"]["unresolved"] == ["contains_ai"]


@pytest.mark.asyncio
async def test_the_specialist_sees_the_prior_conversation() -> None:
    """A bare answer like "no" only makes sense next to the question that prompted it."""
    state = RegAdvisorState(
        profile=ProductProfile(intended_purpose="Detects AF."),
        history=[
            {"role": "user", "content": "I'm building a smartwatch app."},
            {"role": "assistant", "content": "Does it examine specimens?"},
        ],
    )
    model = MockLlm(gather_script("no", profile={"examines_specimens": "no"}))
    await run_turn_async("no", state, runner=build_runner_with(model))

    intake_calls = [
        request
        for request in model.requests
        if "exactly ONE question" in str(request.config.system_instruction or "")
    ]
    # The first intake call carries what the coordinator forwarded.
    forwarded = "\n".join(
        part.text or "" for content in intake_calls[0].contents for part in (content.parts or [])
    )
    assert "Does it examine specimens?" in forwarded
    assert forwarded.count("user: no") == 1, "the current turn is forwarded exactly once"
