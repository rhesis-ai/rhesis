"""Deterministic decision-tree classification.

Every branch of every tree is exercised by the CASES table below, and
`test_every_branch_is_covered` fails if the knowledge base grows a branch no case reaches. No
mocks and no model — this whole module runs on pure functions.
"""

from __future__ import annotations

import pytest

from reg_advisor.classify import Determination, classify, render_determination
from reg_advisor.knowledge import get_knowledge_base
from reg_advisor.state import ProductProfile


def profile(**kwargs: str) -> ProductProfile:
    """A profile with the always-core slots filled, overridden per case."""
    defaults = {
        "target_markets": "EU and US",
        "contains_software": "no",
        "contains_ai": "no",
        "examines_specimens": "no",
        "existing_certification": "none",
    }
    return ProductProfile(**{**defaults, **kwargs})


# Each case: a name, a profile, and the branch every tree it reaches must pick.
CASES: list[tuple[str, ProductProfile, dict[str, str]]] = [
    (
        "consumer fitness tracker with an explicit disclaimer",
        profile(
            intended_purpose=(
                "General fitness and wellbeing tracking. Not intended to diagnose, treat, cure "
                "or prevent any disease."
            ),
            product_description="Consumer smartwatch app showing step count and sleep quality.",
            contains_software="yes",
            influences_clinical_decision="no",
        ),
        {
            "qualification": "wellness_no_medical_purpose",
            "eu_classification": "eu_not_a_device",
            "us_pathway": "us_general_wellness",
            "conformity_route": "eu_no_conformity_route",
            "clinical_evidence": "no_clinical_evidence_regime",
        },
    ),
    (
        "PPG atrial fibrillation app - Rule 11 IIa in the EU, a device in the US",
        profile(
            intended_purpose=(
                "Estimates the risk of atrial fibrillation and tells the user to seek review."
            ),
            product_description=(
                "Mobile app analysing the photoplethysmography waveform from a smartwatch."
            ),
            contains_software="yes",
            contains_ai="yes",
            influences_clinical_decision="yes",
        ),
        {
            "qualification": "medical_purpose",
            "product_family": "software_medical_device",
            "eu_classification": "eu_software_rule11_iia",
            "us_pathway": "us_predicate_unknown",
            "conformity_route": "eu_notified_body",
            "ai_act_stack": "ai_high_risk",
            "clinical_evidence": "device_evidence",
            "change_triggers": "ai_enabled_change",
            "legacy_transition": "no_existing_certification",
        },
    ),
    (
        "clinician guideline lookup - Non-Device CDS in the US, Class IIa in the EU",
        profile(
            intended_purpose=(
                "Surfaces the relevant published guideline so a physician can independently "
                "review the basis for the treatment recommendation."
            ),
            product_description="Web tool for clinicians summarising published guidelines.",
            contains_software="yes",
            influences_clinical_decision="yes",
        ),
        {
            "eu_classification": "eu_software_rule11_iia",
            "us_pathway": "us_non_device_cds",
            "ai_act_stack": "no_ai",
            "change_triggers": "device_change",
        },
    ),
    (
        "ward vital-signs monitor software - Rule 11 IIb",
        profile(
            intended_purpose=(
                "Monitors vital signs on the ward and alerts the care team to serious "
                "deterioration."
            ),
            product_description="Reads the continuous waveform from a bedside patient monitor.",
            contains_software="yes",
            influences_clinical_decision="yes",
        ),
        {
            "eu_classification": "eu_software_rule11_iib",
            "us_pathway": "us_predicate_unknown",
        },
    ),
    (
        "radiotherapy dosing software - Rule 11 III and a US PMA",
        profile(
            intended_purpose=(
                "Recommends a radiotherapy dose. An incorrect recommendation could cause death "
                "or irreversible deterioration."
            ),
            product_description="Treatment planning software used by radiation oncologists.",
            contains_software="yes",
            influences_clinical_decision="yes",
        ),
        {
            "eu_classification": "eu_software_rule11_iii",
            "us_pathway": "us_pma",
        },
    ),
    (
        "clinical record transfer software - outside Rule 11, so Class I self-declared",
        profile(
            intended_purpose="Stores and transmits patient records to support treatment.",
            product_description="Integration middleware between two hospital systems.",
            contains_software="yes",
            contains_ai="yes",
            influences_clinical_decision="no",
        ),
        {
            "eu_classification": "eu_device_active",
            "conformity_route": "eu_self_declared",
            "ai_act_stack": "ai_not_high_risk",
            "us_pathway": "us_predicate_unknown",
            "change_triggers": "ai_enabled_change",
        },
    ),
    (
        "skin cooling pad - non-invasive physical device",
        profile(
            intended_purpose="Cools the skin to alleviate pain after a minor procedure.",
            product_description="A reusable gel pad applied to intact skin.",
            invasiveness="non-invasive, sits on the skin surface",
            duration_of_use="transient, under 60 minutes",
        ),
        {
            "product_family": "medical_device",
            "eu_classification": "eu_device_noninvasive",
            "conformity_route": "eu_self_declared",
            "clinical_evidence": "device_evidence",
            "change_triggers": "device_change",
        },
    ),
    (
        "implanted cardiac lead - invasive, and failure is fatal",
        profile(
            intended_purpose=(
                "Paces the heart to treat symptomatic bradycardia. Lead failure could cause "
                "death or irreversible harm."
            ),
            product_description="A permanently implanted cardiac pacing lead.",
            invasiveness="surgically invasive, implanted",
            duration_of_use="long term, permanent implant",
        ),
        {
            "eu_classification": "eu_device_invasive_long_term",
            "conformity_route": "eu_notified_body",
            "us_pathway": "us_pma",
        },
    ),
    (
        "biopsy needle - invasive but transient, so the lowest invasive band",
        profile(
            intended_purpose="Takes a tissue sample to support diagnosis of a lesion.",
            product_description="A single-use biopsy needle.",
            invasiveness="surgically invasive",
            duration_of_use="transient, a single procedure under 60 minutes",
        ),
        {
            "eu_classification": "eu_device_invasive_transient",
            "conformity_route": "eu_notified_body",
        },
    ),
    (
        "indwelling catheter - invasive, short term",
        profile(
            intended_purpose="Drains urine to treat urinary retention after surgery.",
            product_description="An indwelling urinary catheter.",
            invasiveness="invasive, via a body orifice",
            duration_of_use="short term, under 30 days",
        ),
        {
            "eu_classification": "eu_device_invasive",
            "conformity_route": "eu_notified_body",
        },
    ),
    (
        "device with no predicate stated outright",
        profile(
            intended_purpose="Detects an early marker of disease at the point of care.",
            product_description="A handheld optical reader. There is no predicate on the market.",
            invasiveness="non-invasive",
            duration_of_use="transient",
        ),
        {"us_pathway": "us_denovo"},
    ),
    (
        "companion diagnostic - IVDR Rule 3(f) Class C",
        profile(
            intended_purpose=(
                "Companion diagnostic used to select patients for a targeted oncology therapy."
            ),
            product_description="A tissue assay run on a biopsy specimen.",
            product_family="in vitro diagnostic",
            examines_specimens="yes",
        ),
        {
            "product_family": "ivd",
            "eu_classification": "eu_ivd_companion_class_c",
            "us_pathway": "us_companion_diagnostic",
            "conformity_route": "eu_ivd_notified_body",
            "clinical_evidence": "ivd_evidence",
        },
    ),
    (
        "general laboratory washing solution - the only self-certified IVD category",
        profile(
            intended_purpose="Used in the preparation of specimens for diagnostic testing.",
            product_description="A general laboratory washing solution, supplied non-sterile.",
            product_family="in vitro diagnostic, Class A general laboratory reagent",
            examines_specimens="yes",
        ),
        {
            "eu_classification": "eu_ivd_annexviii",
            "conformity_route": "eu_ivd_self_declared",
            "us_pathway": "us_ivd_device_pathway",
        },
    ),
    (
        "laboratory developed test - CLIA, not an FDA device",
        profile(
            intended_purpose="Detects a gene variant to guide treatment selection.",
            product_description=(
                "A laboratory developed test run only within our own certified laboratory."
            ),
            examines_specimens="yes",
        ),
        {
            "product_family": "ivd",
            "us_pathway": "us_ldt_clia",
            "eu_classification": "eu_ivd_annexviii",
        },
    ),
    (
        "small molecule tablet - a medicinal product",
        profile(
            intended_purpose="Treats hypertension.",
            product_description="An oral small molecule tablet.",
            product_family="medicinal product",
        ),
        {
            "product_family": "medicinal_product",
            "eu_classification": "eu_medicinal_authorisation",
            "us_pathway": "us_drug_nda",
            "conformity_route": "eu_marketing_authorisation",
            "clinical_evidence": "medicinal_evidence",
            "change_triggers": "medicinal_change",
        },
    ),
    (
        "vaccine - a biological product",
        profile(
            intended_purpose="Prevents infection with a respiratory virus.",
            product_description="A recombinant protein vaccine.",
            product_family="vaccine",
        ),
        {
            "product_family": "biologic_vaccine",
            "us_pathway": "us_biologic_bla",
            "eu_classification": "eu_medicinal_authorisation",
        },
    ),
    (
        "prefilled syringe - an integral combination product",
        profile(
            intended_purpose="Treats rheumatoid arthritis.",
            product_description="A prefilled syringe delivering a biologic.",
            product_family="combination product",
        ),
        {
            "product_family": "combination_product",
            "eu_classification": "eu_combination_nbop",
            "us_pathway": "us_combination_rfd",
            "conformity_route": "eu_marketing_authorisation",
            "change_triggers": "medicinal_change",
        },
    ),
    (
        "Class IIb device CE-marked under the MDD",
        profile(
            intended_purpose="Delivers therapy through an implanted catheter.",
            product_description="An implanted infusion device.",
            invasiveness="surgically invasive, implanted",
            duration_of_use="long term",
            existing_certification="Class IIb, CE-marked under the MDD",
        ),
        {
            "legacy_transition": "mdd_legacy",
            "eu_classification": "eu_device_invasive_long_term",
            "conformity_route": "eu_notified_body",
        },
    ),
    (
        "IVD self-declared under the IVDD",
        profile(
            intended_purpose="Detects an infectious agent to support diagnosis.",
            product_description="A rapid antigen test cassette.",
            examines_specimens="yes",
            existing_certification="self-declared under the IVDD",
        ),
        {
            "legacy_transition": "ivdd_legacy",
            "product_family": "ivd",
        },
    ),
    (
        "device with an existing 510(k) clearance",
        profile(
            intended_purpose="Measures blood pressure to support diagnosis of hypertension.",
            product_description="An upper-arm cuff monitor.",
            invasiveness="non-invasive",
            duration_of_use="transient",
            existing_certification="510(k) cleared, K123456",
        ),
        {
            "us_pathway": "us_510k",
            "legacy_transition": "us_prior_clearance",
            "eu_classification": "eu_device_noninvasive",
        },
    ),
    (
        "humanitarian use device for a rare condition",
        profile(
            intended_purpose=(
                "Treats a rare disease affecting fewer than 8,000 patients in the US each year."
            ),
            product_description="An implanted shunt for a rare paediatric condition.",
            invasiveness="surgically invasive",
            duration_of_use="long term",
        ),
        {"us_pathway": "us_hde"},
    ),
    (
        "device whose product code is 510(k) exempt",
        profile(
            intended_purpose="Supports the diagnosis of a skin condition by magnifying the site.",
            product_description="A handheld illuminated magnifier.",
            invasiveness="non-invasive",
            duration_of_use="transient",
            lifecycle_stage="already marketed; the product code is exempt from 510(k)",
        ),
        {"us_pathway": "us_exempt"},
    ),
    (
        "device with no predicate on the market",
        profile(
            intended_purpose="Detects an early marker of disease at the point of care.",
            product_description=(
                "A handheld optical reader. No similar device is on the market today."
            ),
            invasiveness="non-invasive",
            duration_of_use="transient",
        ),
        {"us_pathway": "us_denovo"},
    ),
]


