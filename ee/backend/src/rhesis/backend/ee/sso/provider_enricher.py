"""SSO enricher for the ``/auth/providers`` endpoint.

Registered with core's
:func:`~rhesis.backend.app.auth.provider_hooks.register_provider_enricher`
in :func:`rhesis.backend.ee.bootstrap`. Core delegates per-org provider
decoration to this callback rather than reading
``organization.sso_config`` itself, which keeps SSO-shaped JSON keys
(``enabled``, ``allowed_auth_methods``) entirely inside EE.

Behaviour
---------
For each call:

1. If no organisation is passed in, the list is returned unchanged. The
   public ``/auth/providers`` endpoint is reachable without an ``org``
   query param and we never want to volunteer SSO information in that
   case.

2. If SSO is not :meth:`~rhesis.backend.app.features.FeatureRegistry.is_available`
   for the organisation (unregistered, unlicensed, or runtime check
   failing), the list is returned unchanged.

3. Otherwise the org's ``sso_config`` is parsed:
   - When ``enabled`` is truthy, an ``sso`` provider entry is appended
     with a ``login_url`` derived from the slug (or, as a fallback, the
     org UUID).
   - When ``allowed_auth_methods`` is set, it acts as an org-level allow
     list and prunes the provider list to only the named methods. This
     is how an admin pins their org to "SSO only" or "SSO + Google" and
     hides the rest of the available providers from the login page.
"""

from __future__ import annotations

from typing import List, Optional

from rhesis.backend.app.features import FeatureName, FeatureRegistry
from rhesis.backend.app.models.organization import Organization


def sso_provider_enricher(
    providers: List[dict],
    org: Optional[Organization],
) -> List[dict]:
    """Decorate the provider list with the SSO entry for *org*."""
    if org is None:
        return providers

    if not FeatureRegistry.is_available(FeatureName.SSO, org):
        return providers

    sso_cfg: dict = org.sso_config or {}
    if not sso_cfg.get("enabled"):
        return providers

    login_path = (
        f"/auth/sso/{org.slug}" if org.slug else f"/auth/sso/{org.id}"
    )
    enriched = [
        *providers,
        {
            "name": "sso",
            "display_name": "SSO",
            "type": "oauth",
            "enabled": True,
            "login_url": login_path,
        },
    ]

    allowed_methods = sso_cfg.get("allowed_auth_methods")
    if allowed_methods:
        allowed = set(allowed_methods)
        enriched = [p for p in enriched if p["name"] in allowed]

    return enriched


__all__ = ["sso_provider_enricher"]
