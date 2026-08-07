"""
🧹 Database Cleanup Fixtures Module

Per-test database isolation is now handled by the ``test_db``/
``real_commit_test_db`` fixtures in ``database.py`` (SAVEPOINT rollback for
the former, targeted per-organization delete for the latter) — see their
docstrings. This module only holds the lightweight tenant-context reset that
runs regardless of which DB fixture (if any) a test used.
"""

import pytest


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
