"""Shared state for the Reg-Advisor agent."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from reg_advisor.utils import as_slot_text, as_text, as_tristate, bullet_list, matches_any

# Slots that are core for every product, whatever it turns out to be.
ALWAYS_CORE: tuple[str, ...] = (
    "intended_purpose",
    "product_description",
    "target_markets",
    "contains_software",
    "contains_ai",
    "existing_certification",
)

# Slots that are core only in some shapes of product. `missing_core_profile_slots` decides.
CONDITIONALLY_CORE: tuple[str, ...] = (
    "influences_clinical_decision",
    "examines_specimens",
    "invasiveness",
    "duration_of_use",
)

PROFILE_FIELDS: tuple[str, ...] = (
    "intended_purpose",
    "product_description",
    "target_markets",
    "product_family",
    "contains_software",
    "contains_ai",
    "examines_specimens",
    "influences_clinical_decision",
    "invasiveness",
    "duration_of_use",
    "lifecycle_stage",
    "existing_certification",
)

# Families where a "does it examine specimens" answer still changes the routing. Once the
# family is settled as something else, the question is noise.
_IVD_PLAUSIBLE = ("ivd", "in vitro", "diagnostic*", "assay*", "test*", "specimen*", "sample*")

_SOFTWARE_HINTS = ("software", "app", "apps", "saas", "algorithm*", "samd", "cloud", "platform")
# Any hint of something physical, used only to decide whether to ask about invasiveness and
# duration. Deliberately broad: over-asking costs the user one question. "device" is absent
# because "software as a medical device" is still software only.
_HARDWARE_HINTS = (
    "hardware",
    "firmware",
    "wearable*",
    "sensor*",
    "instrument*",
    "probe*",
    "cartridge*",
    "patch",
    "cuff",
    "enclosure",
    "housing",
    "electrode*",
    "accessory",
    "physical component*",
    "pump*",
    "catheter*",
    "needle*",
    "syringe*",
    "stent*",
    "valve*",
    "tubing",
    "dressing*",
    "pacing lead*",
    "handheld",
    "implanted",
    "implantable",
)

# Hardware the manufacturer clearly supplies, used to decide the product family. Narrower than
# the list above on purpose: over-asking a question is cheap, but routing an implantable down
# the software path gives it the wrong class. "sensor", "wearable" and "patch" are absent
# because software routinely reads *from* those without shipping them.
_SUPPLIED_HARDWARE = (
    "hardware",
    "firmware",
    "implanted",
    "implantable",
    "pump*",
    "catheter*",
    "needle*",
    "syringe*",
    "stent*",
    "valve*",
    "tubing",
    "dressing*",
    "pacing lead*",
    "electrode*",
    "cartridge*",
    "probe*",
    "instrument*",
    "cuff",
    "enclosure",
    "housing",
    "handheld",
)

_LABELS: dict[str, str] = {
    "intended_purpose": "Intended purpose / claim",
    "product_description": "What the product does",
    "target_markets": "Target markets",
    "product_family": "Product family",
    "contains_software": "Contains software",
    "contains_ai": "Contains AI or machine learning",
    "examines_specimens": "Examines specimens from the body",
    "influences_clinical_decision": "Informs a clinical decision",
    "invasiveness": "Invasiveness",
    "duration_of_use": "Duration of use",
    "lifecycle_stage": "Where the product is today",
    "existing_certification": "Existing certification",
}


class Phase(str, Enum):
    """Where the conversation has got to. ``str`` mixin so it serialises as its value."""

    IDLE = "idle"
    SCOPING = "scoping"
    CLASSIFIED = "classified"
    BRIEFED = "briefed"
    REFERRED = "referred"


class ProductProfile(BaseModel):
    """What the user has told us about their product."""

    # The claim, verbatim. Both systems hang qualification off the manufacturer's own words, so
    # this is the single most load-bearing field in the whole profile.
    intended_purpose: str | None = None
    product_description: str | None = None
    target_markets: str | None = None
    product_family: str | None = None
    contains_software: str | None = None
    contains_ai: str | None = None
    examines_specimens: str | None = None
    influences_clinical_decision: str | None = None
    invasiveness: str | None = None
    duration_of_use: str | None = None
    lifecycle_stage: str | None = None
    existing_certification: str | None = None


class RegAdvisorState(BaseModel):
    """Cross-turn conversation state, owned by this package rather than by ADK."""

    turn: int = 0
    phase: Phase = Phase.IDLE
    profile: ProductProfile = Field(default_factory=ProductProfile)
    history: list[dict[str, str]] = Field(default_factory=list)
    scope_flag: bool = False
    determinations: list[str] = Field(default_factory=list)


def _is_blank(value: str | None) -> bool:
    """True when a slot is unset or only whitespace, i.e. not real content."""
    return not as_text(value).strip()


def _described(profile: ProductProfile) -> str:
    return f"{as_text(profile.product_description)} {as_text(profile.product_family)}"


def is_software_only(profile: ProductProfile) -> bool:
    """True when nothing about this product suggests physical hardware.

    Used to decide whether invasiveness and duration are worth asking about, so it errs toward
    "physical": one extra question is cheaper than a missing answer.
    """
    if as_tristate(profile.contains_software) is False:
        return False
    # "an app paired with a wearable sensor" is not software only, so hardware words win.
    if matches_any(_described(profile), _HARDWARE_HINTS):
        return False
    if as_tristate(profile.contains_software) is True:
        return True
    return matches_any(as_text(profile.product_family), _SOFTWARE_HINTS)


def supplies_own_hardware(profile: ProductProfile) -> bool:
    """True when the manufacturer appears to ship hardware, not just read from someone else's.

    This decides the product family, so it uses the narrower vocabulary. Software that analyses
    a signal "from a wrist sensor" is still software; an infusion pump with firmware is not.
    Genuinely ambiguous wording — "our sensor" versus "a sensor" — is beyond keyword matching,
    and lands on the software side by default.
    """
    return matches_any(_described(profile), _SUPPLIED_HARDWARE)


def _ivd_still_plausible(profile: ProductProfile) -> bool:
    family = as_text(profile.product_family)
    if not family.strip():
        return True
    return matches_any(family, _IVD_PLAUSIBLE)


def missing_core_profile_slots(state: RegAdvisorState) -> list[str]:
    """Core slots still unfilled, in ask order.

    Which slots count as core is conditional, because asking every question of every product
    wastes the user's time and produces worse answers. Specimen handling only matters while the
    product could still be an IVD; invasiveness and duration of use only matter for something
    physical.
    """
    profile = state.profile
    missing = [name for name in ALWAYS_CORE if _is_blank(getattr(profile, name))]

    software_only = is_software_only(profile)
    physical = not software_only

    conditional_applies = {
        # Rule 11 and the US CDS carve-out both turn on this, so it is core wherever software is.
        "influences_clinical_decision": as_tristate(profile.contains_software) is not False,
        "examines_specimens": _ivd_still_plausible(profile),
        "invasiveness": physical,
        "duration_of_use": physical,
    }
    missing.extend(
        name
        for name in CONDITIONALLY_CORE
        if conditional_applies[name] and _is_blank(getattr(profile, name))
    )
    return missing


def apply_profile_updates(state: RegAdvisorState, updates: dict[str, Any]) -> RegAdvisorState:
    """Merge slot updates, ignoring blanks so a model cannot erase a filled slot."""
    updated = state.model_copy(deep=True)
    for name, value in updates.items():
        if name not in PROFILE_FIELDS:
            continue
        text = as_slot_text(value)
        if text:
            setattr(updated.profile, name, text)
    return updated


def describe_profile(state: RegAdvisorState) -> str:
    """Render what is known, what is missing, and what has been determined so far.

    This is the picture injected into the coordinator's and the intake agent's prompts. It is
    rendered here rather than templated from state so it stays deterministic and testable, and
    so the taxonomy never has to be dumped into a prompt.
    """
    filled = [
        f"{_LABELS[name]}: {as_text(getattr(state.profile, name)).strip()}"
        for name in PROFILE_FIELDS
        if not _is_blank(getattr(state.profile, name))
    ]
    lines = ["Known so far:", bullet_list(filled) if filled else "- nothing yet."]

    missing = missing_core_profile_slots(state)
    if missing:
        lines.append("Still missing: " + ", ".join(_LABELS[name] for name in missing) + ".")
    else:
        lines.append("Every core slot is filled — the profile is complete enough to classify.")

    if state.determinations:
        lines.append("Nodes already surfaced: " + ", ".join(state.determinations) + ".")
    if state.scope_flag:
        lines.append("A scope flag has been raised in this conversation; the user was referred.")
    return "\n".join(lines)


def profile_from_state(payload: object) -> ProductProfile:
    """Rebuild a profile from a raw framework state payload, tolerating anything else."""
    if not isinstance(payload, dict):
        return ProductProfile()
    known = {name: payload.get(name) for name in PROFILE_FIELDS if payload.get(name) is not None}
    return ProductProfile.model_validate(known)


def state_from_payload(payload: dict[str, Any]) -> RegAdvisorState:
    """Rebuild the domain state from an ADK session-state dict.

    History entries are coerced rather than validated. Pydantic checks a model on construction
    but not on assignment, so a non-string can be assigned into ``history`` and then reach us
    one turn later — where a strict rebuild would fail the whole turn over stale data.
    """
    history = [
        {"role": as_text(item.get("role")) or "user", "content": as_text(item.get("content"))}
        for item in (payload.get("history") or [])
        if isinstance(item, dict)
    ]
    return RegAdvisorState(
        turn=int(payload.get("turn") or 0),
        phase=Phase(payload.get("phase") or Phase.IDLE),
        profile=profile_from_state(payload.get("profile")),
        history=history,
        scope_flag=bool(payload.get("scope_flag")),
        determinations=[as_text(item) for item in (payload.get("determinations") or [])],
    )


__all__ = [
    "ALWAYS_CORE",
    "CONDITIONALLY_CORE",
    "PROFILE_FIELDS",
    "Phase",
    "ProductProfile",
    "RegAdvisorState",
    "apply_profile_updates",
    "describe_profile",
    "is_software_only",
    "supplies_own_hardware",
    "missing_core_profile_slots",
    "profile_from_state",
    "state_from_payload",
]
