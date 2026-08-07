"""Coordinator turn behaviour end to end over the one-component pipeline."""

import pytest
from haystack.dataclasses import ChatMessage, ToolCall

from tests.mocks import (
    check,
    emergency_script,
    gather_script,
    greeting_script,
    make_pipeline,
    out_of_scope_script,
    stub_generator,
    summary_script,
    text,
    tool_call,
)
from visit_prep.pipeline import (
    COORDINATOR,
    _extract_reply,
    build_coordinator_pipeline,
    run_turn,
)
from visit_prep.state import Phase, Slots, VisitPrepState

FILLED_SLOTS = Slots(
    onset="3 days",
    location="temples",
    character="pressure",
    severity="4/10",
    timing="intermittent",
    aggravating="screens",
    relieving="rest",
    associated="neck stiffness",
)


def test_greeting_turn_increments_counter():
    result = run_turn("hello", VisitPrepState(), pipeline=make_pipeline(greeting_script()))
    assert result["state"].turn == 1
    assert "visit" in result["response"].lower()


def test_emergency_escalates():
    result = run_turn(
        "chest pain and can't breathe",
        VisitPrepState(),
        pipeline=make_pipeline(emergency_script()),
    )
    assert result["state"].phase == Phase.ESCALATED
    assert "911" in result["response"] or "emergency" in result["response"].lower()


def test_out_of_scope_redirects():
    result = run_turn(
        "What do I have?", VisitPrepState(), pipeline=make_pipeline(out_of_scope_script())
    )
    assert "diagnos" in result["response"].lower() or "prescrib" in result["response"].lower()


def test_health_concern_asks_one_question():
    msg = "I have a headache"
    result = run_turn(msg, VisitPrepState(), pipeline=make_pipeline(gather_script(msg)))
    assert result["state"].phase == Phase.GATHERING
    assert result["state"].slots.onset == "2 days ago"
    assert "?" in result["response"]


def test_red_flag_mid_gathering_escalates():
    first_msg = "headache"
    pipeline = make_pipeline(
        [*gather_script(first_msg, question="When did it start?"), *emergency_script()]
    )
    first = run_turn(first_msg, VisitPrepState(), pipeline=pipeline)
    result = run_turn(
        "worst headache of my life with slurred speech", first["state"], pipeline=pipeline
    )
    assert result["state"].phase == Phase.ESCALATED


def test_complete_history_produces_summary():
    filled = VisitPrepState(
        chief_complaint="headache",
        slots=FILLED_SLOTS,
        phase=Phase.GATHERING,
        turn=8,
        history=[{"role": "user", "content": "final detail"}],
    )
    summary = "## Timeline\n- Headache for 3 days\n\n## Questions\n- What tests might help?"
    result = run_turn("that's all", filled, pipeline=make_pipeline(summary_script(summary=summary)))
    assert result["state"].phase == Phase.DONE
    # The critic-approved draft reaches the user verbatim, not the coordinator's paraphrase.
    assert result["response"] == summary


def test_pipeline_has_single_coordinator_component():
    pipe = build_coordinator_pipeline(generator=stub_generator())
    assert list(pipe.graph.nodes) == [COORDINATOR]


def test_history_complete_signal_never_reaches_the_user():
    """The specialist's completion signal is an instruction for the coordinator, not a reply."""
    partial = VisitPrepState(
        chief_complaint="headache",
        slots=FILLED_SLOTS.model_copy(update={"associated": None}),
        phase=Phase.GATHERING,
    )
    result = run_turn(
        "also neck stiffness",
        partial,
        pipeline=make_pipeline(
            gather_script(
                "also neck stiffness",
                slot_args={"associated": "neck stiffness"},
                question="Thanks, I have everything I need.",
                coordinator_reply="Great — that's everything I need.",
            )
        ),
    )
    assert result["state"].slots.associated == "neck stiffness"
    assert "HISTORY_COMPLETE" not in result["response"]
    assert result["response"] == "Great — that's everything I need."


def test_status_line_as_closing_text_is_refused():
    """A model that echoes a status line back must not have it relayed to the user.

    The prompt forbids this, but a prompt cannot enforce it: the echoed line satisfies the
    ``text`` exit condition, so the run ends on it and it would be shipped verbatim.
    """
    msg = "also neck stiffness"
    with pytest.raises(RuntimeError, match="without a user-facing reply"):
        run_turn(
            msg,
            VisitPrepState(),
            pipeline=make_pipeline(
                gather_script(
                    msg,
                    question="Thanks.",
                    coordinator_reply="HISTORY_COMPLETE — every core slot is now filled.",
                )
            ),
        )


@pytest.mark.parametrize(
    "status",
    [
        "HISTORY_COMPLETE — every core slot is now filled. Call write_summary next.",
        "SUMMARY_BLOCKED — core slots still missing: onset.",
        "VERDICT: rejected. Feedback: remove the diagnosis.",
    ],
)
def test_handoff_status_left_as_last_message_is_refused(status):
    """Exhausting ``max_agent_steps`` leaves a handoff's tool result as the last message."""
    last = ChatMessage.from_tool(
        tool_result=status,
        origin=ToolCall(id="call-1", tool_name="gather_history", arguments={}),
    )
    assert _extract_reply({"last_message": last}) == ""


def test_approved_summary_still_reaches_the_user():
    """The guard rejects status lines only — ordinary replies pass through untouched."""
    last = ChatMessage.from_assistant("Where exactly does it hurt?")
    assert _extract_reply({"last_message": last}) == "Where exactly does it hurt?"
    assert _extract_reply({"summary": "## Timeline\n- Headache"}) == "## Timeline\n- Headache"


def test_premature_write_summary_does_not_end_the_conversation():
    """A too-early write_summary must be recoverable, not a reply and not 'done'."""
    result = run_turn(
        "that's everything",
        VisitPrepState(chief_complaint="headache"),
        pipeline=make_pipeline(
            [
                check(),
                tool_call("write_summary"),
                text("Before I summarize — when did it start?"),
            ]
        ),
    )
    assert "SUMMARY_BLOCKED" not in result["response"]
    assert result["response"] == "Before I summarize — when did it start?"
    assert result["state"].phase != Phase.DONE
