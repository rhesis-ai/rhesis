from visit_prep.state import CORE_SLOTS, Phase, Slots, VisitPrepState, missing_core_slots


def test_missing_core_slots():
    state = VisitPrepState(slots=Slots(onset="yesterday"))
    missing = missing_core_slots(state)
    assert "onset" not in missing
    assert "location" in missing


def test_core_slots_excludes_context():
    assert "context" not in CORE_SLOTS


def test_apply_slot_updates():
    from visit_prep.state import apply_slot_updates

    state = VisitPrepState()
    updated = apply_slot_updates(state, {"onset": "2 days ago", "location": None})
    assert updated.slots.onset == "2 days ago"
    assert updated.slots.location is None


def test_phase_values():
    assert Phase.GATHERING.value == "gathering"
