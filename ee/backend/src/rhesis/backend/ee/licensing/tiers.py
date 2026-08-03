"""License tier catalog loaded from YAML config.

The YAML file (``tier_config.yaml``, bundled alongside this module) is
the single source of truth for what each
:class:`~rhesis.backend.ee.licensing.entitlements.LicenseEdition` is
entitled to.  It is consumed by the license *minting* side to stamp
the correct ``lic`` claim into a signed token and by the
:class:`~rhesis.backend.ee.licensing.quota_provider.ConfigQuotaProvider`
to resolve usage limits at runtime.

Override the bundled config at runtime by setting the
``RHESIS_TIER_CONFIG`` env var to a path (e.g. a K8s ConfigMap mount).

Verification stays **token-authoritative**: the running server trusts
the signed token's explicit ``all_features`` / ``features`` rather
than re-deriving them from this catalog.

Adding or changing a tier
-------------------------
1. Add a member to :class:`LicenseEdition` in ``entitlements.py``.
2. Add (or edit) an entry in ``tier_config.yaml``.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from rhesis.backend.app.features import FeatureName
from rhesis.backend.app.quota import FREE_TIER_LIMITS, QuotaResource, limits_to_wire
from rhesis.backend.ee.licensing.entitlements import (
    ENV_TIER_CONFIG,
    LIC_ALL_FEATURES,
    LIC_EDITION,
    LIC_FEATURES,
    LIC_LIMITS,
    LIC_STATUS,
    LicenseEdition,
    LicenseStatus,
)

logger = logging.getLogger(__name__)

_BUNDLED_CONFIG = Path(__file__).parent / "tier_config.yaml"

# Editions that are never a real, mintable tier -- absent by design from
# "is this sellable" checks even though COMMUNITY has a limits entry in the
# catalog (unlicensed orgs still need a limits lookup; they just can't be
# minted a token for it).
NON_SELLABLE_EDITIONS = frozenset({LicenseEdition.COMMUNITY, LicenseEdition.UNKNOWN})


@dataclass(frozen=True)
class TierSpec:
    """Declarative entitlement spec for one tier.

    :param edition: the tier this spec describes.
    :param all_features: when ``True`` the tier unlocks every registered
        EE feature; ``features`` is then ignored.
    :param features: explicit set of :class:`FeatureName` members
        granted when ``all_features`` is ``False``.
    :param limits: metered resource limits keyed by
        :class:`QuotaResource`.  ``None`` values mean unlimited.
    :param retention_days: data retention in days for this tier.
    :param overage: ``"hard"`` (block) or ``"soft"`` (warn + allow).
    """

    edition: LicenseEdition
    all_features: bool = False
    features: frozenset[FeatureName] = frozenset()
    limits: dict[QuotaResource, int | None] = field(default_factory=dict)
    retention_days: int = 14
    overage: str = "hard"

    def feature_values(self) -> list[str]:
        """Return granted feature identifiers as sorted wire strings."""
        return sorted(f.value for f in self.features)


def _parse_features(raw: list[str]) -> frozenset[FeatureName]:
    """Coerce raw YAML feature strings to ``FeatureName`` members.

    Unknown names are skipped with a warning rather than raising, unlike
    :func:`_parse_limits`. Features are additive and forward-compatible --
    a config authored for a newer backend can reference a feature this
    version doesn't know about yet, and skipping it is harmless. Limits are
    safety-critical: a typo'd key would silently leave a resource unmetered,
    so that case fails fast instead.
    """
    result = set()
    for name in raw:
        try:
            result.add(FeatureName(name))
        except ValueError:
            logger.warning("Unknown feature %r in tier config, skipping", name)
    return frozenset(result)


def _parse_limits(raw: dict[str, int | None]) -> dict[QuotaResource, int | None]:
    """Coerce raw YAML limit keys to ``QuotaResource`` members.

    :raises ValueError: on an unrecognized key. Deliberately not caught by
        :func:`_load_tier_config`'s fallback -- a config that parses as YAML
        but names a resource that doesn't exist is a real bug that must
        surface at startup, not degrade into a silently-unmetered resource.
    """
    result: dict[QuotaResource, int | None] = {}
    for key, value in raw.items():
        try:
            resource = QuotaResource(key)
        except ValueError:
            raise ValueError(
                f"Unknown limit key {key!r} in tier config. "
                f"Valid keys: {[r.value for r in QuotaResource]}"
            )
        result[resource] = value
    return result


def _fallback_catalog() -> dict[LicenseEdition, TierSpec]:
    """Safety-net catalog used when the tier config can't be read at all.

    Only the community entry is populated, using the same numbers as
    :data:`~rhesis.backend.app.quota.FREE_TIER_LIMITS`. This keeps free-tier
    orgs metered (rather than silently unlimited) if the bundled YAML is
    missing or an operator's ``RHESIS_TIER_CONFIG`` override is broken.
    Paid editions are intentionally absent: :func:`resolve_limits` falls
    back to this same community entry for any edition not in the catalog,
    and :func:`is_sellable` correctly reports paid tiers as unsellable until
    the config is fixed, rather than minting tokens against stale defaults.
    """
    return {
        LicenseEdition.COMMUNITY: TierSpec(
            edition=LicenseEdition.COMMUNITY,
            limits=dict(FREE_TIER_LIMITS),
        )
    }


def _load_tier_config() -> dict[LicenseEdition, TierSpec]:
    """Load tier specs from YAML, falling back to the bundled file."""
    config_path_str = os.environ.get(ENV_TIER_CONFIG)
    config_path = Path(config_path_str) if config_path_str else _BUNDLED_CONFIG

    try:
        raw = yaml.safe_load(config_path.read_text())
    except Exception:
        logger.exception(
            "Failed to load tier config from %s, falling back to free-tier defaults",
            config_path,
        )
        return _fallback_catalog()

    if not isinstance(raw, dict):
        logger.error(
            "Tier config at %s is not a YAML mapping, falling back to free-tier defaults",
            config_path,
        )
        return _fallback_catalog()

    catalog: dict[LicenseEdition, TierSpec] = {}
    for edition_key, spec_raw in raw.items():
        try:
            edition = LicenseEdition(edition_key)
        except ValueError:
            logger.warning("Unknown edition %r in tier config, skipping", edition_key)
            continue

        if not isinstance(spec_raw, dict):
            logger.warning(
                "Tier config entry %r is not a mapping (got %s), skipping",
                edition_key,
                type(spec_raw).__name__,
            )
            continue

        raw_limits = spec_raw.get("limits", {})
        if not isinstance(raw_limits, dict):
            logger.warning(
                "Tier config entry %r has a non-mapping `limits` (got %s), skipping",
                edition_key,
                type(raw_limits).__name__,
            )
            continue

        raw_features = spec_raw.get("features", [])
        if not isinstance(raw_features, list):
            # A string would otherwise iterate per-character in _parse_features
            # and silently resolve to an empty feature set instead of failing.
            logger.warning(
                "Tier config entry %r has a non-list `features` (got %s), skipping",
                edition_key,
                type(raw_features).__name__,
            )
            continue

        limits = _parse_limits(raw_limits)
        features = _parse_features(raw_features)

        # Only pass fields the YAML actually sets; TierSpec's own dataclass
        # defaults apply for the rest. Hardcoding e.g. `retention_days=14`
        # here would duplicate TierSpec's default and silently drift from
        # it if that default ever changes.
        overrides = {
            key: spec_raw[key]
            for key in ("all_features", "retention_days", "overage")
            if key in spec_raw
        }
        catalog[edition] = TierSpec(
            edition=edition,
            features=features,
            limits=limits,
            **overrides,
        )

    return catalog


# ---------------------------------------------------------------------------
# THE CATALOG — loaded from tier_config.yaml at import time.
# ---------------------------------------------------------------------------
EDITION_ENTITLEMENTS: dict[LicenseEdition, TierSpec] = _load_tier_config()


def is_sellable(edition: LicenseEdition) -> bool:
    """Return ``True`` if *edition* is a real, mintable tier.

    ``COMMUNITY`` has a catalog entry (for limits lookups) but is never
    sellable -- see :data:`NON_SELLABLE_EDITIONS`.
    """
    return edition in EDITION_ENTITLEMENTS and edition not in NON_SELLABLE_EDITIONS


def resolve_tier(edition: LicenseEdition) -> TierSpec:
    """Return the :class:`TierSpec` for *edition*.

    :raises KeyError: if *edition* is not a sellable tier (including
        ``community``, which has limits but must never be minted).
    """
    if edition in NON_SELLABLE_EDITIONS:
        raise KeyError(edition)
    return EDITION_ENTITLEMENTS[edition]


def resolve_limits(edition: Optional[LicenseEdition]) -> dict[QuotaResource, int | None]:
    """Return limits for *edition*, falling back to community defaults.

    Used for quota lookups, not minting -- unlike :func:`resolve_tier`,
    this intentionally accepts ``None``/``community`` and any edition
    absent from the catalog, since every org (licensed or not) needs a
    resolvable limits dict.
    """
    spec = EDITION_ENTITLEMENTS.get(edition) if edition is not None else None
    if spec is None:
        spec = EDITION_ENTITLEMENTS.get(LicenseEdition.COMMUNITY)
    if spec is None:
        return {}
    return dict(spec.limits)


def tier_to_lic_claim(
    edition: LicenseEdition,
    status: LicenseStatus = LicenseStatus.ACTIVE,
) -> dict:
    """Build the ``lic`` claim payload for *edition* (for the minting side).

    The returned dict is JSON-ready (enum values rendered as strings)
    and matches the schema
    :func:`~rhesis.backend.ee.licensing.verify.verify_token` expects.
    """
    spec = resolve_tier(edition)
    return {
        LIC_EDITION: spec.edition.value,
        LIC_STATUS: status.value,
        LIC_ALL_FEATURES: spec.all_features,
        LIC_FEATURES: spec.feature_values(),
        LIC_LIMITS: limits_to_wire(spec.limits),
    }


__all__ = [
    "EDITION_ENTITLEMENTS",
    "NON_SELLABLE_EDITIONS",
    "TierSpec",
    "is_sellable",
    "resolve_limits",
    "resolve_tier",
    "tier_to_lic_claim",
]
