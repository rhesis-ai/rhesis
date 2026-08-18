"""FastAPI dependency for quota enforcement.

Thin adapter that routes request-scoped quota checks through
:func:`~rhesis.backend.app.quota.enforcement.enforce_quota`.

Where ``require_feature`` returns 404 to avoid enumerating unlicensed
features, :func:`require_quota` lets
:class:`~rhesis.backend.app.quota.enforcement.QuotaExceededError`
propagate -- the global handler registered in ``main.py`` turns it into
402. Enforcement is not a secret to hide; the client needs the resource,
used and limit to render a sensible message, which 404 cannot carry.

Deliberately does **not** mirror ``feature_gates.py``'s plain-session
``_load_org`` + ``get_db_session`` pattern, even though that is the
sibling gate's shape. ``usage`` (the table :func:`check_quota` reads for
flow resources) carries a ``FORCE``'d RLS policy -- unlike ``organization``,
which is merely RLS-*enabled*, so the app's own DB role is exempt from its
policy and a GUC-less session still reads it fine. ``FORCE`` removes that
owner exemption, so a session with no tenant GUCs bound would have failed
the query outright, or read every org's usage as zero depending on how the
driver surfaces the cast error -- either way, quota enforcement would
never have actually blocked anyone.
:func:`~rhesis.backend.app.dependencies.get_current_organization` already
composes :func:`~rhesis.backend.app.dependencies.get_tenant_db_session`,
which sets those GUCs, and is the primitive ``routers/usage.py`` /
``routers/features.py`` already use to feed ``QuotaRegistry`` lookups --
so this reuses it rather than re-deriving a narrower, RLS-unsafe version
of the same thing.
"""

from __future__ import annotations

from fastapi import Depends, Response
from sqlalchemy.orm import Session

from rhesis.backend.app.dependencies import get_current_organization, get_tenant_db_session
from rhesis.backend.app.models.organization import Organization
from rhesis.backend.app.quota import QuotaResource, QuotaResourceLike
from rhesis.backend.app.quota.enforcement import enforce_quota

#: Set on the response when a SOFT-policy org is past its limit but still
#: inside the grace band -- allowed, but worth surfacing before the request
#: that finally crosses the ceiling gets blocked with no warning.
QUOTA_WARNING_HEADER = "X-Quota-Warning"


def require_quota(resource: QuotaResourceLike):
    """Dependency factory: enforce *resource*'s quota for the current org.

    Raises :class:`~rhesis.backend.app.quota.enforcement.QuotaExceededError`
    when the org has reached its enforceable ceiling for *resource*; the
    global handler in ``main.py`` turns that into HTTP 402. Returns the
    :class:`Organization` on success so route handlers can use it directly,
    the same contract as ``require_feature``.

    ``db`` is requested via :func:`~rhesis.backend.app.dependencies.get_tenant_db_session`
    alongside ``org`` via :func:`~rhesis.backend.app.dependencies.get_current_organization`
    (which itself depends on the same callable). FastAPI caches a dependency
    per callable per request, so both resolve to the *same* tenant-scoped
    session -- required, not cosmetic, since :func:`check_quota` reads a
    FORCE-RLS'd table (see the module docstring).

    When the org is on a ``SOFT`` policy and past the advertised limit but
    still inside the grace band, the request is allowed but the response
    carries a :data:`QUOTA_WARNING_HEADER` header -- the caller is not
    blocked yet, but the next request past the ceiling will be.
    """
    resource = resource if isinstance(resource, QuotaResource) else QuotaResource(resource)

    def _dep(
        response: Response,
        org: Organization = Depends(get_current_organization),
        db: Session = Depends(get_tenant_db_session),
    ) -> Organization:
        verdict = enforce_quota(db, str(org.id), org, resource)
        if verdict.over_limit:
            warning = f"{resource.value}={verdict.used}/{verdict.limit}"
            response.headers[QUOTA_WARNING_HEADER] = warning
        return org

    return _dep


__all__ = ["QUOTA_WARNING_HEADER", "require_quota"]
