"""Deterministic qualification and classification, walked in Python rather than by a model.

This is the highest-value part of the domain, so no LLM touches it. Each tree in
``decision_trees.yaml`` supplies the branch catalogue, the prose and the terminal node ids; the
predicate that picks a branch lives here.

The walk stops at the first tree it cannot settle, naming the field that blocked it. That is the
point: an unresolved branch becomes a question the intake agent asks, not a guess the briefing
repeats.
"""

from __future__ import annotations

from typing import NamedTuple

from pydantic import BaseModel, Field

from reg_advisor.knowledge import KnowledgeBase, get_knowledge_base
from reg_advisor.state import ProductProfile
from reg_advisor.utils import as_text, as_tristate, bullet_list, matches_any

# --- keyword vocabularies ----------------------------------------------------------------
#
# A trailing "*" matches the rest of the word ("diagnos*" catches diagnose and diagnosis).
# Everything else matches on word boundaries — see `utils.matches_any` for why that matters.

# The verbs are the ones the definitions themselves use — MDR Art. 2(1) and FD&C Sec. 201(h) —
# rather than a list of conditions, which would never end.
_MEDICAL_PURPOSE = (
    "diagnos*",
    "detect*",
    "screen*",
    "monitor*",
    "treat*",
    "therap*",
    "prevent*",
    "predict*",
    "alleviate*",
    "cure*",
    "mitigat*",
    "compensat*",
    "prognos*",
    "triage",
    "risk of",
    "disease*",
    "disorder*",
    "injur*",
    "disabilit*",
    "patient*",
    "clinical*",
    "symptom*",
    "lesion*",
    "arrhythm*",
    "fibrillation",
    "tumour",
    "tumor",
    "sepsis",
    "stroke",
)
_WELLNESS = (
    "wellness",
    "well-being",
    "wellbeing",
    "fitness",
    "lifestyle",
    "general health",
    "not intended to diagnose",
    "no medical claim",
    "mindfulness",
    "sleep tracking",
)
# The standard wellness disclaimer spells out the very verbs that signal a medical purpose, so
# it comes out of the text before the medical scan runs. Otherwise every compliant wellness
# label reads as regulated.
_NEGATED_CLAIM = (
    "not intended to diagnose, treat, cure or prevent any disease",
    "not intended to diagnose, treat, cure, or prevent any disease",
    "not intended to diagnose or treat",
    "not intended to diagnose",
    "does not diagnose",
    "makes no medical claim",
    "no medical claim",
)

_MEDICINAL = ("medicin*", "drug*", "pharmaceutic*", "small molecule", "tablet*", "pharmacolog*")
_BIOLOGIC = ("vaccine*", "biologic*", "gene therapy", "cell therapy", "atmp*", "biosimilar*")
_COMBINATION = (
    "combination product",
    "drug-device",
    "drug device",
    "prefilled syringe",
    "pre-filled syringe",
    "pen injector",
    "autoinjector",
    "drug-eluting",
    "inhaler*",
)
_IVD = ("ivd", "in vitro", "assay*", "specimen*", "blood sample", "swab*", "biomarker panel")
_SOFTWARE = (
    "software",
    "app",
    "apps",
    "application*",
    "algorithm*",
    "samd",
    "saas",
    "platform",
    "cloud",
    "machine learning model",
    "web tool",
    "middleware",
)
_COMPANION_DX = ("companion diagnostic*", "companion dx", "cdx", "select patients for")

# Rule 11's escalation words, and the same words that sort a US device into Class III.
_SEVERITY_FATAL = ("death", "fatal", "life-threatening", "life threatening", "irreversible")
_SEVERITY_SERIOUS = (
    "serious deterioration",
    "serious harm",
    "surgical intervention",
    "surgery",
    "urgent*",
    "vital parameter*",
    "vital sign*",
    "intensive care",
    "hospitalis*",
    "hospitaliz*",
)

