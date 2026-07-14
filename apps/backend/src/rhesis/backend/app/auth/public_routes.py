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
    "/auth/local-login",
    "/home",
    "/home/",
    "/feedback/",
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
]


#: Routes that require authentication but are exempt from the permission-level
#: authorization check enforced by ``apply_authz_backstop``.
#:
#: Format: ``frozenset`` of ``(HTTP_METHOD, path)`` tuples so a single path
#: can be exempt for only specific verbs (e.g. ``POST /organizations/`` during
#: onboarding, but not ``GET /organizations/`` once the user has an org).
#:
#: Lifecycle is the same as ``PUBLIC_ROUTES``: the set is evaluated before
#: ``apply_authz_backstop`` runs, so EE can extend it at bootstrap time.
AUTHZ_EXEMPT_ROUTES: frozenset[tuple[str, str]] = frozenset(
    {
        # Onboarding: the creating user has no organization yet; any authz check
        # that depends on organization context would fail with 403 before the org
        # is created.  Authentication (require_current_user_or_token) still runs.
        ("POST", "/organizations/"),
        # Bootstrap / reflexive: these tell the caller what they may do.
        # Requiring a prior permission to call them creates a chicken-and-egg loop.
        ("GET", "/me/permissions"),
        ("GET", "/capabilities"),
        # Feature catalog: the frontend needs this before any RBAC context is set.
        # Authentication is still enforced; the response is org-filtered in the handler.
        ("GET", "/features"),
        # Demo / test endpoint — carries no meaningful permission boundary.
        ("GET", "/home/protected"),
        # Profile update during onboarding: the user may not have an org yet when
        # they first complete their profile (name, picture, etc.) after OAuth sign-in.
        # Cross-user update authorization is enforced by the in-handler authorize() call.
        ("PUT", "/users/{user_id}"),
        # Onboarding: new users accept T&C before they have an organization.
        ("POST", "/auth/accept-terms"),
        ("GET", "/auth/terms-status"),
        # Cross-project entity resolution: spans multiple resource types
        # (test, endpoint, metric, ...) so no single resource+verb capability
        # applies. Authorization is enforced in-handler: the lookup is always
        # organization_id-scoped, and project-level access is resolved to
        # "no_access" (details withheld) when the caller lacks a
        # ProjectMembership row for the entity's project.
        ("GET", "/resolve"),
    }
)

__all__ = ["AUTHZ_EXEMPT_ROUTES", "PUBLIC_ROUTES"]
