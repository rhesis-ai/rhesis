"""
Ambient Request Scope for automatic tenant filtering and stamping.

WHY THIS EXISTS
---------------
Rather than threading (organization_id, user_id, project_id) through every router,
service, CRUD helper, and Celery task, we bind this identity triple once per request
into a ContextVar. Two SQLAlchemy event listeners in models/scope_events.py read it:

- auto_filter: adds WHERE organization_id=... (and project_id=...) to every SELECT
- auto_stamp:  fills organization_id / user_id / project_id on INSERT when None

HOW TO USE
----------
Normal flow (FastAPI):
    The scope is bound automatically by get_db_with_tenant_variables() in database.py.
    Nothing extra to do in routers or CRUD.

Normal flow (Celery):
    BaseTask.get_db_session() routes through get_db_with_tenant_variables(), so scope
    is bound for the lifetime of the task's DB session.

Admin / cross-org reads:
    with bypass_tenant_filter():
        results = db.query(SomeModel).all()   # filter skipped
    Auto-stamp is NOT affected by bypass - inserts still get the caller's identity.

Per-query bypass:
    # Legacy Query API:
    query._bypass_scope = True
    # Modern select() API:
    db.execute(stmt, execution_options={"bypass_scope": True})

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
    """Return the active RequestScope for the current async context."""
    return _scope.get()


def bind_scope(scope: RequestScope):
    """
    Bind a RequestScope to the current context. Returns a token for reset_scope().

    Called once by get_db_with_tenant_variables(); also callable in tests and scripts.
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
