from dr_rhesis.state import CORE_SLOTS, Phase, Slots, DrRhesisState, missing_core_slots


def test_missing_core_slots():
    state = DrRhesisState(slots=Slots(onset="yesterday"))
    missing = missing_core_slots(state)
    assert "onset" not in missing
    assert "location" in missing


def test_core_slots_excludes_context():
    assert "context" not in CORE_SLOTS


def test_apply_slot_updates():
    from dr_rhesis.state import apply_slot_updates

    state = DrRhesisState()
    updated = apply_slot_updates(state, {"onset": "2 days ago", "location": None})
    assert updated.slots.onset == "2 days ago"
    assert updated.slots.location is None


def test_phase_values():
    assert Phase.GATHERING.value == "gathering"