# Cures Act Sec. 520(o)(1)(E) criterion (i): software that acquires, processes or analyses a
# medical image, or a signal from an IVD or a signal acquisition system, is a device however
# transparent the rest of it is.
_SIGNAL_OR_IMAGE = (
    "ppg",
    "photoplethysmog*",
    "ecg",
    "ekg",
    "electrocardiog*",
    "signal*",
    "waveform*",
    "image*",
    "imaging",
    "x-ray",
    "xray",
    "radiograph*",
    "ct scan",
    "mri",
    "ultrasound",
    "histopatholog*",
    "sensor data",
    "raw data",
    "accelerometer*",
    "pulse oximet*",
    "dermoscopy",
    "dermatoscop*",
)
_PATIENT_FACING = (
    "patient*",
    "consumer*",
    "direct-to-consumer",
    "member of the public",
    "lay user*",
    "end user*",
    "self-test*",
    "the user",
)
_CLINICIAN_FACING = (
    "clinician*",
    "physician*",
    "doctor*",
    "healthcare professional*",
    "health care professional*",
    "hcp",
    "nurse*",
    "pharmacist*",
    "care team",
    "clinical team",
    "oncologist*",
    "radiologist*",
    "surgeon*",
    "specialist*",
    "consultant*",
)

_LDT = (
    "laboratory developed",
    "lab developed",
    "ldt",
    "single laboratory",
    "our own lab*",
    "own certified laboratory",
)
_NON_INVASIVE = (
    "non-invasive",
    "noninvasive",
    "not invasive",
    "no contact",
    "external only",
    "intact skin",
)
_INVASIVE = ("invasive", "implant*", "surgical*", "catheter*", "inserted", "in the body")
# MDR Annex VIII duration bands: transient under 60 minutes, short term under 30 days, long
# term over 30 days. Duration is the axis Rules 5-8 escalate on, so it has to be read.
_TRANSIENT = ("transient", "under 60 minutes", "less than an hour", "single procedure", "one-off")
_SHORT_TERM = ("short term", "short-term", "under 30 days", "less than 30 days", "a few days")
_LONG_TERM = (
    "long term",
    "long-term",
    "over 30 days",
    "more than 30 days",
    "permanent*",
    "implant*",
    "continuous*",
    "indefinite*",
)
_ORPHAN = ("humanitarian", "rare disease*", "orphan*", "fewer than 8,000", "8,000 individuals")
# "novel" is deliberately absent: it appears in ordinary product prose ("a novel optical
# technique") and would route any such description to De Novo. Only an explicit statement that
# no predicate exists counts.
_NO_PREDICATE = (
    "no predicate",
    "no legally marketed predicate",
    "without a predicate",
    "there is no predicate",
    "first of its kind",
    "no similar device",
    "no comparable device",
    "nothing comparable on the market",
    "nothing like it on the market",
)

# IVDR Annex VIII Class A: the only self-certified IVD category, and only when non-sterile.
_IVD_CLASS_A = (
    "class a",
    "general laboratory",
    "specimen receptacle",
    "washing solution",
    "buffer*",
    "instrument for general",
    "culture medium",
)
_STERILE = ("sterile", "sterilised", "sterilized")

_MDD_LEGACY = ("mdd", "93/42", "aimdd", "90/385", "medical device directive")
_IVDD_LEGACY = ("ivdd", "98/79", "in vitro diagnostic directive")
_US_PRIOR = ("510(k)", "510k", "pma", "de novo", "cleared", "k number", "approved by fda")
_NO_CERTIFICATE = (
    "none",
    "no",
    "not yet",
    "nothing",
    "n/a",
    "na",
    "new product",
    "pre-market",
    "never",
)


class Determination(BaseModel):
    """What the decision trees settled, and what they could not."""

    regulated: bool | None = None
    product_family: str | None = None
    eu_pathway: str | None = None
    us_pathway: str | None = None
    node_ids: list[str] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)
    rationale: list[str] = Field(default_factory=list)
    branches: dict[str, str] = Field(default_factory=dict)

    @property
    def complete(self) -> bool:
        """True when every tree settled and nothing is outstanding."""
        return not self.unresolved


class _Unsettled(NamedTuple):
    """The profile fields that would settle a tree the walk could not."""

    fields: tuple[str, ...]


_Branch = str | _Unsettled


# --- keyword matching ---------------------------------------------------------------------

_any = matches_any


def _text(*values: str | None) -> str:
    return " ".join(as_text(value) for value in values).lower()


def _purpose_text(profile: ProductProfile) -> str:
    return _text(profile.intended_purpose, profile.product_description)


def _claim_text(profile: ProductProfile) -> str:
    """The claim with any explicit disclaimer removed, for the medical-purpose scan."""
    haystack = _purpose_text(profile)
    for phrase in _NEGATED_CLAIM:
        haystack = haystack.replace(phrase, " ")
    return haystack


def _is_sterile(haystack: str) -> bool:
    """True for a sterile device. "non-sterile" contains "sterile", so it is removed first."""
    return _any(haystack.replace("non-sterile", " ").replace("nonsterile", " "), _STERILE)


