"""Config-backed quota provider that resolves policy from tier_config.yaml.

Installed by :func:`~rhesis.backend.ee.bootstrap` when the EE package
is present.  Resolves the organization's edition from the license
provider, then looks up the limits and overage policy defined in the
YAML-loaded tier catalog.  Unlicensed orgs get the community (free-tier)
entry.

On top of that tier baseline, any bespoke per-org overrides carried in the
license token's ``custom_limits`` claim are applied per-resource. That is the
mechanism behind the pricing page's "custom" enterprise limits: the
``enterprise`` tier is ``null`` (unlimited) across the board in the catalog,
and a negotiated cap is minted into the customer's own token rather than
written into a catalog every org shares.

Two properties of that split are worth stating, because both are load-bearing:

- **Absent means unlimited, not zero.** A resource the token does not name
  keeps its catalog limit, which for ``enterprise`` is unlimited. So every
  enterprise license minted before this claim existed keeps behaving exactly
  as it did, with nothing to re-mint.
- **The catalog stays live.** Overrides are read from ``custom_limits``, never
  from the mint-time ``limits`` snapshot, so changing a published tier number
  takes effect for everyone on that tier without re-issuing tokens. Only the
  resources actually negotiated are pinned.
"""

from __future__ import annotations

import logging
from typing import Optional

from rhesis.backend.app.models.organization import Organization
from rhesis.backend.app.quota import QuotaPolicy, limits_from_wire
from rhesis.backend.ee.licensing.entitlements import LIC_CUSTOM_LIMITS, LicenseEdition
from rhesis.backend.ee.licensing.tiers import resolve_policy

logger = logging.getLogger(__name__)


class ConfigQuotaProvider:
    """Resolves quota policy from the tier YAML config.

    For each organization, it determines the edition from the license
    provider's entitlements, then returns the limits and overage policy
    defined in the config for that edition, with any bespoke per-org
    overrides from the license token overlaid on top.
    """

    def _license_info(self, org: Optional[Organization]) -> dict:
        """Return the installed license provider's info dict for *org*.

        Read once per :meth:`get_policy` call and passed down, rather than
        resolved separately for the edition and the overrides -- two lookups
        could disagree if the license changed between them, and would verify
        the same token twice.
        """
        if org is None:
            return {}

        from rhesis.backend.app.features import FeatureRegistry

        return FeatureRegistry.license_info(org)

    def _resolve_edition(self, org: Optional[Organization], info: dict) -> Optional[LicenseEdition]:
        """Determine the org's edition from the license provider.

        Returns ``None`` (meaning community limits) unless the org holds an
        *active* license. ``info`` keeps reporting the lapsed edition so the UI
        can say which license expired, but granting that tier's limits on the
        strength of the name alone would leave a canceled or past-due
        enterprise org on unlimited quota indefinitely -- billing status is
        exactly the thing that is supposed to end that.
        """
        if org is None:
            return None

        if not info.get("licensed"):
            return None

        edition_str = info.get("edition")
        if edition_str is None:
            return None

        # LicenseEdition._missing_ coerces any unrecognized value to
        # UNKNOWN rather than raising, so check explicitly -- a bare
        # try/except ValueError here would never fire.
        edition = LicenseEdition(edition_str)
        if edition is LicenseEdition.UNKNOWN:
            logger.warning(
                "Unknown edition %r on license info for org %s, falling back to community limits",
                edition_str,
                org.id,
            )
            return None
        return edition

    def get_policy(self, org: Optional[Organization] = None) -> QuotaPolicy:
        info = self._license_info(org)
        edition = self._resolve_edition(org, info)
        policy = resolve_policy(edition)

        overrides = limits_from_wire(info.get(LIC_CUSTOM_LIMITS))
        if not overrides:
            return policy

        logger.info(
            "Applying %d custom limit override(s) for org %s (edition=%s): %s",
            len(overrides),
            getattr(org, "id", None),
            edition.value if edition else None,
            {r.value: v for r, v in overrides.items()},
        )
        return policy.with_limit_overrides(overrides)


__all__ = ["ConfigQuotaProvider"]
