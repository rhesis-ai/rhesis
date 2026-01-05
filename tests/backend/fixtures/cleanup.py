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
    """Clean test database between tests while preserving session authentication data."""
    # Clean up BEFORE each test to ensure isolation
    try:
        with test_engine.connect() as connection:
            # Get session authentication data to preserve
            auth_org_id, auth_user_id, auth_token_value = get_session_auth_ids()

            # Get token ID if we have the token value
            auth_token_id = None
            if auth_token_value:
                try:
                    result = connection.execute(
                        text("""
                        SELECT id FROM token WHERE token = :token_value
                    """),
                        {"token_value": auth_token_value},
                    )
                    row = result.fetchone()
                    if row:
                        auth_token_id = str(row.id)
                        print(f"🔐 Found session token ID: {auth_token_id}")
                except Exception as e:
                    print(f"⚠️ Could not find token ID: {e}")

            print(
                f"🧹 Starting cleanup, preserving session auth: "
                f"org={auth_org_id}, user={auth_user_id}, token={auth_token_id}"
            )

            # OPTIMIZED CLEANUP: Use TRUNCATE CASCADE for speed
            # Only use DELETE for auth tables that need row preservation

            # Tables that can be TRUNCATEd (no auth data to preserve)
            # TRUNCATE is ~10-100x faster than DELETE
            tables_to_truncate = [
                # Telemetry tables (added for trace testing)
                "trace",  # OpenTelemetry spans/traces
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
                # Reference/lookup entities
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

            # Use single transaction for all TRUNCATE operations (much faster)
            try:
                with connection.begin():
                    # Disable triggers for faster truncate
                    connection.execute(text("SET session_replication_role = 'replica'"))

                    # TRUNCATE all test data tables at once
                    for table_name in tables_to_truncate:
                        try:
                            connection.execute(text(f"TRUNCATE TABLE {table_name} CASCADE"))
                        except Exception:
                            # Table might not exist or have constraints - continue
                            pass

                    # Re-enable triggers
                    connection.execute(text("SET session_replication_role = 'origin'"))

                    print(f"  🗑️ TRUNCATEd {len(tables_to_truncate)} tables")
            except Exception as e:
                print(f"  ⚠️ TRUNCATE failed: {e}, falling back to DELETE")

            # AUTH TABLES: Use DELETE with WHERE clause to preserve session auth
            auth_tables_to_clean = [
                ('"user"', auth_user_id, "users"),
                ("organization", auth_org_id, "organizations"),
                ("token", auth_token_id, "tokens"),
            ]

            for table_name, preserve_id, display_name in auth_tables_to_clean:
                if preserve_id:
                    try:
                        with connection.begin():
                            result = connection.execute(
                                text(f"DELETE FROM {table_name} WHERE id != :preserve_id"),
                                {"preserve_id": preserve_id},
                            )
                            if result.rowcount > 0:
                                print(
                                    f"  🗑️ Cleaned {result.rowcount} {display_name} "
                                    f"(preserved session auth)"
                                )
                    except Exception:
                        # Table might not exist - continue
                        pass

            print("✅ Optimized cleanup completed")

    except Exception as e:
        # If cleanup fails completely, continue - tests might still work
        print(f"Database cleanup failed: {e}")
        pass

    yield  # Test runs here

    # Post-test cleanup (if needed)
    # The main cleanup happens before each test, but we could add post-test cleanup here


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
