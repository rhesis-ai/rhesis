"""License tier catalog — the single source of truth for what each
:class:`~rhesis.backend.ee.licensing.entitlements.LicenseEdition` is entitled
to.

This is the one place to edit when adding a new paid tier or changing what an
existing tier includes. It is consumed by the license *minting* side (Unit 2)
to stamp the correct ``lic`` claim into a signed token.

Verification stays **token-authoritative**: the running server trusts the
signed token's explicit ``all_features`` / ``features`` rather than
re-deriving them from this catalog. That decoupling is what keeps the model
flexible — a tier's contents can change, or a one-off custom deal can be
issued to a single org, without redeploying the backend. This catalog simply
guarantees that the *standard* tiers are minted consistently.

Adding or changing a tier
-------------------------
1. Add a member to :class:`LicenseEdition` in ``entitlements.py``.
2. Add (or edit) one :class:`TierSpec` entry in :data:`EDITION_ENTITLEMENTS`.

Nothing else needs to change: ``feature_values`` and ``tier_to_lic_claim``
derive the wire payload, and ``FeatureName`` keeps feature identifiers in
sync with the registry so a typo'd feature is a static error, not a silent
runtime miss.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from rhesis.backend.app.features import FeatureName
from rhesis.backend.ee.licensing.entitlements import (
    LIC_ALL_FEATURES,
    LIC_EDITION,
    LIC_FEATURES,
    LIC_LIMITS,
    LIC_STATUS,
    LIMIT_SEATS,
    LicenseEdition,
    LicenseStatus,
)


@dataclass(frozen=True)
class TierSpec:
    """Declarative entitlement spec for one sellable tier.

    :param edition: the tier this spec describes.
    :param all_features: when ``True`` the tier unlocks every registered EE
        feature; ``features`` is then ignored (kept empty by convention).
    :param features: explicit set of :class:`FeatureName` members granted when
        ``all_features`` is ``False``. Using the enum (not raw strings) means a
        feature rename or typo is caught statically.
    :param limits: open-ended numeric/string limits (e.g. ``{"seats": 50}``).
    """

    edition: LicenseEdition
    all_features: bool = False
    features: frozenset[FeatureName] = frozenset()
    limits: Mapping[str, Any] = field(default_factory=dict)

    def feature_values(self) -> list[str]:
        """Return granted feature identifiers as sorted wire strings."""
        return sorted(f.value for f in self.features)


# ---------------------------------------------------------------------------
# THE CATALOG — edit here to add a tier or change what one includes.
# ---------------------------------------------------------------------------
EDITION_ENTITLEMENTS: dict[LicenseEdition, TierSpec] = {
    LicenseEdition.STARTER: TierSpec(
        edition=LicenseEdition.STARTER,
        features=frozenset({FeatureName.SSO}),
        limits={LIMIT_SEATS: 5},
    ),
    LicenseEdition.PREMIUM: TierSpec(
        edition=LicenseEdition.PREMIUM,
        features=frozenset({FeatureName.SSO, FeatureName.API_CLIENTS}),
        limits={LIMIT_SEATS: 50},
    ),
    LicenseEdition.ENTERPRISE: TierSpec(
        edition=LicenseEdition.ENTERPRISE,
        all_features=True,
    ),
    LicenseEdition.MASTER: TierSpec(
        edition=LicenseEdition.MASTER,
        all_features=True,
    ),
    LicenseEdition.TRIAL: TierSpec(
        edition=LicenseEdition.TRIAL,
        all_features=True,
        limits={LIMIT_SEATS: 10},
    ),
}


def is_sellable(edition: LicenseEdition) -> bool:
    """Return ``True`` if *edition* is a real, mintable tier."""
    return edition in EDITION_ENTITLEMENTS


def resolve_tier(edition: LicenseEdition) -> TierSpec:
    """Return the :class:`TierSpec` for *edition*.

    :raises KeyError: if *edition* is not a sellable tier (``community``,
        ``dev``, ``unknown``) — the mint side must never issue a non-tier
        license, so this fails loud rather than minting an empty entitlement.
    """
    return EDITION_ENTITLEMENTS[edition]


def tier_to_lic_claim(
    edition: LicenseEdition,
    status: LicenseStatus = LicenseStatus.ACTIVE,
) -> dict:
    """Build the ``lic`` claim payload for *edition* (for the minting side).

    The returned dict is JSON-ready (enum values rendered as strings) and
    matches the schema :func:`~rhesis.backend.ee.licensing.verify.verify_token`
    expects.
    """
    spec = resolve_tier(edition)
    return {
        LIC_EDITION: spec.edition.value,
        LIC_STATUS: status.value,
        LIC_ALL_FEATURES: spec.all_features,
        LIC_FEATURES: spec.feature_values(),
        LIC_LIMITS: dict(spec.limits),
    }


__all__ = [
    "EDITION_ENTITLEMENTS",
    "TierSpec",
    "is_sellable",
    "resolve_tier",
    "tier_to_lic_claim",
]
