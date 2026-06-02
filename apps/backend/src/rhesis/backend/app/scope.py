"""
Ambient Request Scope for automatic tenant filtering and stamping.

WHY THIS EXISTS
---------------
Rather than threading (organization_id, user_id, project_id) through every router,
service, CRUD helper, and Celery task, we carry this identity triple as ambient state
that two SQLAlchemy event listeners in models/scope_events.py read:

- auto_filter: adds WHERE organization_id=... (and project_id=...) to every SELECT
- auto_stamp:  fills organization_id / user_id / project_id on INSERT when None

WHERE THE SCOPE LIVES
---------------------
The listeners read the scope from Session.info['_scope'] first, falling back to the
ContextVar below. Session.info is the authoritative source for DB-bound work because
it is visible to the listeners no matter which thread issues the query (FastAPI runs
sync deps in an anyio threadpool while async routes run in the event loop, so a
ContextVar bound in the dep is not reliably visible to the handler's queries). The
ContextVar is for callers that need ambient scope WITHOUT a DB session (e.g. explicit
bind_scope() in scripts/tests).

HOW TO USE
----------
Normal flow (FastAPI):
    get_db_with_tenant_variables() stores the scope on Session.info automatically.
    Nothing extra to do in routers or CRUD.

Normal flow (Celery):
    BaseTask.get_db_session() routes through get_db_with_tenant_variables(), so the
    scope is stored on Session.info for the lifetime of the task's DB session.

Admin / cross-org reads:
    with bypass_tenant_filter():
        results = db.query(SomeModel).all()   # filter skipped
    Auto-stamp is NOT affected by bypass - inserts still get the caller's identity.

Per-query bypass (legacy Query API only):
    query._bypass_scope = True

    Note: db.execute(select(...)) / ORM 2.0 style reads are not auto-filtered by the
    before_compile listener at all, so no bypass is needed or available for them.
    RLS (Phase 5) is the security backstop for those paths.

Background scripts / migrations:
    Scripts run outside get_db_with_tenant_variables. Scope is unbound, auto-stamp is
    a no-op, and NOT-NULL constraints on organization_id will trip. Explicitly bind:
        from rhesis.backend.app.scope import RequestScope, bind_scope, reset_scope
        token = bind_scope(RequestScope(organization_id="...", user_id="..."))
        try:
            ...
        finally:
            reset_scope(token)

Bulk writes (Session.bulk_insert_mappings / bulk_save_objects):
    SQLAlchemy does NOT fire before_insert events for bulk operations. Auto-stamp does
    NOT apply. You MUST include organization_id / user_id / project_id in the payload.

TEST FIXTURES
-------------
tests/backend/conftest.py provides:
- isolate_request_scope (autouse): resets ContextVars to defaults per test
- bound_scope: helper fixture for tests that need to exercise the listeners directly
"""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RequestScope:
    """Immutable identity triple carried per-request via ContextVar."""

    organization_id: Optional[str] = None
    user_id: Optional[str] = None
    project_id: Optional[str] = None


# Identity scope - set once per request, never mutated mid-request.
_scope: ContextVar[RequestScope] = ContextVar("request_scope", default=RequestScope())

# Bypass flag - separate ContextVar, mirrors _soft_delete_disabled in database.py.
# Defaults False. Flipped by bypass_tenant_filter() context manager only.
# Identity and bypass are different concerns and live in different ContextVars.
_tenant_filter_disabled: ContextVar[bool] = ContextVar("tenant_filter_disabled", default=False)


def current_scope() -> RequestScope:
    """
    Return the ContextVar-bound RequestScope for the current context.

    Note: for DB-bound work the listeners prefer Session.info['_scope'] over this
    ContextVar (see module docstring). This returns the ContextVar value, which is
    only populated by explicit bind_scope() callers (scripts/tests), not by the
    normal FastAPI / Celery DB-session path.
    """
    return _scope.get()


def bind_scope(scope: RequestScope):
    """
    Bind a RequestScope to the ContextVar. Returns a token for reset_scope().

    For scripts and tests that need ambient scope WITHOUT a DB session. The normal
    request/Celery path does not use this — it stores scope on Session.info instead.
    """
    return _scope.set(scope)


def reset_scope(token) -> None:
    """Reset the scope ContextVar to its previous value using the token from bind_scope()."""
    _scope.reset(token)


def is_tenant_filter_disabled() -> bool:
    """Return True when auto-filter has been suppressed via bypass_tenant_filter()."""
    return _tenant_filter_disabled.get()


@contextmanager
def bypass_tenant_filter():
    """
    Disable the auto-filter for the duration of this block.

    Auto-stamp is NOT affected - inserts under bypass still receive the caller's identity.

    Mirrors without_soft_delete_filter() in app/database.py.

    Usage:
        with bypass_tenant_filter():
            all_orgs = db.query(SomeModel).all()  # not filtered by org/project
    """
    token = _tenant_filter_disabled.set(True)
    try:
        yield
    finally:
        _tenant_filter_disabled.reset(token)
