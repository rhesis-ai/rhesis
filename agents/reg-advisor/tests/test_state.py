"""State model and conditional core-slot logic."""

from __future__ import annotations

from reg_advisor.state import (
    ALWAYS_CORE,
    PROFILE_FIELDS,
    Phase,
    ProductProfile,
    RegAdvisorState,
    apply_profile_updates,
    describe_profile,
    missing_core_profile_slots,
    profile_from_state,
    state_from_payload,
)


def state(**profile_kwargs: str) -> RegAdvisorState:
    return RegAdvisorState(profile=ProductProfile(**profile_kwargs))


# --- the conditional core -----------------------------------------------------------------


def test_empty_profile_is_missing_every_always_core_slot() -> None:
    missing = missing_core_profile_slots(RegAdvisorState())
    assert set(ALWAYS_CORE) <= set(missing)


def test_software_only_product_does_not_require_invasiveness() -> None:
    """The enrichment over a flat core list: physical questions for physical products only."""
    software = state(
        intended_purpose="Flags a possible lesion for a physician to review.",
        product_description="A cloud service analysing dermoscopy images.",
        product_family="software as a medical device",
        target_markets="EU and US",
        contains_software="yes",
        contains_ai="yes",
        examines_specimens="no",
        influences_clinical_decision="yes",
        existing_certification="none",
    )
    missing = missing_core_profile_slots(software)
    assert "invasiveness" not in missing
    assert "duration_of_use" not in missing
    assert missing == []


def test_physical_product_does_require_invasiveness_and_duration() -> None:
    physical = state(
        intended_purpose="Treats a wound.",
        product_description="A sterile dressing.",
        product_family="medical device",
        target_markets="EU",
        contains_software="no",
        contains_ai="no",
        examines_specimens="no",
        existing_certification="none",
    )
    missing = missing_core_profile_slots(physical)
    assert "invasiveness" in missing
    assert "duration_of_use" in missing


def test_software_with_hardware_still_counts_as_physical() -> None:
    """Software plus a wearable sensor is not software-only, so the physical slots return."""
    hybrid = state(
        intended_purpose="Monitors a patient after surgery.",
        product_description="An app paired with a wearable sensor patch.",
        product_family="software and hardware device",
        target_markets="US",
        contains_software="yes",
        contains_ai="no",
        examines_specimens="no",
        influences_clinical_decision="yes",
        existing_certification="none",
    )
    assert "invasiveness" in missing_core_profile_slots(hybrid)


def test_specimen_question_drops_away_once_the_family_is_settled_elsewhere() -> None:
    unsettled = state(intended_purpose="Something.", product_description="Something.")
    assert "examines_specimens" in missing_core_profile_slots(unsettled)

    settled = state(
        intended_purpose="Treats hypertension.",
        product_description="An oral tablet.",
        product_family="medicinal product",
        target_markets="EU",
        contains_software="no",
        contains_ai="no",
        invasiveness="not applicable",
        duration_of_use="daily, long term",
        existing_certification="none",
    )
    assert "examines_specimens" not in missing_core_profile_slots(settled)


def test_specimen_question_stays_while_the_family_is_ivd_plausible() -> None:
    plausible = state(product_family="diagnostic test kit")
    assert "examines_specimens" in missing_core_profile_slots(plausible)


def test_clinical_decision_question_drops_away_for_a_product_with_no_software() -> None:
    no_software = state(contains_software="no")
    assert "influences_clinical_decision" not in missing_core_profile_slots(no_software)

    with_software = state(contains_software="yes")
    assert "influences_clinical_decision" in missing_core_profile_slots(with_software)


def test_missing_slots_are_returned_in_ask_order() -> None:
    missing = missing_core_profile_slots(RegAdvisorState())
    assert missing.index("intended_purpose") < missing.index("product_description")
    assert missing.index("product_description") < missing.index("target_markets")


# --- merging ------------------------------------------------------------------------------