@pytest.mark.parametrize("name,product,expected", CASES, ids=[case[0] for case in CASES])
def test_branch_routing(name: str, product: ProductProfile, expected: dict[str, str]) -> None:
    determination = classify(product)
    assert determination.unresolved == [], f"{name}: unexpectedly unresolved"
    for tree_id, branch_id in expected.items():
        assert determination.branches.get(tree_id) == branch_id, tree_id


def test_every_branch_is_covered() -> None:
    """The CASES table must reach every branch the knowledge base declares."""
    declared = {
        (tree.id, branch.id) for tree in get_knowledge_base().trees for branch in tree.branches
    }
    covered = {
        (tree_id, branch_id) for _, _, expected in CASES for tree_id, branch_id in expected.items()
    }
    assert declared - covered == set(), "branches with no test case"


# --- the two divergences the brief calls out ---------------------------------------------


def test_rule_11_and_cures_act_3060_disagree_about_the_same_product() -> None:
    """Same clinical decision support tool: regulated in the EU, not a device in the US."""
    tool = profile(
        intended_purpose=(
            "Surfaces the relevant published guideline so a physician can independently review "
            "the basis for the treatment recommendation."
        ),
        product_description="Web tool for clinicians summarising published guidelines.",
        contains_software="yes",
        influences_clinical_decision="yes",
    )
    determination = classify(tool)

    assert determination.regulated is True
    assert "Class IIa" in determination.eu_pathway
    assert "Not a device" in determination.us_pathway
    assert {"EU-MD-CLASS-011", "US-SW-CDS-3060"} <= set(determination.node_ids)


