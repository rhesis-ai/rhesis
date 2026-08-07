from visit_prep.state import CORE_SLOTS, Phase, Slots, VisitPrepState, missing_core_slots


def test_missing_core_slots():
    state = VisitPrepState(slots=Slots(onset="yesterday"))
    missing = missing_core_slots(state)
    assert "onset" not in missing
    assert "location" in missing


def test_missing_core_slots_treats_blank_as_missing():
    state = VisitPrepState(slots=Slots(onset="", location="   "))
    missing = missing_core_slots(state)
    assert "onset" in missing
    assert "location" in missing


def test_core_slots_excludes_context():
    assert "context" not in CORE_SLOTS


def test_apply_slot_updates():
    from visit_prep.state import apply_slot_updates

    state = VisitPrepState()
    updated = apply_slot_updates(state, {"onset": "2 days ago", "location": None})
    assert updated.slots.onset == "2 days ago"
    assert updated.slots.location is None


def test_apply_slot_updates_ignores_blank_values():
    from visit_prep.state import apply_slot_updates

    state = VisitPrepState(slots=Slots(onset="2 days ago"))
    updated = apply_slot_updates(state, {"onset": "", "location": "   "})
    # Blank updates must not overwrite a filled slot or fill an empty one.
    assert updated.slots.onset == "2 days ago"
    assert updated.slots.location is None


def test_phase_values():
    assert Phase.GATHERING.value == "gathering"


def test_describe_slots_reports_known_and_missing():
    from visit_prep.state import describe_slots

    state = VisitPrepState(chief_complaint="headache", slots=Slots(onset="3 days"))
    text = describe_slots(state)
    assert "Chief complaint: headache" in text
    assert "- onset: 3 days" in text
    assert "Still missing core slots:" in text
    assert "location" in text


def test_describe_slots_announces_a_complete_history():
    from visit_prep.state import describe_slots

    state = VisitPrepState(
        chief_complaint="headache",
        slots=Slots(
            onset="3 days",
            location="temples",
            character="pressure",
            severity="4/10",
            timing="intermittent",
            aggravating="screens",
            relieving="rest",
            associated="none",
        ),
    )
    assert "the history is complete" in describe_slots(state)


def test_state_from_slots_tolerates_a_non_dict_payload():
    from visit_prep.state import state_from_slots

    assert state_from_slots(None, None).slots.onset is None
    assert state_from_slots("headache", {"onset": "2 days"}).chief_complaint == "headache"