def _severity(profile: ProductProfile) -> str:
    haystack = _purpose_text(profile)
    if _any(haystack, _SEVERITY_FATAL):
        return "fatal"
    if _any(haystack, _SEVERITY_SERIOUS):
        return "serious"
    return "ordinary"


def _invasiveness(profile: ProductProfile) -> str | None:
    haystack = _text(profile.invasiveness)
    if not haystack.strip():
        return None
    if _any(haystack, _NON_INVASIVE):
        return "non_invasive"
    if _any(haystack, _INVASIVE):
        return "invasive"
    return None


def _duration(profile: ProductProfile) -> str | None:
    """Which MDR duration band the device sits in, or ``None`` when it cannot be read."""
    haystack = _text(profile.duration_of_use, profile.invasiveness)
    if not haystack.strip():
        return None
    # Long term is checked first: "long-term implant" also contains a short-term-ish phrase in
    # some wordings, and the longer band always governs.
    if _any(haystack, _LONG_TERM):
        return "long_term"
    if _any(haystack, _TRANSIENT):
        return "transient"
    if _any(haystack, _SHORT_TERM):
        return "short_term"
    return None


# --- one function per tree ------------------------------------------------------------------


def _branch_qualification(profile: ProductProfile) -> _Branch:
    if not _purpose_text(profile).strip():
        return _Unsettled(("intended_purpose", "product_description"))
    if _any(_claim_text(profile), _MEDICAL_PURPOSE):
        return "medical_purpose"
    if as_tristate(profile.influences_clinical_decision) is True:
        return "medical_purpose"
    if _any(_purpose_text(profile), _WELLNESS):
        return "wellness_no_medical_purpose"
    return _Unsettled(("intended_purpose", "influences_clinical_decision"))


def _branch_product_family(profile: ProductProfile) -> _Branch:
    haystack = _text(profile.product_family, profile.product_description, profile.intended_purpose)
    # Order matters: a prefilled syringe mentions both a drug and a device, and the combination
    # test has to win before either single-family test sees it.
    if _any(haystack, _COMBINATION):
        return "combination_product"
    if _any(haystack, _BIOLOGIC):
        return "biologic_vaccine"
    if _any(haystack, _MEDICINAL):
        return "medicinal_product"
    if as_tristate(profile.examines_specimens) is True or _any(haystack, _IVD):
        return "ivd"
    if as_tristate(profile.contains_software) is True or _any(haystack, _SOFTWARE):
        return "software_medical_device"
    if as_tristate(profile.contains_software) is False:
        return "medical_device"
    return _Unsettled(("product_family", "contains_software", "examines_specimens"))


def _branch_eu_classification(profile: ProductProfile, family: str, qualified: str) -> _Branch:
    if qualified == "wellness_no_medical_purpose":
        return "eu_not_a_device"
    if family in {"medicinal_product", "biologic_vaccine"}:
        return "eu_medicinal_authorisation"
    if family == "combination_product":
        return "eu_combination_nbop"
    if family == "ivd":
        if _any(_purpose_text(profile), _COMPANION_DX):
            return "eu_ivd_companion_class_c"
        return "eu_ivd_annexviii"
    if family == "software_medical_device":
        informs = as_tristate(profile.influences_clinical_decision)
        if informs is None:
            return _Unsettled(("influences_clinical_decision",))
        if informs is False:
            # Outside Rule 11, so software falls back to the general active-device rules.
            return "eu_device_active"
        severity = _severity(profile)
        if severity == "fatal":
            return "eu_software_rule11_iii"
        if severity == "serious":
            return "eu_software_rule11_iib"
        return "eu_software_rule11_iia"
    invasiveness = _invasiveness(profile)
    if invasiveness == "non_invasive":
        return "eu_device_noninvasive"
    if invasiveness == "invasive":
        # Rules 5-8 escalate on duration, so an invasive device is not classified until the
        # band is known. Asking for it and then ignoring it would be worse than not asking.
        duration = _duration(profile)
        if duration is None:
            return _Unsettled(("duration_of_use",))
        if duration == "transient":
            return "eu_device_invasive_transient"
        if duration == "long_term":
            return "eu_device_invasive_long_term"
        return "eu_device_invasive"
    return _Unsettled(("invasiveness",))


