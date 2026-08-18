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
from rhesis.backend.app.quota import (
    FREE_TIER_LIMITS,
    OveragePolicy,
    QuotaPolicy,
    QuotaResource,
    limits_to_wire,
)
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

# Editions the config is required to define. Derived from the enum rather
# than listed by hand so adding a member to LicenseEdition automatically
# extends what _assert_catalog_complete() demands of the YAML.
SELLABLE_EDITIONS = frozenset(LicenseEdition) - NON_SELLABLE_EDITIONS

# Every edition the catalog is allowed to contain: the sellable tiers plus
# COMMUNITY, which carries free-tier limits for unlicensed orgs but is never
# minted. UNKNOWN is excluded -- it is a decode-time sentinel, not a tier,
# and must never pick up limits from a config entry.
CATALOG_EDITIONS = SELLABLE_EDITIONS | {LicenseEdition.COMMUNITY}


def all_sellable() -> frozenset[LicenseEdition]:
    """Return every edition that can be minted a license token.

    Single source of truth for "what tiers exist" -- prefer this over
    hardcoding edition lists in callers and tests, so adding a tier does
    not require hunting down literal lists.
    """
    return SELLABLE_EDITIONS


def _parse_edition(edition_key: object) -> Optional[LicenseEdition]:
    """Strictly resolve a YAML edition key to a :class:`LicenseEdition`.

    ``LicenseEdition(value)`` cannot be used directly here: its
    :meth:`~LicenseEdition._missing_` coerces anything unrecognized to
    ``UNKNOWN`` instead of raising, which would silently bind a typo'd or
    not-yet-declared tier's limits onto the ``UNKNOWN`` sentinel -- and
    every org whose license carries an unrecognized edition resolves to
    ``UNKNOWN``. Match against real member values instead, so an unknown
    key is reported rather than absorbed.

    :returns: the matching member, or ``None`` if *edition_key* is not a
        declared edition (or is the ``UNKNOWN`` sentinel, which the config
        must never define).
    """
    if not isinstance(edition_key, str):
        return None
    for edition in CATALOG_EDITIONS:
        if edition.value == edition_key:
            return edition
    return None


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
    :param overage: whether reaching a limit blocks immediately or allows
        the grace band in :attr:`overage_tolerance_percent`.
    :param overage_tolerance_percent: for :attr:`OveragePolicy.SOFT`, how
        far past a limit this tier may run before it hard-blocks. Ignored
        (equivalent to ``0``) for :attr:`OveragePolicy.HARD`.
    """

    edition: LicenseEdition
    all_features: bool = False
    features: frozenset[FeatureName] = frozenset()
    limits: dict[QuotaResource, int | None] = field(default_factory=dict)
    retention_days: int = 14
    overage: OveragePolicy = OveragePolicy.HARD
    overage_tolerance_percent: int = 0

    def to_policy(self) -> QuotaPolicy:
        """Return the :class:`QuotaPolicy` this tier grants."""
        return QuotaPolicy(
            limits=dict(self.limits),
            overage=self.overage,
            overage_tolerance_percent=self.overage_tolerance_percent,
        )

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
    """Coerce and validate raw YAML limits into ``QuotaResource`` members.

    Both the key and the value are checked. ``yaml.safe_load`` happily
    returns strings, booleans and negative numbers, none of which are a
    meaningful quota: a string limit raises ``TypeError`` the first time
    enforcement compares ``used >= limit``, ``True`` silently means a limit
    of 1 (``bool`` is an ``int`` subclass), and a negative limit blocks every
    request. These flow straight into the JWT ``lic.limits`` claim and the
    ``/features`` response, so they are rejected here rather than surfacing
    far from their cause.

    :raises ValueError: on an unrecognized key, a value that is neither
        ``None`` (unlimited) nor a non-negative ``int``, or a ``limits``
        mapping that doesn't cover every :class:`QuotaResource`. Deliberately
        not caught by :func:`_load_tier_config`'s fallback -- a config that
        parses as YAML but is semantically wrong is a real bug that must
        surface at startup, not degrade into a silently-unmetered or
        permanently-blocked resource.
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

        # bool must be rejected explicitly: it passes isinstance(v, int).
        if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
            raise ValueError(
                f"Invalid limit for {key!r} in tier config: {value!r} "
                f"({type(value).__name__}). Expected an integer, or null for unlimited."
            )
        if value is not None and value < 0:
            raise ValueError(
                f"Invalid limit for {key!r} in tier config: {value!r}. "
                f"Limits must be non-negative (use null for unlimited)."
            )

        result[resource] = value

    # A resource this dict never mentions and a resource explicitly set to
    # `null` both end up absent from `result` -- and `QuotaPolicy.limits.get()`
    # reads either as unlimited. The unknown-key check above catches a typo
    # that adds a key; nothing caught the opposite typo, a key that's simply
    # missing -- most likely a new QuotaResource member added without every
    # tier config being updated for it, which would then silently unmeter it
    # everywhere rather than block, the same failure mode _parse_limits exists
    # to prevent for typo'd keys.
    missing = sorted(r.value for r in QuotaResource if r not in result)
    if missing:
        raise ValueError(
            f"Tier config `limits` is missing resource(s): {missing}. Every "
            f"QuotaResource member must have an explicit entry (use null for "
            f"unlimited) -- an absent resource is not 'inherits a default', "
            f"it reads as unlimited to every caller."
        )
    return result


