"""Provider enrichment extension point for ``GET /auth/providers``.

The base provider list is built by core from
:class:`~rhesis.backend.app.auth.providers.ProviderRegistry`. EE features
(or any future plugin) may need to decorate this list per-organization
— the canonical example is SSO, which appends an ``sso`` provider entry
for orgs that have configured an IdP.

To avoid placing feature-specific knowledge in core, this module exposes
a tiny callback registry. EE registers a callback in its
:func:`~rhesis.backend.ee.bootstrap` and core never has to inspect
``Organization.sso_config`` (or any other EE-shaped JSON) directly.

Contract
--------
An enricher receives the current provider list and an optional
:class:`Organization`. It must return a (possibly new) list. Enrichers
run in registration order; subsequent enrichers see the output of
previous ones.

Enrichers are free to *remove* providers as well as add them — the SSO
enricher uses this to honour ``allowed_auth_methods`` org policy.
"""

from __future__ import annotations

from typing import Callable, List, Optional

from rhesis.backend.app.models.organization import Organization

#: Callback signature for provider list enrichers.
ProviderEnricher = Callable[[List[dict], Optional[Organization]], List[dict]]

_enrichers: List[ProviderEnricher] = []


def register_provider_enricher(enricher: ProviderEnricher) -> None:
    """Register *enricher* to participate in provider-list decoration.

    Idempotent: re-registering the same callable is a no-op so the
    application can call this safely from a bootstrap that may run
    multiple times in test suites.
    """
    if enricher not in _enrichers:
        _enrichers.append(enricher)


def apply_enrichers(
    providers: List[dict],
    org: Optional[Organization],
) -> List[dict]:
    """Run every registered enricher in order, threading the list through."""
    for enricher in _enrichers:
        providers = enricher(providers, org)
    return providers


def reset_enrichers() -> None:
    """Clear the registry. For tests that need a clean state."""
    _enrichers.clear()


__all__ = [
    "ProviderEnricher",
    "apply_enrichers",
    "register_provider_enricher",
    "reset_enrichers",
]
