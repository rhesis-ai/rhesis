"""SignedTokenLicenseProvider — EE license enforcement.

Precedence (first match wins):

1. ``RHESIS_LICENSE`` env var — a blanket ``sub:"*"`` token covering all
   orgs; used for simple single-tenant deployments or dev overrides.
2. ``organization.license`` column — a per-org token where ``sub`` must
   equal the org's UUID (string comparison, case-insensitive).
3. Deny — no valid token found for this org.

Dev fallback (permissive): only when ``RHESIS_LICENSE_ALLOW_UNLICENSED=1`` is
explicitly set does the provider allow all registered features without a
valid token. This is an explicit opt-in for local development — every other
environment, including ``development`` and ``staging`` ``BACKEND_ENV``
values, is fail-closed and requires a real license.

Fail-closed on missing keys: if no public keys are loaded, the provider
denies all features and logs a one-time warning.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from rhesis.backend.app.features import Feature
from rhesis.backend.app.models.organization import Organization
from rhesis.backend.ee.licensing.entitlements import (
    BLANKET_SUBJECT,
    ENV_ALLOW_UNLICENSED,
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
        if self._is_dev_fallback():
            return True

        entitlements = self._resolve_entitlements(org)
        if entitlements is None:
            return False

        # Expiry is already enforced by verify_token (expired -> None above);
        # only the billing-status gate remains, shared with info() below.
        if not entitlements.is_active():
            return False

        return entitlements.allows(feature.name.value)

    def info(self, org: Optional[Organization] = None) -> dict:
        """Return opaque license metadata for the ``GET /features`` response."""
        if self._is_dev_fallback():
            return self._unlicensed_info(LicenseEdition.DEV)

        if org is None:
            return self._unlicensed_info(LicenseEdition.COMMUNITY)

        entitlements = self._resolve_entitlements(org)
        if entitlements is None:
            return self._unlicensed_info(LicenseEdition.COMMUNITY)

        # verify_token already dropped expired tokens; is_active() is the same
        # status gate allows_feature uses, so the two can never disagree.
        if not entitlements.is_active():
            return self._unlicensed_info(entitlements.edition)

        return {"edition": entitlements.edition.value, "licensed": True}

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

    def _is_dev_fallback(self) -> bool:
        """Return ``True`` if the unlicensed permissive mode is active.

        Explicit opt-in only, via
        :data:`~rhesis.backend.ee.licensing.entitlements.ENV_ALLOW_UNLICENSED`.
        Deliberately does **not** key off ``settings.is_development`` —
        ``BACKEND_ENV`` values other than ``production`` (e.g. ``staging``)
        must still require a real license.
        """
        return os.environ.get(ENV_ALLOW_UNLICENSED, "").strip() == "1"

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