def _parse_all_features(raw: object) -> bool:
    """Validate a raw YAML ``all_features`` value.

    :func:`~rhesis.backend.ee.licensing.verify.verify_token` reads the minted
    claim back with ``bool(lic.get(LIC_ALL_FEATURES, False))``, and Python's
    ``bool()`` treats any non-empty string as ``True`` -- including the
    string ``"false"``. An unvalidated ``all_features: "false"`` in the YAML
    would therefore mint a token that unlocks every registered EE feature,
    the opposite of what the config says. Reject anything that isn't a real
    bool here, at load time, rather than at verify time on every request.

    :raises ValueError: if *raw* is not a ``bool``.
    """
    if not isinstance(raw, bool):
        raise ValueError(
            f"Invalid all_features in tier config: {raw!r} ({type(raw).__name__}). "
            f"Expected true or false."
        )
    return raw


def _parse_overage(raw: object) -> OveragePolicy:
    """Coerce a raw YAML ``overage`` value to an :class:`OveragePolicy`.

    :raises ValueError: on anything other than ``"hard"`` or ``"soft"``.
    Deliberately not caught by :func:`_load_tier_config`'s fallback, for the
    same reason as :func:`_parse_limits`: an overage policy this backend
    doesn't recognize is a config bug, not a "no data yet" situation, and
    guessing a default here could turn a paid tier's intended grace period
    into an unannounced hard block, or vice versa.
    """
    try:
        return OveragePolicy(raw)
    except ValueError:
        raise ValueError(
            f"Invalid overage policy {raw!r} in tier config. "
            f"Valid values: {[p.value for p in OveragePolicy]}"
        )


def _parse_overage_tolerance(raw: object) -> int:
    """Validate a raw YAML ``overage_tolerance_percent`` value.

    Same shape as the limit-value checks in :func:`_parse_limits`: ``bool``
    is rejected explicitly because it passes ``isinstance(v, int)``, and a
    negative percent would make :meth:`QuotaPolicy.ceiling_for` return a
    ceiling *below* the limit, blocking a soft tier before it even reaches
    the number it was promised.

    :raises ValueError: if *raw* is not a non-negative ``int``.
    """
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise ValueError(
            f"Invalid overage_tolerance_percent in tier config: {raw!r} "
            f"({type(raw).__name__}). Expected a non-negative integer."
        )
    if raw < 0:
        raise ValueError(
            f"Invalid overage_tolerance_percent in tier config: {raw!r}. Must be non-negative."
        )
    return raw


class _FallbackCatalog(dict):
    """Marks a catalog as the intentional safety-net from :func:`_fallback_catalog`.

    A genuinely broken multi-tier config can also collapse to a bare
    ``{COMMUNITY: TierSpec(...)}`` -- e.g. every paid entry gets dropped by
    the per-entry shape checks in :func:`_load_tier_config` while community
    itself stays valid. That result is indistinguishable from the on-purpose
    fallback *by shape alone*, and :func:`_assert_catalog_complete` used to
    tell them apart by comparing key sets, which made the two cases look
    identical: a paying org silently gets free-tier limits and no error is
    raised, when the real bug is a malformed config for two other tiers.

    Subclassing ``dict`` rather than returning a separate boolean means the
    marker survives being passed through anything that treats the catalog as
    a plain mapping (which is everywhere else in this module), with no
    signature changes required.
    """


def _fallback_catalog() -> _FallbackCatalog:
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
    return _FallbackCatalog(
        {
            LicenseEdition.COMMUNITY: TierSpec(
                edition=LicenseEdition.COMMUNITY,
                limits=dict(FREE_TIER_LIMITS),
            )
        }
    )


