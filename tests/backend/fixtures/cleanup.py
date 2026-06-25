"""
🧹 Database Cleanup Fixtures Module

This module contains database cleanup logic for test isolation, including:
- Test database cleanup between tests
- Authentication data preservation
- Selective table cleanup with dependency ordering

Extracted from conftest.py for better modularity and maintainability.
"""

import pytest
from sqlalchemy import text

from .database import test_engine


def get_session_auth_ids():
    """Get session authentication IDs to preserve during cleanup."""
    import os

    from tests.backend.fixtures.auth import _session_auth_cache

    # First try to get from session cache
    if _session_auth_cache is not None:
        org_id, user_id, token_value = _session_auth_cache
        print(f"🔐 Found session auth cache: org={org_id}, user={user_id}")
        return org_id, user_id, token_value

    # Fallback: try to get from environment API key
    api_key = os.getenv("RHESIS_API_KEY")
    if api_key:
        from tests.backend.fixtures.auth import get_authenticated_user_info
        from tests.backend.fixtures.database import TestingSessionLocal

        session = TestingSessionLocal()
        try:
            org_id, user_id = get_authenticated_user_info(session)
            if org_id and user_id:
                print(f"🔐 Found auth from API key: org={org_id}, user={user_id}")
                return org_id, user_id, api_key
        except Exception as e:
            print(f"⚠️ Could not get auth from API key: {e}")
        finally:
            session.close()

    print("⚠️ No session auth found to preserve")
    return None, None, None


@pytest.fixture(autouse=True)
def clean_test_database():
    """Clean test database between tests while preserving session authentication data.

    SQLAlchemy 2.x uses "autobegin": the first SQL executed on a connection
    implicitly starts a transaction, so calling ``connection.begin()`` on that
    same connection raises::

        This connection has already initialized a SQLAlchemy Transaction()
        object via begin() or autobegin; can't call begin() here …

    The fix is to use ``engine.begin()`` instead of ``engine.connect()`` +
    nested ``connection.begin()``.  ``engine.begin()`` returns a connection
    that is already inside an explicit transaction, commits on exit and
    rolls back on exception.
    """
    auth_org_id, auth_user_id, auth_token_value = get_session_auth_ids()

    # Tables that contain only test data and can be TRUNCATEd each time.
    # Order matters when session_replication_role='replica' disables FK
    # cascade triggers: list referencing tables BEFORE referenced ones.
    tables_to_truncate = [
        # Membership / join tables (reference project, user)
        "project_membership",
        # Telemetry
        "trace",
        # Association tables
        "test_test_set",
        "prompt_test_set",
        "behavior_metric",
        "risk_use_case",
        "prompt_use_case",
        "tagged_item",
        # Dependent entities
        "comment",
        "test_result",
        "test_run",
        "test_configuration",
        "test_context",
        "test",
        # Content entities
        "prompt",
        "test_set",
        "prompt_template",
        "model",
        "task",
        "metric",
        "endpoint",
        "project",
        # Reference / lookup entities
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
    ]

    try:
        # engine.begin() opens a connection *and* starts an explicit transaction
        # in one step — no autobegin conflict.  Commits on clean exit; rolls
        # back on exception.
        with test_engine.begin() as connection:
            # Resolve the token row ID inside the same transaction so we can
            # preserve it in the DELETE-based auth-table cleanup below.
            auth_token_id = None
            if auth_token_value:
                try:
                    row = connection.execute(
                        text("SELECT id FROM token WHERE token = :tv"),
                        {"tv": auth_token_value},
                    ).fetchone()
                    if row:
                        auth_token_id = str(row.id)
                except Exception:
                    pass

            # Disable FK-cascade triggers so TRUNCATE doesn't need to chase
            # every FK edge.  Restored in the finally block below.
            connection.execute(text("SET session_replication_role = 'replica'"))
            try:
                for table_name in tables_to_truncate:
                    try:
                        connection.execute(text(f"TRUNCATE TABLE {table_name} CASCADE"))
                    except Exception:
                        # Table may not exist yet (schema drift) — keep going.
                        pass
            finally:
                # Always restore, even if a TRUNCATE raised; the SET is
                # session-scoped so it survives a transaction rollback.
                try:
                    connection.execute(text("SET session_replication_role = 'origin'"))
                except Exception:
                    pass

            # Auth tables: use DELETE (not TRUNCATE) so the session org / user /
            # token rows that the whole test run authenticates with are kept.
            auth_tables_to_clean = [
                ('"user"', auth_user_id),
                ("organization", auth_org_id),
                ("token", auth_token_id),
            ]
            for table_name, preserve_id in auth_tables_to_clean:
                if preserve_id:
                    try:
                        connection.execute(
                            text(f"DELETE FROM {table_name} WHERE id != :pid"),
                            {"pid": preserve_id},
                        )
                    except Exception:
                        pass

    except Exception as e:
        # Log but never fail the test — a partial cleanup is better than a
        # broken test run.
        print(f"Database cleanup failed: {e}")

    yield  # test runs here


@pytest.fixture(autouse=True)
def ensure_test_isolation():
    """
    🏝️ Ensure proper test isolation for session-scoped authentication.

    This fixture ensures that each test runs in a clean environment while
    preserving session authentication data for performance.
    """
    # Pre-test: Reset any test-specific state
    yield

    # Post-test: Clean up any test-specific modifications
    # This runs after each test to ensure no state leaks between tests
    try:
        from rhesis.backend.app.database import clear_tenant_context

        clear_tenant_context()
    except Exception:
        # If tenant context clearing fails, continue
        pass
