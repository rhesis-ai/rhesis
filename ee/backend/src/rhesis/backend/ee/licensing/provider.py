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
from rhesis.backend.ee.licensing.tiers import is_sellable
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
        ``routers/features.py`` builds its ``LicenseInfo`` from ``edition``,
        ``licensed`` and ``is_paid`` only, and reports limits separately from
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

        info: dict = {
            "edition": entitlements.edition.value,
            "licensed": True,
            "is_paid": is_sellable(entitlements.edition),
        }
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

        ``is_paid`` describes the *tier*, not the licence state, so a lapsed
        enterprise licence still reports ``is_paid=True`` with
        ``licensed=False``. Those are the two facts a client needs to tell
        "free tier" apart from "paid tier, expired" -- collapsing them into one
        flag is what forced the UI to guess from the edition name.
        """
        return {
            "edition": edition.value,
            "licensed": False,
            "is_paid": is_sellable(edition),
        }

    def _blanket_entitlements(self) -> Optional[Entitlements]:
        """Entitlements from the ``RHESIS_LICENSE`` env token, if it is a
        blanket one. ``None`` when unset, unverifiable, or bound to a
        specific org rather than ``*``."""
        env_token = os.environ.get(ENV_LICENSE, "").strip()
        if not env_token:
            return None

        entitlements = verify_token(env_token)
        if entitlements is None:
            return None
        if entitlements.sub == BLANKET_SUBJECT:
            return entitlements

        logger.debug(
            "%s token sub=%s is not %r; falling through to org token",
            ENV_LICENSE,
            entitlements.sub,
            BLANKET_SUBJECT,
        )
        return None

    def _org_entitlements(self, org: Organization) -> Optional[Entitlements]:
        """Entitlements from ``organization.license``, if the token's ``sub``
        matches this org. ``None`` otherwise."""
        org_token = getattr(org, "license", None)
        if not org_token:
            return None

        entitlements = verify_token(org_token)
        if entitlements is None:
            return None

        org_id_str = str(org.id).lower()
        if entitlements.sub.lower() == org_id_str:
            return entitlements

        logger.debug(
            "org.license token sub=%s does not match org.id=%s; denying",
            entitlements.sub,
            org_id_str,
        )
        return None

    def _resolve_entitlements(self, org: Organization) -> Optional[Entitlements]:
        """Resolve entitlements for *org*.

        **An active licence always beats an inactive one.** Within that, the
        declared precedence holds:

        1. ``RHESIS_LICENSE`` env (blanket ``sub:"*"``)
        2. ``organization.license`` (per-org, ``sub`` must match the org UUID)

        The active-first rule is not cosmetic. This used to return a blanket
        token the moment its ``sub`` was ``*``, without checking its status, so
        a stale or canceled ``RHESIS_LICENSE`` **shadowed an org's own valid
        licence** -- the org was reported as unlicensed and held to community
        limits immediately after being issued a good token, with the blanket
        token's edition as the only clue.

        When nothing is active, an inactive licence is still returned rather
        than ``None``. Falling through to ``None`` would report such an org as
        ``community``, losing the one thing worth saying: which licence
        expired. Callers gate on
        :meth:`~rhesis.backend.ee.licensing.entitlements.Entitlements.is_active`
        anyway, so an inactive result grants nothing.
        """
        blanket = self._blanket_entitlements()
        if blanket is not None and blanket.is_active():
            return blanket

        per_org = self._org_entitlements(org)
        if per_org is not None and per_org.is_active():
            if blanket is not None:
                logger.info(
                    "%s token is present but not active (status=%s); using the "
                    "org's own active licence instead",
                    ENV_LICENSE,
                    blanket.status.value,
                )
            return per_org

        # Nothing active. Prefer the blanket token's edition, matching the
        # precedence above, so the lapsed state is still reported.
        return blanket if blanket is not None else per_org


__all__ = ["SignedTokenLicenseProvider"]
