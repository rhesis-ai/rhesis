from dr_rhesis.agents.gathering import GatheringBrain, SlotExtraction
from dr_rhesis.state import DrRhesisState
from dr_rhesis.utils import normalize_slot_payload
from tests.mocks import MockChatGenerator


def test_normalize_slot_payload_coerces_int_severity():
    payload = {"severity": 4}
    normalized = normalize_slot_payload(payload)
    assert normalized["severity"] == "4"
    extraction = SlotExtraction.model_validate(normalized)
    assert extraction.severity == "4"


def test_extract_accepts_numeric_severity_from_llm():
    gen = MockChatGenerator(['{"severity": 4}'])
    brain = GatheringBrain(generator=gen)
    state = DrRhesisState(
        chief_complaint="nausea",
        history=[{"role": "user", "content": "4"}],
    )
    updated = brain.extract("4", state)
    assert updated.slots.severity == "4"


def test_gathering_extracts_and_asks_one_question():
    gen = MockChatGenerator(
        [
            '{"chief_complaint": "headache", "onset": "3 days ago"}',
            '{"target_slot": "location", "question": "Where do you feel the headache?"}',
        ]
    )
    brain = GatheringBrain(generator=gen)
    state = DrRhesisState(
        history=[{"role": "user", "content": "I have a headache for a few days"}]
    )
    result = brain.run(message="It started 3 days ago", state=state)
    assert result["state"].chief_complaint == "headache"
    assert result["state"].slots.onset == "3 days ago"
    assert "?" in result["question"]
    assert gen._calls
