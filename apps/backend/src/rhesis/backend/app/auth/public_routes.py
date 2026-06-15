"""Public route registry.

:data:`PUBLIC_ROUTES` drives ``apply_auth_backstop`` in ``main.py``: routes
whose exact path is in this list skip the baseline authentication
dependency. Every other HTTP route gets ``require_current_user_or_token``
injected as a defense-in-depth backstop, so a route is never accidentally
exposed without authentication. Per-handler dependencies still enforce the
specific policy (session-only, superuser, project-membership, etc.) and
remain authoritative.

Why a mutable module-level list rather than a frozen tuple?
-----------------------------------------------------------
EE features may need to add their own public paths (e.g. SSO callback
URLs). By exposing the list as a regular module attribute, EE can
extend it from :func:`~rhesis.backend.ee.bootstrap` *before*
``apply_auth_backstop`` runs — at which point the backstop evaluates
``path in PUBLIC_ROUTES`` and sees the extended list.

Note: the check is an **exact** match against the fully-resolved route
path (prefix + route), so trailing slashes matter (e.g. ``/home/`` and
``/feedback/`` are listed with their trailing slash).

Order of operations during startup:

1. Core imports and includes its routers.
2. Core calls ``bootstrap_ee(app)``; EE extends ``PUBLIC_ROUTES`` with its
   own public paths and includes its routers.
3. Core defines app-level routes (``/``, ``/health``).
4. Core calls ``apply_auth_backstop(app)`` last, which evaluates every
   registered route against the now-complete ``PUBLIC_ROUTES``.

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
    "/home/",
    "/feedback/",
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
]

__all__ = ["PUBLIC_ROUTES"]