def test_signal_analysis_defeats_the_cds_carve_out() -> None:
    """Criterion (i): analysing a signal makes it a device however transparent the rest is."""
    ppg = profile(
        intended_purpose="Flags possible atrial fibrillation for a physician to review.",
        product_description="Analyses the photoplethysmography signal from a wrist sensor.",
        contains_software="yes",
        influences_clinical_decision="yes",
    )
    assert classify(ppg).branches["us_pathway"] != "us_non_device_cds"


def test_ai_act_stacks_without_changing_the_device_class() -> None:
    """Article 6(1) adds obligations; it does not move the MDR class."""
    without_ai = profile(
        intended_purpose="Flags a possible lesion for a physician to review.",
        product_description="Analyses a dermoscopy image.",
        contains_software="yes",
        contains_ai="no",
        influences_clinical_decision="yes",
    )
    with_ai = without_ai.model_copy(update={"contains_ai": "yes"})

    plain = classify(without_ai)
    stacked = classify(with_ai)

    assert plain.branches["eu_classification"] == stacked.branches["eu_classification"]
    assert plain.eu_pathway == stacked.eu_pathway
    assert plain.branches["ai_act_stack"] == "no_ai"
    assert stacked.branches["ai_act_stack"] == "ai_high_risk"
    assert "EU-AI-HIGHRISK-006" in stacked.node_ids