def _non_device_cds(profile: ProductProfile) -> bool | None:
    """Does the software meet the Cures Act Sec. 3060 Non-Device CDS carve-out?

    Three of the four criteria are checkable here, and they are the three that most often fail.
    Criterion (i) excludes anything analysing a medical image or a signal. Criterion (iii)
    excludes support for time-critical decisions, which is why a claim whose failure mode is
    death cannot qualify however it is worded. Criterion (iv) needs a healthcare professional
    able to review the basis independently, so a patient-facing tool is out.
    """
    haystack = _purpose_text(profile)
    if _any(haystack, _SIGNAL_OR_IMAGE):
        return False
    if _severity(profile) == "fatal":
        return False
    clinician = _any(haystack, _CLINICIAN_FACING)
    patient = _any(haystack, _PATIENT_FACING)
    if patient and not clinician:
        return False
    if clinician:
        return True
    return None


def _branch_us_pathway(profile: ProductProfile, family: str, qualified: str) -> _Branch:
    if qualified == "wellness_no_medical_purpose":
        return "us_general_wellness"
    if family == "medicinal_product":
        return "us_drug_nda"
    if family == "biologic_vaccine":
        return "us_biologic_bla"
    if family == "combination_product":
        return "us_combination_rfd"

    haystack = _text(profile.intended_purpose, profile.product_description, profile.lifecycle_stage)
    if family == "ivd":
        if _any(haystack, _LDT):
            return "us_ldt_clia"
        if _any(haystack, _COMPANION_DX):
            return "us_companion_diagnostic"
        return "us_ivd_device_pathway"

    if family == "software_medical_device":
        informs = as_tristate(profile.influences_clinical_decision)
        if informs is None:
            return _Unsettled(("influences_clinical_decision",))
        # Software informing no clinical decision is outside the CDS question entirely; it
        # falls through to the ordinary device fork below.
        if informs is True:
            cds = _non_device_cds(profile)
            if cds is None:
                return _Unsettled(("product_description",))
            if cds:
                return "us_non_device_cds"

    if _any(haystack, _ORPHAN):
        return "us_hde"
    if _any(_text(profile.existing_certification, profile.lifecycle_stage), ("exempt*",)):
        return "us_exempt"
    if _severity(profile) == "fatal":
        return "us_pma"
    if _any(_text(profile.existing_certification), _US_PRIOR):
        return "us_510k"
    if _any(haystack, _NO_PREDICATE):
        return "us_denovo"
    # The 510(k) versus De Novo fork turns on whether a predicate exists, which no profile field
    # settles. Naming the fork beats picking a side.
    return "us_predicate_unknown"


def _branch_conformity_route(profile: ProductProfile, eu_class: str) -> str:
    if eu_class.startswith("eu_software_rule11") or eu_class.startswith("eu_device_invasive"):
        return "eu_notified_body"
    if eu_class in {"eu_device_noninvasive", "eu_device_active"}:
        return "eu_self_declared"
    if eu_class == "eu_ivd_annexviii":
        haystack = _text(profile.product_family, profile.product_description)
        if _any(haystack, _IVD_CLASS_A) and not _is_sterile(haystack):
            return "eu_ivd_self_declared"
        return "eu_ivd_notified_body"
    if eu_class == "eu_ivd_companion_class_c":
        return "eu_ivd_notified_body"
    if eu_class in {"eu_medicinal_authorisation", "eu_combination_nbop"}:
        return "eu_marketing_authorisation"
    return "eu_no_conformity_route"


def _branch_ai_act_stack(profile: ProductProfile, conformity: str) -> _Branch:
    contains_ai = as_tristate(profile.contains_ai)
    if contains_ai is None:
        return _Unsettled(("contains_ai",))
    if contains_ai is False:
        return "no_ai"
    if conformity in {"eu_notified_body", "eu_ivd_notified_body"}:
        return "ai_high_risk"
    return "ai_not_high_risk"


def _branch_clinical_evidence(family: str, qualified: str) -> str:
    if qualified == "wellness_no_medical_purpose":
        return "no_clinical_evidence_regime"
    if family == "ivd":
        return "ivd_evidence"
    if family in {"medicinal_product", "biologic_vaccine", "combination_product"}:
        return "medicinal_evidence"
    return "device_evidence"


def _branch_change_triggers(profile: ProductProfile, family: str) -> str:
    # An integral combination marketed as a medicine follows the variations framework, not the
    # device change rules, so it sits with the medicines here.
    if family in {"medicinal_product", "biologic_vaccine", "combination_product"}:
        return "medicinal_change"
    if as_tristate(profile.contains_ai) is True:
        return "ai_enabled_change"
    return "device_change"


