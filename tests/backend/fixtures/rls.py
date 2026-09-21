"""Tenant scoping helpers for tests running under enforced RLS.

Backend tests run as a non-BYPASSRLS role, so Postgres RLS policies apply the
same way they do in production (issue #2525). Two consequences drive every
caller of this module:

``INSERT ... RETURNING`` evaluates the policy's USING clause, not only
WITH CHECK, because RETURNING reads the new row back. So the session's org GUC
has to match a row *before* it is flushed. Scoping after the flush is too late
and surfaces as "new row violates row-level security policy".

The HTTP test client builds a fresh session per request and copies
``test_db.info`` into it, reading its GUCs from ``_TENANT_VARS_KEY``. Writing
that key is what makes the *next* request act as the given org or project.

Two info keys look interchangeable but are not, and conflating them breaks
tests in ways that are hard to trace:

``_tenant_vars``   the live scope. Handler sessions re-apply it at the start of
                   every transaction. This is what these helpers write.
``_test_gucs``     the restore *baseline*, owned by the ``test_db`` fixture. Its
                   ``create_organization`` patch re-applies it after that
                   function blanks the GUCs. Scoping must not move it, or a
                   later create silently restores the wrong org.
"""

from contextlib import contextmanager
from typing import Any, Iterator, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from rhesis.backend.app.database import _TENANT_VARS_KEY

# Imported by the test_db fixture in tests/backend/fixtures/database.py rather
# than redefined there.
TEST_GUC_KEY = "_test_gucs"


def scope_to_org(db: Session, organization_id: Optional[Any]) -> None:
    """Scope this session, and later HTTP requests, to one organization.

    Call before flushing rows that belong to ``organization_id``.
    """
    _apply(db, "app.current_organization", "org_id", organization_id)


def scope_to_project(db: Session, project_id: Optional[Any]) -> None:
    """Scope this session, and later HTTP requests, to one project."""
    _apply(db, "app.current_project", "project_id", project_id)


def scope_session_to_org(db: Session, organization_id: Optional[Any]) -> None:
    """Session-level org scope, for sessions whose commits are real.

    ``scope_to_org`` sets the GUC transaction-locally. That is right for
    ``test_db``, which re-applies it from ``_tenant_vars`` after every commit.
    ``real_commit_test_db`` commits for real and has no such restore, so a
    transaction-local GUC is gone after its first commit. A plain ``SET``
    persists for the connection instead.
    """
    _apply_session(db, '"app.current_organization"', organization_id)


def scope_session_to_project(db: Session, project_id: Optional[Any]) -> None:
    """Session-level project scope. See ``scope_session_to_org``."""
    _apply_session(db, '"app.current_project"', project_id)


@contextmanager
def as_org(db: Session, organization_id: Optional[Any]) -> Iterator[None]:
    """Scope to an organization for the block, then restore the previous scope.

    For the common cross-tenant shape: write or read a foreign org's rows, then
    go back. Leaving the session parked on another org makes later work in the
    test fail in ways that do not point at the cause.
    """
    with _restoring(db, "app.current_organization", "org_id"):
        scope_to_org(db, organization_id)
        yield


@contextmanager
def as_project(db: Session, project_id: Optional[Any]) -> Iterator[None]:
    """Scope to a project for the block, then restore. See ``as_org``."""
    with _restoring(db, "app.current_project", "project_id"):
        scope_to_project(db, project_id)
        yield


@contextmanager
def _restoring(db: Session, guc: str, info_key: str) -> Iterator[None]:
    previous = db.execute(text("SELECT current_setting(:guc, true)"), {"guc": guc}).scalar()
    try:
        yield
    finally:
        _apply(db, guc, info_key, previous)


def _apply(db: Session, guc: str, info_key: str, value: Optional[Any]) -> None:
    value = "" if value is None else str(value)
    db.execute(text("SELECT set_config(:guc, :value, true)"), {"guc": guc, "value": value})
    if _TENANT_VARS_KEY in db.info:
        db.info[_TENANT_VARS_KEY][info_key] = value


def _apply_session(db: Session, quoted_guc: str, value: Optional[Any]) -> None:
    # SET takes the setting name as syntax, not a bind parameter, so the name
    # is interpolated. Callers pass only the two literals above, never input.
    value = "" if value is None else str(value)
    db.execute(text(f"SET {quoted_guc} = :value"), {"value": value})
