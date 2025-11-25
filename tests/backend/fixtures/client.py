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

from rhesis.backend.app.main import app
from rhesis.backend.app.database import get_db
from rhesis.backend.app.dependencies import get_tenant_db_session


@pytest.fixture
def client(test_db):
    """🌐 FastAPI test client with test database."""

    # Create override function that uses the same session as test fixtures
    def override_get_db():
        """Override the get_db dependency to use the same session as fixtures."""
        yield test_db

    # Override the database dependencies
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_tenant_db_session] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    # Clean up the override
    app.dependency_overrides.clear()


@pytest.fixture
def authenticated_client(client, rhesis_api_key):
    """🔑 FastAPI test client with authentication headers."""
    masked_key = f"{rhesis_api_key[:3]}...{rhesis_api_key[-4:]}" if rhesis_api_key else None
    print(f"🔍 DEBUG: Setting Authorization header with API key: {masked_key}")
    client.headers.update({"Authorization": f"Bearer {rhesis_api_key}"})
    # Mask the authorization header in debug output
    headers_debug = dict(client.headers)
    if "authorization" in headers_debug:
        headers_debug["authorization"] = "***"
    print(f"🔍 DEBUG: Client headers now include: {headers_debug}")
    return client


@pytest.fixture
def superuser_client(test_db, client):
    """🔑 FastAPI test client with superuser authentication."""
    from rhesis.backend.app import models
    from tests.backend.fixtures.test_setup import create_test_organization_and_user
    from datetime import datetime
    import uuid

    # Create a superuser
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_suffix = str(uuid.uuid4())[:8]
    test_org_name = f"Superuser Org {timestamp}_{session_suffix}"
    test_user_email = f"superuser_{timestamp}_{session_suffix}@rhesis-test.com"
    test_user_name = "Test Superuser"

    organization, user, token = create_test_organization_and_user(
        test_db, test_org_name, test_user_email, test_user_name
    )

    # Make the user a superuser
    user.is_superuser = True
    test_db.commit()
    test_db.refresh(user)

    # Set auth header
    client.headers.update({"Authorization": f"Bearer {token.token}"})

    return client
