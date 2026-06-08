"""License entitlements extracted from a validated JWT.

:class:`Entitlements` is a frozen dataclass populated by
:mod:`~rhesis.backend.ee.licensing.verify`. It carries the decoded license
payload and exposes :meth:`is_expired` for live expiry checks outside the
JWT verification cache.

This module is also the single source of truth for the licensing domain
vocabulary — editions, billing statuses, JWT claim keys, the signing
algorithm, and the environment-variable names — so verify/provider/keys (and
the future mint helper) never hard-code the same string twice.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional


class LicenseEdition(str, Enum):
    """License tier reported to the UI/diagnostics.

    Inherits from ``str`` so members compare equal to and serialize as their
    raw value (``LicenseEdition.ENTERPRISE == "enterprise"``). Unknown values
    decoded from a token coerce to :attr:`UNKNOWN` via :meth:`_missing_`
    rather than raising, keeping verification fail-soft on cosmetic fields.

    Adding a sellable tier is a two-step change: add a member here, then add
    its entitlement spec to
    :data:`~rhesis.backend.ee.licensing.tiers.EDITION_ENTITLEMENTS`.
    ``COMMUNITY``, ``DEV`` and ``UNKNOWN`` are non-sellable sentinels and are
    intentionally absent from that catalog.
    """

    COMMUNITY = "community"
    DEV = "dev"
    # --- Sellable tiers (see tiers.EDITION_ENTITLEMENTS) ---
    STARTER = "starter"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"
    MASTER = "master"
    TRIAL = "trial"
    UNKNOWN = "unknown"

    @classmethod
    def _missing_(cls, value: object) -> "LicenseEdition":
        return cls.UNKNOWN


class LicenseStatus(str, Enum):
    """Billing status of a license.

    Unknown statuses coerce to :attr:`UNKNOWN` (which is *not* in
    :data:`ACTIVE_STATUSES`), so an unrecognized status fails closed.
    """

    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    UNKNOWN = "unknown"

    @classmethod
    def _missing_(cls, value: object) -> "LicenseStatus":
        return cls.UNKNOWN


# Billing statuses that still grant feature access. ``past_due`` is included
# so a temporary payment hiccup does not immediately lock an org out; only an
# explicit ``canceled`` (or any unknown status) revokes access. Single source
# of truth consumed by :meth:`Entitlements.is_active`.
ACTIVE_STATUSES = frozenset({LicenseStatus.ACTIVE, LicenseStatus.PAST_DUE})

# --- JWT signing / claim constants -----------------------------------------
# Shared by verify.py (decoder) and any future mint helper so they stay in
# sync with a single source of truth.
LICENSE_ISSUER = "rhesis-license-issuer"
LICENSE_AUDIENCE = "rhesis"
LICENSE_ALGORITHM = "EdDSA"

# ``sub`` value that marks a blanket (all-orgs) license.
BLANKET_SUBJECT = "*"

# Standard JWT claim names we read or require.
CLAIM_ISSUER = "iss"
CLAIM_AUDIENCE = "aud"
CLAIM_SUBJECT = "sub"
CLAIM_EXPIRY = "exp"
CLAIM_ISSUED_AT = "iat"
CLAIM_JWT_ID = "jti"
REQUIRED_CLAIMS = (CLAIM_ISSUER, CLAIM_AUDIENCE, CLAIM_SUBJECT, CLAIM_EXPIRY)

# Custom top-level claim holding the license payload, plus its sub-keys.
CLAIM_LICENSE = "lic"
LIC_EDITION = "edition"
LIC_STATUS = "status"
LIC_ALL_FEATURES = "all_features"
LIC_FEATURES = "features"
LIC_LIMITS = "limits"

# Well-known keys inside the ``limits`` map. Limits are open-ended; these are
# just the names the platform understands today.
LIMIT_SEATS = "seats"

# --- Environment variable names --------------------------------------------
ENV_LICENSE = "RHESIS_LICENSE"
ENV_LICENSE_PUBLIC_KEY = "RHESIS_LICENSE_PUBLIC_KEY"
# Private key for the minting/issuance side only — never set on the running
# backend. In production this is mounted into the Cloud Run issuance job from
# Secret Manager via --set-secrets; locally it can be exported for dev minting.
ENV_LICENSE_PRIVATE_KEY = "RHESIS_LICENSE_PRIVATE_KEY"
ENV_ALLOW_UNLICENSED = "RHESIS_LICENSE_ALLOW_UNLICENSED"

# Grace period applied when checking expiry live (seconds).  Prevents
# spurious denials during clock skew or brief cert-rotation windows.
EXPIRY_LEEWAY_SECONDS = 60


@dataclass(frozen=True)
class Entitlements:
    """Decoded and structurally-validated license payload.

    Fields mirror the ``lic`` claim of the license JWT::

        {
          "edition": "enterprise|trial",
          "status": "active|past_due|canceled",
          "all_features": true,
          "features": ["sso", "api_clients"],
          "limits": {"seats": 50}
        }

    ``sub`` and ``expires_at`` come from the standard JWT top-level claims.
    ``jti`` is stored for audit logging / revocation checks in later units.
    """

    sub: str
    """JWT ``sub`` claim: org UUID or :data:`BLANKET_SUBJECT` for a blanket license."""

    edition: LicenseEdition
    """License tier (see :class:`LicenseEdition`)."""

    status: LicenseStatus
    """Billing status (see :class:`LicenseStatus`)."""

    all_features: bool
    """When ``True`` the license unlocks every registered EE feature."""

    features: frozenset[str]
    """Explicit feature list; used when ``all_features`` is ``False``."""

    expires_at: Optional[datetime]
    """UTC expiry derived from the ``exp`` JWT claim; ``None`` if absent."""

    limits: dict[str, Any] = field(default_factory=dict)
    """Arbitrary limit map (e.g. ``{"seats": 50}``)."""

    jti: Optional[str] = None
    """JWT ID for audit logging and future revocation support."""

    def is_expired(self) -> bool:
        """Return ``True`` if the license has passed its expiry window.

        Applies :data:`EXPIRY_LEEWAY_SECONDS` so brief clock-skew or
        rotation windows do not cause spurious denials.  Returns ``False``
        when ``expires_at`` is ``None`` (no expiry claim → never expires).
        """
        if self.expires_at is None:
            return False
        now = datetime.now(tz=timezone.utc)
        return now > self.expires_at + timedelta(seconds=EXPIRY_LEEWAY_SECONDS)

    def is_active(self) -> bool:
        """Return ``True`` if the billing status currently grants access.

        Single source of truth for the status gate shared by
        ``allows_feature`` and ``info`` on the provider, so the two can never
        disagree about which statuses count as licensed.
        """
        return self.status in ACTIVE_STATUSES

    def allows(self, feature_name: str) -> bool:
        """Return ``True`` if this license covers *feature_name*."""
        if self.all_features:
            return True
        return feature_name in self.features


__all__ = [
    "ACTIVE_STATUSES",
    "BLANKET_SUBJECT",
    "CLAIM_AUDIENCE",
    "CLAIM_EXPIRY",
    "CLAIM_ISSUED_AT",
    "CLAIM_ISSUER",
    "CLAIM_JWT_ID",
    "CLAIM_LICENSE",
    "CLAIM_SUBJECT",
    "Entitlements",
    "EXPIRY_LEEWAY_SECONDS",
    "ENV_ALLOW_UNLICENSED",
    "ENV_LICENSE",
    "ENV_LICENSE_PRIVATE_KEY",
    "ENV_LICENSE_PUBLIC_KEY",
    "LICENSE_ALGORITHM",
    "LICENSE_AUDIENCE",
    "LICENSE_ISSUER",
    "LicenseEdition",
    "LicenseStatus",
    "LIC_ALL_FEATURES",
    "LIC_EDITION",
    "LIC_FEATURES",
    "LIC_LIMITS",
    "LIC_STATUS",
    "LIMIT_SEATS",
    "REQUIRED_CLAIMS",
]
