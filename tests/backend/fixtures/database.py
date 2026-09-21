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

from rhesis.backend.app.config.settings import get_database_settings
from rhesis.backend.app.database import get_database_url

_db_settings = get_database_settings()


@contextmanager
def _yield_fresh_session(db):
    """A ``get_db()``-shaped context manager, but with a fresh ``Session`` per call.

    Mirrors production's real ``get_db()``: commits on success, rolls back on
    exception, always closes. Bound to ``db``'s own connection/savepoint so it
    still sees ``db``'s writes -- but with its own empty identity map, so it
    can't serve a stale cached row for something another session (e.g. an
    HTTP request handled via ``fixtures/client.py``'s ``override_get_db``)
    committed after this session last read it.

    Copies ``db.info`` (as ``override_get_db`` does) so ambient scope set via
    ``db.info["_scope"]`` still applies -- otherwise auth functions called
    directly against this session would silently lose project/org scoping.
    """
    session = TestingSessionLocal(bind=db.get_bind(), join_transaction_mode="create_savepoint")
    session.info.update(db.info)
    try:
        yield session
        if session.in_transaction():
            session.commit()
    except Exception:
        if session.in_transaction():
            session.rollback()
        raise
    finally:
        session.close()


def patch_auth_get_db(monkeypatch, db):
    """Route the auth-resolution path's direct ``get_db()`` calls onto ``db``'s connection.

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

    monkeypatch.setattr(user_utils, "get_db", lambda: _yield_fresh_session(db))

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

_CONNECT_ARGS = {
    "connect_timeout": 10,
    "application_name": "rhesis-backend-test-admin",
    "keepalives_idle": "300",
    "keepalives_interval": "10",
    "keepalives_count": "3",
    "tcp_user_timeout": "30000",
}

admin_engine = create_engine(
    _db_settings.admin_url,
    pool_size=2,
    max_overflow=3,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_timeout=10,
    connect_args=_CONNECT_ARGS,
)

AdminSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=admin_engine,
    expire_on_commit=False,
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
        _SET_CONFIG_SQL,
        _TENANT_VARS_KEY,
        _current_tenant_organization_id,
        _current_tenant_user_id,
        clear_tenant_context,
    )
    from tests.backend.fixtures.rls import TEST_GUC_KEY as _TEST_GUC_KEY

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

        # Store the test GUC params under a private key (NOT _SCOPE_KEY,
        # which would activate the ORM auto-filter/auto-stamp listeners).
        _test_params = {
            "org_id": test_org_id or "",
            "user_id": authenticated_user_id or "",
            "project_id": "",
        }
        db.info[_TEST_GUC_KEY] = _test_params
        # Also store under _TENANT_VARS_KEY so _reapply_tenant_vars can
        # restore GUCs on handler sessions after a handler (e.g.
        # temporary_project_scope cleanup) blanks them with SET LOCAL.
        db.info[_TENANT_VARS_KEY] = dict(_test_params)

        # Patch create_organization to re-apply the test GUCs after it
        # returns. create_organization calls reset_session_context to blank
        # GUCs (the org INSERT needs the policy passthrough), but then
        # leaves them blank — subsequent queries on tables with strict
        # tenant_isolation crash on ''::uuid.
        from rhesis.backend.app.crud import organization as _org_crud_mod
        _original_create = _org_crud_mod.create_organization

        _fixture_db = db

        def _test_create_organization(db, organization, owner_user_id=None):
            result = _original_create(db, organization, owner_user_id)
            # reset_session_context inside _original_create blanked the GUCs
            # with set_config(..., is_local=true). That '' persists after
            # RELEASE SAVEPOINT, which is fine for the org table (its policy
            # treats '' as "no scope") — BUT any subsequent code in the SAME
            # session that touches a table with strict tenant_isolation
            # crashes on ''::uuid (e.g. _sync_project_roles_from_org_role
            # during user-creation in auth fixtures).
            #
            # Only re-apply on the test fixture session. HTTP handler
            # sessions must NOT get the test GUCs re-applied: the LOCAL
            # set_config persists after the handler's savepoint is released,
            # and setting it to test_org_id would hide any newly created org
            # from subsequent reads (the org policy's USING clause compares
            # id = GUC::uuid).
            if db is _fixture_db:
                db.execute(_SET_CONFIG_SQL, _test_params)
                # reset_session_context also stored empty strings under
                # _TENANT_VARS_KEY. Handler sessions (override_get_db) copy
                # test_db.info and _reapply_tenant_vars reads that key, so
                # leaving it blank would override the connection-level SET.
                if _TENANT_VARS_KEY in db.info:
                    db.info[_TENANT_VARS_KEY].update(_test_params)
            return result

        monkeypatch.setattr(_org_crud_mod, "create_organization", _test_create_organization)

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


@pytest.fixture
def admin_test_db(test_org_id, authenticated_user_id, monkeypatch):
    """Like ``test_db`` but connects as the superuser admin role.

    For tests that run DDL or other operations requiring table-owner /
    superuser privileges (e.g. migration tests that call ``ALTER TABLE``).
    Still savepoint-isolated and rolls back at teardown.
    """
    from rhesis.backend.app.database import (
        _current_tenant_organization_id,
        _current_tenant_user_id,
        clear_tenant_context,
    )

    connection = admin_engine.connect()
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

        db = AdminSessionLocal(bind=connection, join_transaction_mode="create_savepoint")
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
    "requirement_metric",
    "tagged_item",
    "comment",
    "test_result",
    "test_run",
    "test_configuration",
    "test",
    "prompt",
    "test_set",
    "prompt_template",
    "model",
    "task",
    "metric",
    "endpoint",
    "project",
    "source",
    "requirement",
    "category",
    "topic",
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
    user/token/project/requirement/test/test_run/... are all ``NO ACTION``; only
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
        for table in managed_tables:
            db.execute(
                text(f"DELETE FROM {table} WHERE organization_id = :oid"),
                {"oid": organization_id},
            )
        db.execute(text("DELETE FROM organization WHERE id = :oid"), {"oid": organization_id})
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"real_commit_test_db cleanup failed for org {organization_id}: {e}")
    finally:
        # session_replication_role is session-scoped, not transaction-scoped —
        # a rollback above does NOT reset it. Restore it in its own try/except,
        # after any rollback has already cleared an aborted transaction (a
        # failed DELETE above would otherwise make this very statement fail
        # too, leaving the pooled connection stuck in 'replica' — silently
        # disabling FK enforcement for whichever later test reuses it).
        try:
            db.execute(text("SET session_replication_role = 'origin'"))
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"real_commit_test_db: failed to reset session_replication_role: {e}")


def _hard_delete_user(db, user_id: str) -> None:
    """Best-effort targeted hard-delete of one leaked user row and its dependents.

    Companion to ``_hard_delete_organization`` for ``real_commit_test_db``
    tests that commit a *user* into the existing shared session-auth org
    (rather than creating a whole new org) — those rows aren't covered by
    ``_owned_org_ids`` cleanup and would otherwise persist for the rest of
    the worker's test session. Same FK-trigger-disabling technique, but
    scoped by ``user_id`` across every table that has one (queried live
    rather than hardcoded, since "who did this" ``user_id`` columns are far
    more widespread across the schema than ``organization_id`` ones).
    """
    try:
        user_scoped_tables = {
            row[0]
            for row in db.execute(
                text(
                    "SELECT c.table_name FROM information_schema.columns c "
                    "JOIN information_schema.tables t "
                    "ON t.table_schema = c.table_schema AND t.table_name = c.table_name "
                    "WHERE c.table_schema = 'public' AND c.column_name = 'user_id' "
                    "AND t.table_type = 'BASE TABLE'"
                )
            )
        }

        db.execute(text("SET session_replication_role = 'replica'"))
        for table in user_scoped_tables:
            db.execute(text(f'DELETE FROM "{table}" WHERE user_id = :uid'), {"uid": user_id})
        db.execute(text('DELETE FROM "user" WHERE id = :uid'), {"uid": user_id})
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"real_commit_test_db cleanup failed for user {user_id}: {e}")
    finally:
        try:
            db.execute(text("SET session_replication_role = 'origin'"))
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"real_commit_test_db: failed to reset session_replication_role: {e}")


@pytest.fixture
def real_commit_test_db(test_org_id, authenticated_user_id, monkeypatch):
    """``test_db`` variant for tests needing genuinely cross-connection-visible commits.

    Unlike ``test_db``, commits here are real. Use this only when a separate
    connection must see this session's writes — e.g. auth resolution
    (``get_current_user``/``get_authenticated_user_with_context`` in
    ``auth/user_utils.py``) calls ``get_db()`` directly, bypassing
    ``app.dependency_overrides`` entirely, so it needs a freshly created token
    to be really committed to authenticate as that user.

    Teardown does targeted cleanup instead of a blanket TRUNCATE, tracked via
    two lists on ``db.info``: ``"_owned_org_ids"`` (see
    ``_hard_delete_organization``) for callers that create a whole new org
    (e.g. ``owner_client``), and ``"_owned_user_ids"`` (see
    ``_hard_delete_user``) for callers that instead commit a user into the
    existing shared session-auth org.
    """
    from rhesis.backend.app.database import (
        _current_tenant_organization_id,
        _current_tenant_user_id,
        clear_tenant_context,
    )

    db = TestingSessionLocal()
    db.info["_owned_org_ids"] = []
    db.info["_owned_user_ids"] = []

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

        owned_orgs = db.info.get("_owned_org_ids", [])
        owned_users = db.info.get("_owned_user_ids", [])
        db.close()

        if owned_orgs or owned_users:
            admin_db = AdminSessionLocal()
            try:
                for org_id in owned_orgs:
                    _hard_delete_organization(admin_db, org_id)
                for user_id in owned_users:
                    _hard_delete_user(admin_db, user_id)
            finally:
                admin_db.close()

        clear_tenant_context()