def _load_tier_config() -> dict[LicenseEdition, TierSpec]:
    """Load tier specs from YAML, falling back to the bundled file."""
    config_path_str = os.environ.get(ENV_TIER_CONFIG)
    if config_path_str:
        config_path = Path(config_path_str)
        if not config_path.is_absolute():
            config_path = _BUNDLED_CONFIG.parent / config_path
    else:
        config_path = _BUNDLED_CONFIG

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
        edition = _parse_edition(edition_key)
        if edition is None:
            raise ValueError(
                f"Unknown edition {edition_key!r} in tier config at {config_path}. "
                f"Declare it in LicenseEdition first. "
                f"Valid keys: {sorted(e.value for e in CATALOG_EDITIONS)}"
            )

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
        overrides: dict[str, object] = {
            key: spec_raw[key] for key in ("retention_days",) if key in spec_raw
        }
        if "all_features" in spec_raw:
            overrides["all_features"] = _parse_all_features(spec_raw["all_features"])
        if "overage" in spec_raw:
            overrides["overage"] = _parse_overage(spec_raw["overage"])
        if "overage_tolerance_percent" in spec_raw:
            overrides["overage_tolerance_percent"] = _parse_overage_tolerance(
                spec_raw["overage_tolerance_percent"]
            )

        catalog[edition] = TierSpec(
            edition=edition,
            features=features,
            limits=limits,
            **overrides,
        )

    return catalog


def _assert_catalog_complete(catalog: dict[LicenseEdition, TierSpec]) -> None:
    """Fail loud if the enum and the tier config disagree.

    Adding a tier is a two-step change (declare it in
    :class:`LicenseEdition`, then define it in ``tier_config.yaml``). This
    gate makes it impossible to ship it half-done: a declared-but-undefined
    tier would otherwise fail late and cryptically with a ``KeyError`` the
    first time someone tried to mint it, and the reverse case is caught by
    :func:`_parse_edition`.

    Checks COMMUNITY as well as the sellable tiers. A malformed community
    entry is dropped by the shape checks in :func:`_load_tier_config`, and
    without it :func:`resolve_limits` returns an empty dict for every
    unlicensed org -- which reads downstream as *unlimited*. Requiring it
    here turns that fail-open into a startup failure.

    Skipped only for the genuine safety-net fallback -- see
    :class:`_FallbackCatalog`. Checking ``isinstance`` rather than comparing
    key sets matters: a real multi-tier config that lost every paid entry to
    :func:`_load_tier_config`'s per-entry shape checks also collapses to a
    bare ``{COMMUNITY: ...}``, and that case must still raise.

    :raises RuntimeError: naming exactly which editions are missing.
    """
    if isinstance(catalog, _FallbackCatalog):
        return

    missing = sorted(e.value for e in CATALOG_EDITIONS - set(catalog))
    if missing:
        raise RuntimeError(
            f"Tier config is missing an entry for declared edition(s): {missing}. "
            f"Every LicenseEdition member except "
            f"{sorted(e.value for e in NON_SELLABLE_EDITIONS - {LicenseEdition.COMMUNITY})} "
            f"must have a corresponding entry in tier_config.yaml "
            f"(community included -- it carries the free-tier limits)."
        )


# ---------------------------------------------------------------------------
# THE CATALOG — loaded from tier_config.yaml at import time.
# ---------------------------------------------------------------------------
EDITION_ENTITLEMENTS: dict[LicenseEdition, TierSpec] = _load_tier_config()
_assert_catalog_complete(EDITION_ENTITLEMENTS)


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


def resolve_policy(edition: Optional[LicenseEdition]) -> QuotaPolicy:
    """Return the full :class:`QuotaPolicy` for *edition*, falling back to
    community defaults.

    Used for quota lookups, not minting -- unlike :func:`resolve_tier`,
    this intentionally accepts ``None``/``community`` and any edition
    absent from the catalog, since every org (licensed or not) needs a
    resolvable policy.
    """
    spec = EDITION_ENTITLEMENTS.get(edition) if edition is not None else None
    if spec is None:
        spec = EDITION_ENTITLEMENTS.get(LicenseEdition.COMMUNITY)
    if spec is None:
        return QuotaPolicy()
    return spec.to_policy()


def resolve_limits(edition: Optional[LicenseEdition]) -> dict[QuotaResource, int | None]:
    """Return just the limits for *edition*. See :func:`resolve_policy`."""
    return resolve_policy(edition).limits


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
    "CATALOG_EDITIONS",
    "EDITION_ENTITLEMENTS",
    "NON_SELLABLE_EDITIONS",
    "SELLABLE_EDITIONS",
    "TierSpec",
    "all_sellable",
    "is_sellable",
    "resolve_limits",
    "resolve_policy",
    "resolve_tier",
    "tier_to_lic_claim",
]
