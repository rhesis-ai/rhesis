"""
🌐 Client Fixtures Module

This module contains FastAPI test client-related fixtures, including:
- Test client configuration
- Authenticated client setup
- Database dependency overrides

Extracted from conftest.py for better modularity and maintainability.
"""

import pytest
from fastapi.testclient import TestClient

from rhesis.backend.app.database import get_db
from rhesis.backend.app.dependencies import get_db_session, get_tenant_db_session
from rhesis.backend.app.main import app


@pytest.fixture
def client(test_db):
    """🌐 FastAPI test client with test database.

    ``test_db`` itself patches the auth-resolution path's direct ``get_db()``
    calls (see ``fixtures/database.py:patch_auth_get_db``) to share this same
    session, so requests made through this client see the session's writes
    consistently, including under savepoint isolation.
    """

    # Create override function that uses the same session as test fixtures
    def override_get_db():
        """Override the get_db dependency to use the same session as fixtures."""
        yield test_db

    # Override the database dependencies
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_db_session] = override_get_db
    app.dependency_overrides[get_tenant_db_session] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    # Clean up the override
    app.dependency_overrides.clear()


@pytest.fixture
def authenticated_client(client, rhesis_api_key):
    """🔑 FastAPI test client with authentication headers."""
    client.headers.update({"Authorization": f"Bearer {rhesis_api_key}"})
    return client


@pytest.fixture
def real_commit_client(real_commit_test_db):
    """🌐 FastAPI test client backed by ``real_commit_test_db``.

    Same DI-override wiring as ``client``, but bound to a session that really
    commits. Needed only by tests whose code under test opens a genuinely
    separate connection that no in-process patch can reach — e.g. a CLI
    entrypoint that calls ``SessionLocal()`` directly (see
    ``real_commit_test_db``'s docstring). The auth-resolution path itself no
    longer needs this split (``real_commit_test_db`` patches it too) — most
    tests should use ``owner_client``/``client`` rather than reach for this
    directly.
    """

    def override_get_db():
        yield real_commit_test_db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_db_session] = override_get_db
    app.dependency_overrides[get_tenant_db_session] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def owner_client(test_db, client):
    """🔑 FastAPI test client authenticated as a fresh org owner.

    Creates an independent org + user + token (separate from the shared
    ``authenticated_client`` org) and returns a client authenticated as that
    user.  The user is set as the org's ``owner_id``, matching real onboarding.
    """
    import uuid
    from datetime import datetime

    from tests.backend.fixtures.test_setup import create_test_organization_and_user

    # Create a fresh org owner for this test
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_suffix = str(uuid.uuid4())[:8]
    test_org_name = f"Owner Org {timestamp}_{session_suffix}"
    test_user_email = f"owner_{timestamp}_{session_suffix}@rhesis-test.com"
    test_user_name = "Test Org Owner"

    organization, user, token = create_test_organization_and_user(
        test_db, test_org_name, test_user_email, test_user_name
    )

    # No real commit needed: client's user_utils.get_db patch (see above)
    # means the auth-resolution path shares this same savepoint-scoped
    # session, so it sees the new token without a real commit.
    client.headers.update({"Authorization": f"Bearer {token.token}"})

    return client
