"""Config-backed quota provider that resolves limits from tier_config.yaml.

Installed by :func:`~rhesis.backend.ee.bootstrap` when the EE package
is present.  Resolves the organization's edition from the license
provider, then looks up per-resource limits in the YAML-loaded tier
catalog.  Unlicensed orgs get the community (free-tier) entry.
"""

from __future__ import annotations

import logging
from typing import Optional

from rhesis.backend.app.models.organization import Organization
from rhesis.backend.app.quota import QuotaResource
from rhesis.backend.ee.licensing.entitlements import LicenseEdition
from rhesis.backend.ee.licensing.tiers import resolve_limits

logger = logging.getLogger(__name__)


class ConfigQuotaProvider:
    """Resolves quota limits from the tier YAML config.

    For each organization, it determines the edition from the license
    provider's entitlements, then returns the limits defined in the
    config for that edition.
    """

    def _resolve_edition(self, org: Optional[Organization]) -> Optional[LicenseEdition]:
        """Determine the org's edition from the license provider."""
        if org is None:
            return None

        from rhesis.backend.app.features import FeatureRegistry

        info = FeatureRegistry.license_info(org)
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

    def get_limits(self, org: Optional[Organization] = None) -> dict[QuotaResource, int | None]:
        edition = self._resolve_edition(org)
        return resolve_limits(edition)


__all__ = ["ConfigQuotaProvider"]
