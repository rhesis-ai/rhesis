"""
🗄️ Database Fixtures Module

This module contains all database-related fixtures for testing, including:
- Database engine and session configuration
- Database setup and teardown
- Test database session management

Extracted from conftest.py for better modularity and maintainability.
"""

from contextlib import contextmanager
from uuid import UUID

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from rhesis.backend.app.database import get_database_url


@contextmanager
def _yield_shared_session(db):
    """A ``get_db()``-shaped context manager that just hands back ``db``.

    ``db``'s own fixture owns commit/rollback/close — this never touches
    either, so it's safe to substitute anywhere ``get_db()`` is called.
    """
    yield db


def patch_auth_get_db(monkeypatch, db):
    """Route the auth-resolution path's direct ``get_db()`` calls onto ``db``.

    ``get_current_user``/``get_user_from_jwt``/``get_authenticated_user_with_context``
    (``auth/user_utils.py``) call ``get_db()`` directly rather than through a
    FastAPI ``Depends`` parameter, so ``app.dependency_overrides`` never
    intercepts them — they'd otherwise always open a genuinely separate
    connection that can't see this session's writes (savepoint-scoped ones in
    particular, but even real ones without this patch would just be an
    unnecessary second connection). All three resolve ``get_db`` from the
    single module-level import in ``user_utils.py``, so one patch covers all
    three call sites. Applied here (not just in ``client``) because several
    tests call these auth functions directly against ``test_db``, without
    ever going through the ``client``/``TestClient`` fixture.
    """
    from rhesis.backend.app.auth import user_utils

    monkeypatch.setattr(user_utils, "get_db", lambda: _yield_shared_session(db))

# Test database configuration uses the same URL resolution as production.
DATABASE_URL = get_database_url()

# Create test engine with the same configuration as production
# but optimized for testing (smaller pool sizes)
test_engine = create_engine(
    DATABASE_URL,
    # Reduced pool settings for testing
    pool_size=5,  # Smaller than production (10)
    max_overflow=10,  # Smaller than production (20)
    pool_pre_ping=True,  # Same as production
    pool_recycle=3600,  # Same as production (1 hour)
    pool_timeout=10,  # Same as production
    # Same connection args as production
    connect_args={
        "connect_timeout": 10,  # Same as production
        "application_name": "rhesis-backend-test",  # Distinguish test connections
        "keepalives_idle": "300",  # Same as production
        "keepalives_interval": "10",  # Same as production
        "keepalives_count": "3",  # Same as production
        "tcp_user_timeout": "30000",  # Same as production
    },
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
    expire_on_commit=False,  # Same as production
)


@pytest.fixture(scope="session", autouse=True)
def setup_test_database(run_migrations_once):
    """Ensure DB schema is ready before tests.

    Depends on ``run_migrations_once`` so Alembic migrations always run first.
    No ``create_all`` / ``drop_all`` — Alembic is the single source of truth
    for the test-DB schema.
    """
    yield


def _validate_uuid(value: str, label: str) -> None:
    try:
        UUID(value)
    except (ValueError, TypeError):
        raise ValueError(f"Invalid {label}: {value}")


@pytest.fixture
def test_db(test_org_id, authenticated_user_id, monkeypatch):
    """🗄️ Provide a database session for testing, isolated via a SAVEPOINT.

    The whole test — including any ``db.commit()`` called by application code
    (routers/services/crud commit directly on the session ~62 times) — runs
    inside one outer transaction that is unconditionally rolled back at
    teardown. ``join_transaction_mode="create_savepoint"`` (SQLAlchemy 2.0+)
    makes every top-level SessionTransaction ride on a SAVEPOINT of that outer
    transaction instead of a real one, including the ones autobegun after a
    mid-test commit/rollback, so no custom event listener is needed.

    The RLS ``SET`` statements are issued on the raw ``connection`` *before*
    the session/first-savepoint exists. This matters: if they were issued via
    ``db.execute()`` after the session exists, they'd live inside the first
    savepoint, and any fixture/test that calls ``db.rollback()`` before the
    test's first commit (a few already do, e.g. the ``test_project`` fixture
    in ``tests/backend/utils/test_project_querybuilder.py``) would silently
    wipe the org/user GUCs for the rest of the test. Setting them on the
    connection's outer transaction means they survive any number of
    savepoint rollbacks/restarts.

    Note: this session only sees its own uncommitted writes plus whatever was
    truly committed before the test started (e.g. the shared session-auth
    org/user/token). Auth resolution in ``auth/user_utils.py`` calls
    ``get_db()`` directly rather than through FastAPI ``Depends``, but
    ``patch_auth_get_db`` (see below) points that at this same session, so
    authenticating as a brand-new user created mid-test (e.g. ``owner_client``)
    works fine here — no real commit needed. ``real_commit_test_db`` is only
    for code that opens a genuinely independent, unpatchable connection —
    e.g. a CLI entrypoint calling ``SessionLocal()`` directly.
    """
    from rhesis.backend.app.database import (
        _current_tenant_organization_id,
        _current_tenant_user_id,
        clear_tenant_context,
    )

    connection = test_engine.connect()
    outer_transaction = connection.begin()

    try:
        if test_org_id:
            _validate_uuid(test_org_id, "test_org_id")
            connection.execute(
                text('SET "app.current_organization" = :org_id'), {"org_id": test_org_id}
            )

        if authenticated_user_id:
            _validate_uuid(authenticated_user_id, "authenticated_user_id")
            connection.execute(
                text('SET "app.current_user" = :user_id'), {"user_id": authenticated_user_id}
            )

        _current_tenant_organization_id.set(test_org_id)
        if authenticated_user_id:
            _current_tenant_user_id.set(authenticated_user_id)

        db = TestingSessionLocal(bind=connection, join_transaction_mode="create_savepoint")
        patch_auth_get_db(monkeypatch, db)
        try:
            yield db
        finally:
            try:
                db.close()
            except Exception:
                pass

    finally:
        try:
            outer_transaction.rollback()
        except Exception:
            pass
        try:
            connection.close()
        except Exception:
            pass
        clear_tenant_context()


