"""
🔑 Authentication Fixtures Module

This module contains authentication-related fixtures for testing, including:
- Session-scoped user authentication and organization setup
- API key management with environment detection
- Optimized authentication fixtures for fast test execution

Extracted from conftest.py for better modularity and maintainability.
"""

import os
import uuid
from datetime import datetime
from typing import Optional, Tuple

import pytest

from .database import TestingSessionLocal

# Global session authentication cache
_session_auth_cache: Optional[Tuple[str, str, str]] = None  # (org_id, user_id, token)


def get_authenticated_user_info(db) -> tuple[str | None, str | None]:
    """
    Retrieve the authenticated user and organization IDs from the API key.

    Args:
        db: Database session

    Returns:
        Tuple of (organization_id, user_id) as strings, or (None, None) if not found
    """
    try:
        from rhesis.backend.app import crud
    except ImportError:
        return None, None

    api_key = os.getenv("RHESIS_API_KEY")
    if not api_key:
        return None, None

    try:
        # Get token from database using the API key value
        token = crud.get_token_by_value(db, api_key)
        if not token:
            return None, None

        # Get user from the token's user_id
        user = crud.get_user_by_id(db, token.user_id)
        if not user:
            return None, None

        return str(user.organization_id), str(user.id)

    except Exception as e:
        print(f"⚠️ Warning: Could not retrieve authenticated user info: {e}")
        return None, None


def create_session_authentication() -> Tuple[str, str, str]:
    """
    Create session-scoped authentication data (user, organization, token).
    This is called only once per test session.

    Returns:
        Tuple of (organization_id, user_id, token_value) as strings
    """
    global _session_auth_cache

    if _session_auth_cache is not None:
        print(
            f"🔄 Using cached session auth: org={_session_auth_cache[0]}, user={_session_auth_cache[1]}"
        )
        return _session_auth_cache

    from tests.backend.fixtures.test_setup import create_test_organization_and_user

    # Create a temporary database session
    session = TestingSessionLocal()
    try:
        # Generate unique names for this session
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_suffix = str(uuid.uuid4())[:8]
        test_org_name = f"Test Session Org {timestamp}_{session_suffix}"
        test_user_email = f"session_{timestamp}_{session_suffix}@rhesis-test.com"
        test_user_name = "Test Session User"

        # Create session auth data
        organization, user, token = create_test_organization_and_user(
            session, test_org_name, test_user_email, test_user_name
        )

        # Commit the session to make the organization and user available to other sessions
        session.commit()

        # Cache the session auth data
        _session_auth_cache = (str(organization.id), str(user.id), token.token)

        # Set the token in environment for all tests to use
        os.environ["RHESIS_API_KEY"] = token.token

        print(f"🆕 Created session auth data: user={user.id}, org={organization.id}")
        print(f"🔑 Set RHESIS_API_KEY for session: {token.token[:3]}...{token.token[-4:]}")

        return _session_auth_cache

    except Exception as e:
        print(f"❌ Failed to create session auth data: {e}")
        raise RuntimeError(f"Could not create session authentication data: {e}")
    finally:
        session.close()


def get_or_create_session_auth() -> Tuple[str, str, str]:
    """
    Get existing session auth or create new one.
    Checks for RHESIS_API_KEY environment variable first.

    Returns:
        Tuple of (organization_id, user_id, token_value) as strings
    """
    # First check if we have an environment API key
    api_key = os.getenv("RHESIS_API_KEY")
    if api_key:
        print(f"🔍 Found RHESIS_API_KEY in environment: {api_key[:3]}...{api_key[-4:]}")

        # Try to get user info from this API key
        session = TestingSessionLocal()
        try:
            org_id, user_id = get_authenticated_user_info(session)
            if org_id and user_id:
                print(f"✅ Using existing API key auth: org={org_id}, user={user_id}")
                return org_id, user_id, api_key
            else:
                print("⚠️ API key found but could not retrieve user info, creating new session auth")
        except Exception as e:
            print(f"⚠️ Error validating API key: {e}, creating new session auth")
        finally:
            session.close()

    # No valid environment API key, create session auth
    print("🔧 No valid RHESIS_API_KEY detected, creating session authentication")
    return create_session_authentication()


@pytest.fixture(scope="session")
def session_auth_data() -> Tuple[str, str, str]:
    """
    🔑 Session-scoped authentication data (organization_id, user_id, token)

    This fixture creates authentication data once per test session for optimal performance.
    It first checks for RHESIS_API_KEY environment variable, and if not found,
    creates fresh test authentication data.

    Returns:
        Tuple of (organization_id, user_id, token_value) as strings
    """
    return get_or_create_session_auth()


@pytest.fixture
def rhesis_api_key(session_auth_data):
    """🔑 API key from session authentication"""
    _, _, token = session_auth_data
    masked_key = f"{token[:3]}...{token[-4:]}" if token else None
    print(f"🔍 Using session API key: {masked_key}")
    return token


@pytest.fixture(scope="session")
def authenticated_user_info(session_auth_data) -> tuple[str, str]:
    """
    🔑 Session-scoped user and organization info

    This fixture provides the same user/organization throughout the test session
    for optimal performance while maintaining test isolation through proper cleanup.

    Returns:
        Tuple of (organization_id, user_id) as strings
    """
    org_id, user_id, _ = session_auth_data
    print(f"🔄 Using session auth: org={org_id}, user={user_id}")
    return org_id, user_id


@pytest.fixture(scope="session")
def test_org_id(authenticated_user_info) -> str:
    """🏢 Get the session organization ID"""
    org_id, _ = authenticated_user_info
    return org_id


@pytest.fixture(scope="session")
def authenticated_user_id(authenticated_user_info) -> str:
    """👤 Get the session authenticated user ID"""
    _, user_id = authenticated_user_info
    return user_id


@pytest.fixture
def test_entity_type(test_db, test_org_id, authenticated_user_id):
    """Create a test EntityType TypeLookup for testing Status relationships."""
    from rhesis.backend.app import models
    from rhesis.backend.app.constants import EntityType

    # Create a TypeLookup for EntityType.TEST
    entity_type = models.TypeLookup(
        type_name="EntityType",
        type_value=EntityType.TEST.value,
        organization_id=test_org_id,
        user_id=authenticated_user_id,
    )
    test_db.add(entity_type)
    test_db.commit()
    test_db.refresh(entity_type)
    return entity_type


@pytest.fixture
def project_entity_type(test_db, test_org_id, authenticated_user_id):
    """Create a project EntityType TypeLookup for testing Project Status relationships."""
    from rhesis.backend.app import models
    from rhesis.backend.app.constants import EntityType

    # Create a TypeLookup for EntityType.PROJECT
    entity_type = models.TypeLookup(
        type_name="EntityType",
        type_value=EntityType.PROJECT.value,
        organization_id=test_org_id,
        user_id=authenticated_user_id,
    )
    test_db.add(entity_type)
    test_db.commit()
    test_db.refresh(entity_type)
    return entity_type


@pytest.fixture
def secondary_org_id(test_db):
    """🏢 Secondary organization ID for multi-org testing."""
    import uuid
    from datetime import datetime

    from tests.backend.fixtures.test_setup import create_test_organization_and_user

    # Create a secondary organization
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_suffix = str(uuid.uuid4())[:8]
    test_org_name = f"Secondary Org {timestamp}_{session_suffix}"
    test_user_email = f"secondary_{timestamp}_{session_suffix}@rhesis-test.com"
    test_user_name = "Test Secondary User"

    organization, user, token = create_test_organization_and_user(
        test_db, test_org_name, test_user_email, test_user_name
    )

    return str(organization.id)
