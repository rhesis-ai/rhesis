"""Public and token-enabled route registry.

These two lists drive ``AuthenticatedAPIRoute.get_dependencies`` in
``main.py``: paths in :data:`PUBLIC_ROUTES` skip authentication entirely;
paths whose prefix matches an entry in :data:`TOKEN_ENABLED_ROUTES`
accept either a session cookie or an API token; everything else
requires a session.

Why a mutable module-level list rather than a frozen tuple?
-----------------------------------------------------------
EE features may need to add their own public paths (e.g. SSO callback
URLs). By exposing the list as a regular module attribute, EE can
extend it from :func:`~rhesis.backend.ee.bootstrap` *before* it calls
``app.include_router(...)`` for its own routes — at which point the
auth class evaluates ``self.path in PUBLIC_ROUTES`` and sees the
extended list.

Order of operations during startup:

1. Core imports its routers and calls ``app.include_router`` for each
   (route_class evaluates against ``PUBLIC_ROUTES`` as it is at this
   point — core paths only).
2. Core calls ``bootstrap_ee(app)``.
3. EE extends ``PUBLIC_ROUTES`` with its own paths.
4. EE calls ``app.include_router(<ee_router>)`` (route_class now sees
   the extended list and recognises EE-owned public paths).

The list must therefore stay mutable for EE to extend; we deliberately
do not freeze it.
"""

from __future__ import annotations

#: Routes that require no authentication (public endpoints).
PUBLIC_ROUTES: list[str] = [
    "/",
    "/auth/login",
    "/auth/login/{provider}",
    "/auth/login/email",
    "/auth/callback",
    "/auth/logout",
    "/auth/providers",
    "/auth/register",
    "/auth/verify-email",
    "/auth/resend-verification",
    "/auth/forgot-password",
    "/auth/reset-password",
    "/auth/magic-link",
    "/auth/magic-link/verify",
    "/auth/exchange-code",
    "/auth/refresh",
    "/auth/verify",
    "/auth/demo",
    "/auth/local-login",
    "/home",
    "/docs",
    "/redoc",
    "/openapi.json",
]

#: Route prefixes that accept session-or-token authentication.
TOKEN_ENABLED_ROUTES: list[str] = [
    "/api/",
    "/tokens/",
    "/tasks/",
    "/test_sets/",
    "/topics/",
    "/prompts/",
    "/test_configurations/",
    "/test_results/",
    "/test_runs/",
    "/services/",
    "/organizations/",
    "/demographics/",
    "/dimensions/",
    "/tags/",
    "/users/",
    "/statuses/",
    "/risks/",
    "/projects/",
    "/tests/",
    "/test-contexts/",
    "/comments/",
    "/sources/",
    "/models/",
    "/connector/",
    "/explorer/",
    "/features",
]

__all__ = ["PUBLIC_ROUTES", "TOKEN_ENABLED_ROUTES"]
