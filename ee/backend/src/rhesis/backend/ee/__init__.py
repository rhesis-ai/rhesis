"""Rhesis Enterprise Edition backend package.

This package registers EE features with the core FeatureRegistry at
application startup. It is loaded conditionally — if the package is not
installed (i.e. the ``ee`` extra was not requested), the application
runs in Community mode without any of the code in this directory being
imported.

Entry point
-----------
:func:`bootstrap` is the single function called by core at startup
(via ``apps/backend/src/rhesis/backend/app/ee_bootstrap.py``).
It receives the FastAPI app instance and registers all EE features and
routers that the current license allows.

Dependency rule
---------------
EE code may freely import from ``rhesis.backend.*`` (core). Core code
must NEVER import from ``rhesis.backend.ee.*`` directly. The only
core-side coupling is the ``try/except ImportError`` in
``ee_bootstrap.py``. Violating this rule breaks the "delete ee/ to get
a pure MIT build" guarantee and is caught by the ``community-boundary``
CI job.
"""

from __future__ import annotations

import logging
from importlib.metadata import PackageNotFoundError, version
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)

try:
    __version__ = version("rhesis-backend-ee")
except PackageNotFoundError:
    # Reachable only in unusual dev configurations where the package metadata
    # is missing. Better to surface "unknown" than silently lie about a stale
    # hard-coded version that drifts from pyproject.toml.
    __version__ = "0+unknown"


def bootstrap(app: "FastAPI") -> None:
    """Register EE features and routers with the FastAPI *app*.

    Called once at application startup by
    :func:`rhesis.backend.app.ee_bootstrap.bootstrap_ee`. Steps:

    1. Register each EE feature with
       :class:`~rhesis.backend.app.features.FeatureRegistry`.
    2. Hook into core extension points (provider enrichers, public route
       list, refresh-client minter) *before* including any EE routers,
       so the auth class sees the extended public route list at
       route-registration time and the refresh hook is in place if any
       request lands during startup.
    3. Install the token-endpoint cache-headers middleware so every
       response from ``/auth/token-exchange`` and ``/auth/refresh``
       carries ``Cache-Control: no-store`` -- middleware ordering is
       last-added-runs-first, so we add it before mounting the routers.
    4. Include EE routers, inheriting the core ``route_class`` so
       path-based authentication applies uniformly.
    """
    import os

    from rhesis.backend.app.auth.provider_hooks import register_provider_enricher
    from rhesis.backend.app.auth.public_routes import PUBLIC_ROUTES
    from rhesis.backend.app.auth.refresh_client_hook import (
        register_refresh_client_minter,
    )
    from rhesis.backend.app.config.settings import get_application_settings
    from rhesis.backend.app.features import Feature, FeatureName, FeatureRegistry
    from rhesis.backend.ee.api_clients.cache_headers import (
        TokenEndpointCacheHeadersMiddleware,
    )
    from rhesis.backend.ee.api_clients.refresh_minter import (
        mint_for_client_bound_refresh,
    )
    from rhesis.backend.ee.api_clients.router import router as api_clients_router
    from rhesis.backend.ee.rbac.provider import PermissionAuthorizationProvider
    from rhesis.backend.ee.rbac.router import router as rbac_router
    from rhesis.backend.ee.sso.provider_enricher import sso_provider_enricher
    from rhesis.backend.ee.sso.router import router as sso_router
    from rhesis.backend.ee.sso.runtime_check import sso_runtime_check
    from rhesis.backend.ee.sso.token_exchange.router import (
        router as token_exchange_router,
    )

    # ---- Startup configuration assertions --------------------------------
    # In production the audit log requires AUDIT_HASH_KEY (HMAC over
    # email for hashed_email). Missing it would silently disable a
    # forensic capability; refuse to bootstrap rather than ship an
    # un-correlatable audit stream.
    settings = get_application_settings()
    if not settings.is_development:
        if not os.getenv("AUDIT_HASH_KEY"):
            raise RuntimeError(
                "AUDIT_HASH_KEY must be set in non-dev environments; "
                "the API Clients audit log relies on it for hashed_email"
            )

    # ---- Feature registry -----------------------------------------------
    FeatureRegistry.register(
        Feature(
            name=FeatureName.SSO,
            display_name="Single Sign-On",
            runtime_check=sso_runtime_check,
            description="Per-organization OIDC-based SSO.",
        )
    )

    # ---- RBAC feature -----------------------------------------------
    FeatureRegistry.register(
        Feature(
            name=FeatureName.RBAC,
            display_name="Role-Based Access Control",
            description=(
                "Full RBAC: project-role overrides, custom roles, and "
                "org-level role assignments. Activates the "
                "PermissionAuthorizationProvider (SP8)."
            ),
        )
    )

    # Install the EE authorization provider.  The community
    # DefaultAuthorizationProvider is replaced for the lifetime of the process;
    # per-org RBAC availability is checked inside the provider itself.
    from rhesis.backend.app.auth.rbac import set_authorization_provider

    set_authorization_provider(PermissionAuthorizationProvider())

    # API Clients depends on SSO at runtime: the token-exchange flow
    # validates the subject token against the org's SSOConfig issuer.
    # Composing the runtime check explicitly here is what lets a
    # license that allows API_CLIENTS but not SSO fail closed at
    # request time rather than 500ing on a missing SSOConfig.
    def _api_clients_runtime_check() -> bool:
        # SSO encryption must be configured for token-exchange to work.
        return sso_runtime_check()

    FeatureRegistry.register(
        Feature(
            name=FeatureName.API_CLIENTS,
            display_name="API Clients",
            runtime_check=_api_clients_runtime_check,
            description=(
                "Per-organization machine-to-machine clients that can "
                "trade an OIDC subject token for a Rhesis JWT via "
                "RFC 8693 token exchange."
            ),
        )
    )

    # ---- Hooks -----------------------------------------------------------
    # Plug into core's provider discovery so SSO appears in the
    # /auth/providers response without core knowing how SSO works.
    register_provider_enricher(sso_provider_enricher)

    # Install the client-bound refresh-token minter. Core's
    # /auth/refresh delegates to this when the refresh row carries a
    # client_id; without it core fails closed (503) on any
    # client-bound refresh.
    register_refresh_client_minter(mint_for_client_bound_refresh)

    # ---- Public routes (must run before include_router) ------------------
    # AuthenticatedAPIRoute resolves dependencies at registration time;
    # extending the existing list (rather than rebinding) is what lets
    # the running auth class see the new entries.
    for path in (
        "/auth/sso/{org_id}",
        "/auth/sso/callback",
        # Token exchange is a public OAuth endpoint -- the request
        # carries its own client credentials in HTTP Basic / form,
        # not a Rhesis session.
        "/auth/token-exchange",
    ):
        if path not in PUBLIC_ROUTES:
            PUBLIC_ROUTES.append(path)

    # ---- Middleware ------------------------------------------------------
    app.add_middleware(TokenEndpointCacheHeadersMiddleware)

    # ---- Routers ---------------------------------------------------------
    # EE routers must use the same authenticated route class as core routers
    # so the public/token route lists apply uniformly. Without this, the SSO
    # admin endpoints would silently fall back to vanilla APIRoute and any
    # future EE route relying on path-based auth would break.
    for r in (sso_router, api_clients_router, token_exchange_router, rbac_router):
        r.route_class = app.router.route_class
        app.include_router(r)

    logger.info("EE bootstrap complete - registered features: [sso, api_clients, rbac]")
