"""History specialist / gather_history handoff tests."""

from haystack.dataclasses import ChatRole

from tests.mocks import MockChatGenerator, gather_script, make_pipeline
from visit_prep.pipeline import build_coordinator_pipeline, run_turn
from visit_prep.state import Phase, Slots, VisitPrepState, missing_core_slots


def test_gather_history_fills_slots_then_asks():
    msg = "I have a headache for 2 days"
    result = run_turn(
        msg,
        VisitPrepState(),
        pipeline=make_pipeline(
            gather_script(
                msg,
                slot_args={"chief_complaint": "headache", "onset": "2 days"},
                question="Where do you feel it?",
            )
        ),
    )
    assert result["state"].chief_complaint == "headache"
    assert result["state"].slots.onset == "2 days"
    assert result["state"].phase == Phase.GATHERING
    assert "Where" in result["response"]
    assert missing_core_slots(result["state"])


def test_specialist_receives_slot_status_and_conversation():
    """The specialist must see what is on file and what was already asked.

    Agent State is invisible to the model, so a handoff forwarding only the latest message
    leaves the specialist unable to tell which slot a bare answer like "9" belongs to.
    """
    prior = VisitPrepState(
        chief_complaint="headache",
        slots=Slots(onset="3 days", location="temples"),
        phase=Phase.GATHERING,
        history=[
            {"role": "user", "content": "I have a headache"},
            {"role": "assistant", "content": "How bad is it, from 1 to 10?"},
        ],
    )
    generator = MockChatGenerator(
        gather_script("9", slot_args={"severity": "9"}, question="What makes it worse?")
    )
    run_turn("9", prior, pipeline=build_coordinator_pipeline(generator=generator))

    # Call 3 is the history specialist's first LLM call (calls 1-2 are the coordinator's).
    specialist_messages = generator.calls[2]
    system = "\n".join(m.text or "" for m in specialist_messages if m.is_from(ChatRole.SYSTEM))
    assert "onset: 3 days" in system
    assert "Still missing core slots" in system
    assert "severity" in system

    forwarded = [m.text for m in specialist_messages if m.is_from(ChatRole.USER)]
    assert "I have a headache" in forwarded, "prior user turns must be forwarded"
    assert forwarded[-1] == "9"
    relayed = [m.text for m in specialist_messages if m.is_from(ChatRole.ASSISTANT)]
    assert "How bad is it, from 1 to 10?" in relayed, "the question just asked must be visible"


def test_coordinator_sees_slot_status():
    """The coordinator cannot judge whether history is complete without seeing the slots."""
    state = VisitPrepState(chief_complaint="headache", slots=Slots(onset="3 days"))
    generator = MockChatGenerator(gather_script("it's on my temples"))
    run_turn("it's on my temples", state, pipeline=build_coordinator_pipeline(generator=generator))

    system = "\n".join(m.text or "" for m in generator.calls[0] if m.is_from(ChatRole.SYSTEM))
    assert "Chief complaint: headache" in system
    assert "onset: 3 days" in system
    assert "Still missing core slots" in system