# Tables carrying an organization_id column, in FK-safe (children-first) order.
# Mirrors the table list the old blanket-TRUNCATE fixture used
# (tests/backend/fixtures/cleanup.py), but here it scopes a targeted DELETE to
# one organization_id rather than wiping every row in the table.
_ORG_SCOPED_TABLES = [
    "project_membership",
    "trace",
    "test_test_set",
    "prompt_test_set",
    "behavior_metric",
    "risk_use_case",
    "prompt_use_case",
    "tagged_item",
    "comment",
    "test_result",
    "test_run",
    "test_configuration",
    "test_context",
    "test",
    "prompt",
    "test_set",
    "prompt_template",
    "model",
    "task",
    "metric",
    "endpoint",
    "project",
    "response_pattern",
    "risk",
    "use_case",
    "source",
    "behavior",
    "category",
    "topic",
    "demographic",
    "dimension",
    "tag",
    "type_lookup",
    "status",
    "subscription",
    "organization_member",
    "token",
    '"user"',
]


def _hard_delete_organization(db, organization_id: str) -> None:
    """Best-effort targeted hard-delete of one organization and its rows.

    Most ``organization_id`` foreign keys in this schema are
    ``ON DELETE NO ACTION``, not ``CASCADE`` (confirmed via ``pg_constraint``:
    user/token/project/behavior/test/test_run/... are all ``NO ACTION``; only
    organization_member/project_membership/role cascade) — a plain
    ``DELETE FROM organization`` would fail with an FK violation as soon as any
    child row exists. This disables FK-trigger enforcement for the duration of
    the deletes, the same technique the old blanket-TRUNCATE fixture used,
    restricted to rows matching this one organization_id.
    """
    try:
        existing_tables = {
            row[0]
            for row in db.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public'"
                )
            )
        }
        managed_tables = [t for t in _ORG_SCOPED_TABLES if t.strip('"') in existing_tables]

        db.execute(text("SET session_replication_role = 'replica'"))
        try:
            for table in managed_tables:
                db.execute(
                    text(f"DELETE FROM {table} WHERE organization_id = :oid"),
                    {"oid": organization_id},
                )
            db.execute(text("DELETE FROM organization WHERE id = :oid"), {"oid": organization_id})
        finally:
            db.execute(text("SET session_replication_role = 'origin'"))
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"real_commit_test_db cleanup failed for org {organization_id}: {e}")


@pytest.fixture
def real_commit_test_db(test_org_id, authenticated_user_id, monkeypatch):
    """``test_db`` variant for tests needing genuinely cross-connection-visible commits.

    Unlike ``test_db``, commits here are real. Use this only when a separate
    connection must see this session's writes — e.g. auth resolution
    (``get_current_user``/``get_authenticated_user_with_context`` in
    ``auth/user_utils.py``) calls ``get_db()`` directly, bypassing
    ``app.dependency_overrides`` entirely, so it needs a freshly created token
    to be really committed to authenticate as that user.

    Teardown does targeted, per-organization cleanup (see
    ``_hard_delete_organization``) instead of a blanket TRUNCATE — tracked via
    ``db.info["_owned_org_ids"]``, which callers (e.g. ``owner_client``) append
    to after creating an org.
    """
    from rhesis.backend.app.database import (
        _current_tenant_organization_id,
        _current_tenant_user_id,
        clear_tenant_context,
    )

    db = TestingSessionLocal()
    db.info["_owned_org_ids"] = []

    try:
        if test_org_id:
            _validate_uuid(test_org_id, "test_org_id")
            db.execute(
                text('SET "app.current_organization" = :org_id'), {"org_id": test_org_id}
            )
        if authenticated_user_id:
            _validate_uuid(authenticated_user_id, "authenticated_user_id")
            db.execute(
                text('SET "app.current_user" = :user_id'), {"user_id": authenticated_user_id}
            )

        _current_tenant_organization_id.set(test_org_id)
        if authenticated_user_id:
            _current_tenant_user_id.set(authenticated_user_id)

        patch_auth_get_db(monkeypatch, db)
        yield db

    finally:
        try:
            if db.in_transaction():
                db.rollback()
        except Exception:
            pass

        for org_id in db.info.get("_owned_org_ids", []):
            _hard_delete_organization(db, org_id)

        clear_tenant_context()
        db.close()
