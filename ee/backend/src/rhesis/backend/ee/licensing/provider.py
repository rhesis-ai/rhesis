"""SignedTokenLicenseProvider — EE license enforcement.

Precedence (first match wins):

1. ``RHESIS_LICENSE`` env var — a blanket ``sub:"*"`` token covering all
   orgs; used for simple single-tenant deployments.
2. ``organization.license`` column — a per-org token where ``sub`` must
   equal the org's UUID (string comparison, case-insensitive).
3. Deny — no valid token found for this org.

No environment-based bypass exists. A missing, invalid, or expired license
results in the ``community`` edition, identically in every environment —
local, development, staging, production, and self-hosted. There is no
special "dev" posture: community is always the safe, always-available
default, the same way the rest of the open-core model already works.

Fail-closed on missing keys: if no public keys are loaded, the provider
denies all features and logs a one-time warning.

Blanket tokens are not bound to a specific customer or deployment. The
only checks are signature, expiry, status, and ``sub == "*"`` — nothing
ties the token to *which* deployment presents it. A self-hosted customer
who copies their ``RHESIS_LICENSE`` value to a second, unrelated
deployment gets the same entitlements there too, with nothing in this
provider to detect or prevent it. This is a deliberate scope decision, not
an oversight: the alternative (a domain- or installation-ID-binding claim,
checked locally) was considered and explicitly rejected in favor of
relying on the license agreement — the same tradeoff a lot of on-prem
enterprise software makes, and consistent with this provider's "no
phone-home" design (see the licensing package's issuance-side workflow
docs). Per-org tokens (``organization.license``, via :func:`~rhesis.
backend.ee.licensing.mint.issue`) are unaffected: their ``sub`` must match
the org's UUID, so those already can't be replayed onto a different org.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from rhesis.backend.app.features import Feature
from rhesis.backend.app.models.organization import Organization
from rhesis.backend.ee.licensing.entitlements import (
    BLANKET_SUBJECT,
    ENV_LICENSE,
    Entitlements,
    LicenseEdition,
)
from rhesis.backend.ee.licensing.verify import verify_token

logger = logging.getLogger(__name__)


class SignedTokenLicenseProvider:
    """EE license provider backed by signed Ed25519 JWTs.

    Install via
    :meth:`~rhesis.backend.app.features.FeatureRegistry.set_license_provider`
    during EE bootstrap.  The provider is stateless (all state lives in
    the JWT or in environment variables) and therefore safe to share across
    threads.
    """

    # ------------------------------------------------------------------ #
    # Public LicenseProvider interface
    # ------------------------------------------------------------------ #

    def allows_feature(self, feature: Feature, org: Organization) -> bool:
        """Return ``True`` iff *org* holds a valid license covering *feature*."""
        entitlements = self._resolve_entitlements(org)
        if entitlements is None:
            return False

        # Expiry is already enforced by verify_token (expired -> None above);
        # only the billing-status gate remains, shared with info() below.
        if not entitlements.is_active():
            return False

        return entitlements.allows(feature.name.value)

    def info(self, org: Optional[Organization] = None) -> dict:
        """Return opaque license metadata for the ``GET /features`` response.

        ``custom_limits`` carries the token's ``lic.custom_limits`` claim
        verbatim (wire form: string resource names). It is present only for a
        licensed, active org whose token actually carries the claim --
        :class:`~rhesis.backend.ee.licensing.quota_provider.ConfigQuotaProvider`
        reads it to overlay a bespoke deal's negotiated caps on the tier
        defaults. This is the same channel it already resolves ``edition``
        through, which is equally enforcement-critical.

        The mint-time ``limits`` snapshot is deliberately *not* exposed: it is
        for audit only, and handing it to the quota provider would pin the org
        to its mint-time numbers (see :data:`~rhesis.backend.ee.licensing.entitlements.LIC_LIMITS`).

        Note this does *not* widen the ``GET /features`` payload:
        ``routers/features.py`` builds its ``LicenseInfo`` from ``edition``
        and ``licensed`` only, and reports limits separately from
        :meth:`~rhesis.backend.app.quota.QuotaRegistry.get_limits` -- which
        resolves through the quota provider, so the overlay is reflected there
        already.
        """
        if org is None:
            return self._unlicensed_info(LicenseEdition.COMMUNITY)

        entitlements = self._resolve_entitlements(org)
        if entitlements is None:
            return self._unlicensed_info(LicenseEdition.COMMUNITY)

        # verify_token already dropped expired tokens; is_active() is the same
        # status gate allows_feature uses, so the two can never disagree.
        if not entitlements.is_active():
            return self._unlicensed_info(entitlements.edition)

        info: dict = {"edition": entitlements.edition.value, "licensed": True}
        # Omitted rather than sent as {} when the token carries no override, so
        # "no custom limits" and "an empty override map" are the same thing on
        # the consuming side instead of two cases it has to distinguish.
        if entitlements.custom_limits:
            info["custom_limits"] = dict(entitlements.custom_limits)
        return info

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _unlicensed_info(edition: LicenseEdition) -> dict:
        """Build an ``info`` payload for an unlicensed posture of *edition*.

        Returns ``edition`` as a plain string (``.value``) so the wire format
        never leaks an ``Enum`` repr through core's ``str(...)`` coercion.
        """
        return {"edition": edition.value, "licensed": False}

    def _resolve_entitlements(self, org: Organization) -> Optional[Entitlements]:
        """Resolve entitlements for *org* using the declared precedence.

        1. ``RHESIS_LICENSE`` env (blanket ``sub:"*"``)
        2. ``org.license`` column (per-org, ``sub`` must match org UUID)
        """
        # --- 1. Blanket env token ---
        env_token = os.environ.get(ENV_LICENSE, "").strip()
        if env_token:
            entitlements = verify_token(env_token)
            if entitlements is not None and entitlements.sub == BLANKET_SUBJECT:
                return entitlements
            if entitlements is not None:
                logger.debug(
                    "%s token sub=%s is not %r; falling through to org token",
                    ENV_LICENSE,
                    entitlements.sub,
                    BLANKET_SUBJECT,
                )

        # --- 2. Per-org column ---
        org_token = getattr(org, "license", None)
        if org_token:
            entitlements = verify_token(org_token)
            if entitlements is not None:
                org_id_str = str(org.id).lower()
                if entitlements.sub.lower() == org_id_str:
                    return entitlements
                logger.debug(
                    "org.license token sub=%s does not match org.id=%s; denying",
                    entitlements.sub,
                    org_id_str,
                )

        return None


__all__ = ["SignedTokenLicenseProvider"]