def _branch_legacy_transition(profile: ProductProfile) -> _Branch:
    haystack = _text(profile.existing_certification)
    if _any(haystack, _MDD_LEGACY):
        return "mdd_legacy"
    if _any(haystack, _IVDD_LEGACY):
        return "ivdd_legacy"
    if _any(haystack, _US_PRIOR):
        return "us_prior_clearance"
    if _any(haystack, _NO_CERTIFICATE):
        return "no_existing_certification"
    return _Unsettled(("existing_certification",))


# --- the walk -----------------------------------------------------------------------------


def classify(profile: ProductProfile, *, base: KnowledgeBase | None = None) -> Determination:
    """Walk the decision trees and return what they settled.

    Stops at the first tree the profile cannot settle, naming the fields that would settle it.
    The intake agent asks about those, so the next question is the one that actually moves the
    classification forward rather than the next slot in declaration order.
    """
    knowledge = base or get_knowledge_base()
    result = Determination()

    def record(tree_id: str, branch_id: str) -> None:
        tree = knowledge.tree(tree_id)
        branch = tree.branch(branch_id) if tree else None
        if tree is None or branch is None:  # pragma: no cover - validation catches this at boot
            raise KeyError(f"unknown decision-tree branch: {tree_id}/{branch_id}")
        result.branches[tree_id] = branch_id
        result.rationale.append(f"{tree.name} -> {branch.summary}")
        for node_id in branch.nodes:
            if node_id not in result.node_ids:
                result.node_ids.append(node_id)
        if branch.eu_pathway:
            result.eu_pathway = branch.eu_pathway
        if branch.us_pathway:
            result.us_pathway = branch.us_pathway

    def settle(tree_id: str, outcome: _Branch) -> str | None:
        if isinstance(outcome, _Unsettled):
            result.unresolved = list(outcome.fields)
            return None
        record(tree_id, outcome)
        return outcome

    qualified = settle("qualification", _branch_qualification(profile))
    if qualified is None:
        return result
    result.regulated = qualified == "medical_purpose"

    if not result.regulated:
        # Nothing left to classify, but the EU/US contrast still has to be stated.
        record("eu_classification", "eu_not_a_device")
        record("us_pathway", "us_general_wellness")
        record("conformity_route", "eu_no_conformity_route")
        record("clinical_evidence", "no_clinical_evidence_regime")
        result.product_family = "wellness_products"
        return result

    family = settle("product_family", _branch_product_family(profile))
    if family is None:
        return result
    result.product_family = family

    eu_class = settle("eu_classification", _branch_eu_classification(profile, family, qualified))
    if eu_class is None:
        return result

    if settle("us_pathway", _branch_us_pathway(profile, family, qualified)) is None:
        return result

    conformity = _branch_conformity_route(profile, eu_class)
    record("conformity_route", conformity)

    if settle("ai_act_stack", _branch_ai_act_stack(profile, conformity)) is None:
        return result

    record("clinical_evidence", _branch_clinical_evidence(family, qualified))
    record("change_triggers", _branch_change_triggers(profile, family))

    settle("legacy_transition", _branch_legacy_transition(profile))
    return result


def render_determination(
    determination: Determination,
    *,
    base: KnowledgeBase | None = None,
) -> str:
    """Render a determination as text, with its staleness warnings attached."""
    knowledge = base or get_knowledge_base()
    if determination.regulated is None:
        lines = ["No determination yet — the profile does not settle qualification."]
    else:
        lines = [
            "Regulated as a health product: " + ("yes" if determination.regulated else "no"),
            f"Product family: {determination.product_family or 'not settled'}",
            f"EU: {determination.eu_pathway or 'not settled'}",
            f"US: {determination.us_pathway or 'not settled'}",
        ]

    lines += ["", "How the trees routed:", bullet_list(determination.rationale)]
    lines += ["", "Knowledge base nodes:", bullet_list(determination.node_ids)]

    if determination.unresolved:
        lines += [
            "",
            "Unresolved — these fields would settle the rest:",
            bullet_list(determination.unresolved),
        ]

    warnings = knowledge.staleness_warnings(determination.node_ids)
    if warnings:
        lines += [
            "",
            "Staleness warnings that must travel with these nodes:",
            bullet_list(warnings),
        ]
    return "\n".join(lines)


__all__ = ["Determination", "classify", "render_determination"]
