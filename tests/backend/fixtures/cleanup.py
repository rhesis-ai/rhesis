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
    from tests.backend.fixtures.auth import _session_auth_cache
    import os

    # First try to get from session cache
    if _session_auth_cache is not None:
        org_id, user_id, token_value = _session_auth_cache
        print(f"🔐 Found session auth cache: org={org_id}, user={user_id}")
        return org_id, user_id, token_value

    # Fallback: try to get from environment API key
    api_key = os.getenv("RHESIS_API_KEY")
    if api_key:
        from tests.backend.fixtures.database import TestingSessionLocal
        from tests.backend.fixtures.auth import get_authenticated_user_info

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
                f"🧹 Starting cleanup, preserving session auth: org={auth_org_id}, user={auth_user_id}, token={auth_token_id}"
            )

            # List of tables to clean (in correct dependency order - most dependent first)
            # Clean ALL test data but preserve ONLY core authentication data (tokens, users, organization)
            tables_to_clean = [
                # Level 1: Association tables (no dependencies, just references)
                "test_test_set",  # test.id + test_set.id
                "prompt_test_set",  # prompt.id + test_set.id
                "behavior_metric",  # behavior.id + metric.id
                "risk_use_case",  # risk.id + use_case.id
                "prompt_use_case",  # prompt.id + use_case.id
                "tagged_item",  # tag.id + entity polymorphic
                # Level 2: Highly dependent entities (reference many other tables)
                "comment",  # -> user, organization (polymorphic entity refs)
                "test_result",  # -> test_configuration, test_run, prompt, test, status, user, organization
                # Level 3: Execution/runtime entities
                "test_run",  # -> user, status, test_configuration, organization
                "test_configuration",  # -> endpoint, category, topic, prompt, use_case, test_set, user, status, organization
                # Level 4: Test entities
                "test_context",  # -> test, organization, user
                "test",  # -> prompt, type_lookup, user(3x), topic, behavior, category, status, organization
                # Level 5: Content entities
                "prompt",  # -> demographic, category(2x), topic, behavior, prompt, prompt_template, source, user, status
                "test_set",  # -> status, type_lookup, user(3x), organization
                "prompt_template",  # -> user, organization
                "model",  # -> user(2x), organization
                "task",  # -> user(2x), status, type_lookup, organization
                "metric",  # -> user(2x), organization
                "endpoint",  # -> user, organization
                "project",  # -> user(2x), status, organization
                # Level 6: Reference/lookup entities (clean everything - no preservation)
                "response_pattern",  # -> organization
                "risk",  # -> organization, user
                "use_case",  # -> organization, user
                "source",  # -> organization
                "behavior",  # -> organization, user
                "category",  # -> organization, user
                "topic",  # -> organization, user
                "demographic",  # -> dimension, organization, user
                "dimension",  # -> organization, user
                "tag",  # -> (referenced by tagged_item)
                "type_lookup",  # -> organization, user
                "status",  # -> organization, user
                # Level 7: User-related tables (clean everything except auth tokens)
                "subscription",  # -> user, organization (CLEAN ALL)
                # Level 8: Core authentication tables (preserve ONLY auth user/org/tokens)
                "token",  # -> user, organization (PRESERVE AUTH TOKENS ONLY)
                "organization",  # -> user(2x) [owner_id, user_id] (PRESERVE AUTH ORG ONLY)
                '"user"',  # -> organization [organization_id] (PRESERVE AUTH USER ONLY)
            ]

            # Clean each table in its own transaction to prevent cascading failures
            for table_name in tables_to_clean:
                try:
                    with connection.begin():
                        if table_name == '"user"' and auth_user_id:
                            # Preserve session auth user only
                            result = connection.execute(
                                text(f"DELETE FROM {table_name} WHERE id != :auth_user_id"),
                                {"auth_user_id": auth_user_id},
                            )
                            if result.rowcount > 0:
                                print(
                                    f"  🗑️ Cleaned {result.rowcount} users (preserved session auth user)"
                                )
                        elif table_name == "organization" and auth_org_id:
                            # Preserve session auth organization only
                            result = connection.execute(
                                text(f"DELETE FROM {table_name} WHERE id != :auth_org_id"),
                                {"auth_org_id": auth_org_id},
                            )
                            if result.rowcount > 0:
                                print(
                                    f"  🗑️ Cleaned {result.rowcount} organizations (preserved session auth org)"
                                )
                        elif table_name == "token" and auth_token_id:
                            # Preserve session auth token only
                            result = connection.execute(
                                text(f"DELETE FROM {table_name} WHERE id != :auth_token_id"),
                                {"auth_token_id": auth_token_id},
                            )
                            if result.rowcount > 0:
                                print(
                                    f"  🗑️ Cleaned {result.rowcount} tokens (preserved session auth token)"
                                )
                        elif table_name == "subscription":
                            # Clean ALL subscriptions (no preservation needed)
                            result = connection.execute(text(f"DELETE FROM {table_name}"))
                            if result.rowcount > 0:
                                print(f"  🗑️ Cleaned {result.rowcount} subscriptions")
                        else:
                            # For all other tables, clean everything (test data isolation)
                            result = connection.execute(text(f"DELETE FROM {table_name}"))
                            if result.rowcount > 0:
                                print(f"  🗑️ Cleaned {result.rowcount} rows from {table_name}")

                except Exception as e:
                    # If cleanup fails for a table, continue with others
                    # This is expected for tables that don't exist or have complex constraints
                    pass

            print(f"✅ Selective cleanup completed")

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