def test_duration_of_use_changes_the_class_of_an_invasive_device() -> None:
    """Rules 5-8 escalate on duration. A slot we ask for has to change something."""
    invasive = {
        "intended_purpose": "Delivers therapy to treat a chronic condition.",
        "product_description": "A catheter-based delivery device.",
        "invasiveness": "surgically invasive",
    }
    bands = {
        "transient, under 60 minutes": "eu_device_invasive_transient",
        "short term, under 30 days": "eu_device_invasive",
        "long term, over 30 days": "eu_device_invasive_long_term",
    }
    for duration, expected in bands.items():
        determination = classify(profile(**invasive, duration_of_use=duration))
        assert determination.branches["eu_classification"] == expected, duration
        assert "Rules 5-" in determination.eu_pathway


def test_an_invasive_device_without_a_duration_is_unresolved() -> None:
    """Asking for duration and then ignoring it would be worse than not asking."""
    determination = classify(
        profile(
            intended_purpose="Delivers therapy to treat a chronic condition.",
            product_description="A catheter-based delivery device.",
            invasiveness="surgically invasive",
            duration_of_use="not sure yet",
        )
    )
    assert determination.branches.get("eu_classification") is None
    assert determination.unresolved == ["duration_of_use"]


def test_ordinary_product_prose_does_not_route_to_de_novo() -> None:
    """ "A novel optical technique" describes the technology, not the predicate landscape."""
    determination = classify(
        profile(
            intended_purpose="Detects a skin condition to support diagnosis.",
            product_description="A handheld reader using a novel optical technique.",
            invasiveness="non-invasive",
            duration_of_use="transient",
        )
    )
    assert determination.branches["us_pathway"] == "us_predicate_unknown"