def test_updates_merge_into_a_copy() -> None:
    before = state(intended_purpose="Detects a condition.")
    after = apply_profile_updates(before, {"target_markets": "EU only"})

    assert after.profile.target_markets == "EU only"
    assert before.profile.target_markets is None, "the original must not be mutated"


def test_blank_values_never_overwrite_a_filled_slot() -> None:
    before = state(intended_purpose="Detects atrial fibrillation.")
    after = apply_profile_updates(
        before,
        {"intended_purpose": "", "product_description": "   ", "target_markets": "US"},
    )

    assert after.profile.intended_purpose == "Detects atrial fibrillation."
    assert after.profile.product_description is None
    assert after.profile.target_markets == "US"


def test_unknown_keys_are_ignored() -> None:
    after = apply_profile_updates(RegAdvisorState(), {"nonsense": "value", "target_markets": "EU"})
    assert after.profile.target_markets == "EU"
    assert not hasattr(after.profile, "nonsense")


def test_non_string_values_are_coerced_and_trimmed() -> None:
    after = apply_profile_updates(RegAdvisorState(), {"contains_ai": True, "target_markets": 1})
    assert after.profile.contains_ai == "True"
    assert after.profile.target_markets == "1"


# --- rendering ----------------------------------------------------------------------------


def test_describe_profile_shows_nothing_yet_when_empty() -> None:
    rendered = describe_profile(RegAdvisorState())
    assert "nothing yet" in rendered
    assert "Still missing:" in rendered


def test_describe_profile_lists_what_is_known_and_what_is_left() -> None:
    rendered = describe_profile(state(intended_purpose="Detects atrial fibrillation."))
    assert "Detects atrial fibrillation." in rendered
    assert "Still missing:" in rendered
    assert "Intended purpose" in rendered


def test_describe_profile_reports_completeness_and_determinations() -> None:
    complete = RegAdvisorState(
        profile=ProductProfile(
            intended_purpose="Flags a possible lesion for a physician to review.",
            product_description="A cloud service analysing dermoscopy images.",
            product_family="software as a medical device",
            target_markets="EU and US",
            contains_software="yes",
            contains_ai="yes",
            examines_specimens="no",
            influences_clinical_decision="yes",
            existing_certification="none",
        ),
        determinations=["EU-MD-CLASS-011"],
    )
    rendered = describe_profile(complete)
    assert "complete enough to classify" in rendered
    assert "EU-MD-CLASS-011" in rendered


def test_describe_profile_reports_a_raised_scope_flag() -> None:
    flagged = RegAdvisorState(scope_flag=True)
    assert "scope flag has been raised" in describe_profile(flagged)


# --- rebuilding from a framework payload ----------------------------------------------------


def test_profile_from_state_tolerates_a_non_dict() -> None:
    assert profile_from_state("not a dict") == ProductProfile()
    assert profile_from_state(None) == ProductProfile()


def test_profile_from_state_keeps_known_fields_only() -> None:
    rebuilt = profile_from_state({"target_markets": "EU", "junk": "ignored"})
    assert rebuilt.target_markets == "EU"
    assert set(rebuilt.model_dump()) == set(PROFILE_FIELDS)


def test_state_from_payload_round_trips() -> None:
    original = RegAdvisorState(
        turn=3,
        phase=Phase.CLASSIFIED,
        profile=ProductProfile(target_markets="US"),
        history=[{"role": "user", "content": "hello"}],
        scope_flag=True,
        determinations=["US-SW-CDS-3060"],
    )
    rebuilt = state_from_payload(original.model_dump())
    assert rebuilt == original


def test_state_from_payload_fills_defaults_for_an_empty_dict() -> None:
    rebuilt = state_from_payload({})
    assert rebuilt.turn == 0
    assert rebuilt.phase is Phase.IDLE
    assert rebuilt.profile == ProductProfile()


def test_phase_serialises_as_its_value() -> None:
    assert Phase.REFERRED == "referred"
    assert RegAdvisorState(phase=Phase.BRIEFED).model_dump()["phase"] == "briefed"