def test_self_certified_class_i_ai_escapes_article_6() -> None:
    """Article 6(1) needs third-party conformity assessment, which Class I does not have."""
    determination = classify(
        profile(
            intended_purpose="Stores and transmits patient records to support treatment.",
            product_description="Integration middleware between two hospital systems.",
            contains_software="yes",
            contains_ai="yes",
            influences_clinical_decision="no",
        )
    )
    assert determination.branches["conformity_route"] == "eu_self_declared"
    assert determination.branches["ai_act_stack"] == "ai_not_high_risk"


# --- honest ambiguity ---------------------------------------------------------------------


def test_empty_profile_resolves_nothing() -> None:
    determination = classify(ProductProfile())
    assert determination.regulated is None
    assert determination.branches == {}
    assert "intended_purpose" in determination.unresolved


def test_walk_stops_at_the_first_unsettled_tree() -> None:
    """A claim with no product shape settles qualification and then stops."""
    determination = classify(
        ProductProfile(intended_purpose="Helps clinicians diagnose a skin condition.")
    )
    assert determination.regulated is True
    assert determination.branches == {"qualification": "medical_purpose"}
    assert "contains_software" in determination.unresolved


def test_unknown_clinical_decision_answer_stops_the_software_branch() -> None:
    """A shrug is not a branch. It becomes the intake agent's next question."""
    determination = classify(
        profile(
            intended_purpose="Helps clinicians assess a patient.",
            product_description="A web application.",
            contains_software="yes",
            influences_clinical_decision="not sure yet",
        )
    )
    assert determination.branches.get("eu_classification") is None
    assert "influences_clinical_decision" in determination.unresolved
    assert determination.complete is False


def test_unknown_ai_answer_stops_before_the_ai_act_stack() -> None:
    determination = classify(
        profile(
            intended_purpose="Flags a possible lesion for a physician to review.",
            product_description="Analyses a dermoscopy image.",
            contains_software="yes",
            contains_ai="we have not decided",
            influences_clinical_decision="yes",
        )
    )
    assert determination.branches.get("ai_act_stack") is None
    assert determination.unresolved == ["contains_ai"]


def test_missing_existing_certification_stops_at_the_transition_tree() -> None:
    determination = classify(
        profile(
            intended_purpose="Flags a possible lesion for a physician to review.",
            product_description="Analyses a dermoscopy image.",
            contains_software="yes",
            influences_clinical_decision="yes",
            existing_certification="",
        )
    )
    assert determination.branches.get("legacy_transition") is None
    assert "existing_certification" in determination.unresolved


# --- rendering ----------------------------------------------------------------------------


def test_render_names_both_jurisdictions_and_carries_staleness() -> None:
    determination = classify(CASES[1][1])
    rendered = render_determination(determination)

    assert "EU:" in rendered and "US:" in rendered
    assert "EU-MD-CLASS-011" in rendered
    # The AI Act node is in this determination, and its citation is flagged unverified.
    assert "CITATION UNVERIFIED" in rendered


def test_render_lists_unresolved_fields() -> None:
    rendered = render_determination(classify(ProductProfile()))
    assert "Unresolved" in rendered
    assert "intended_purpose" in rendered


def test_render_handles_an_empty_determination() -> None:
    assert "No determination yet" in render_determination(Determination())
