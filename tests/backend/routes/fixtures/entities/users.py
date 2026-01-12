"""
User Fixtures (Enhanced Factory-Based System)

This module provides clean, purpose-driven user fixtures with clear naming
and automatic cleanup. Replaces the old confusing mix of user fixture types.

Usage Guidelines:
- Use mock_* fixtures for unit tests (no database)
- Use db_* fixtures for integration tests (real database entities)
- Use authenticated_* fixtures when you need the actual authenticated user

Categories:
🎭 Mock Fixtures: Fast, no database interaction
🗄️ Database Fixtures: Real entities in test database
🔑 Authenticated Fixtures: The actual authenticated user from API key
"""

from typing import Any, Dict
from unittest.mock import Mock

import pytest
from faker import Faker

# Import models (adjust path as needed)
try:
    from rhesis.backend.app import crud
    from rhesis.backend.app.models.organization import Organization
    from rhesis.backend.app.models.user import User
except ImportError:
    # Fallback for tests that don't need real models
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from rhesis.backend.app.models.organization import Organization
        from rhesis.backend.app.models.user import User
    else:
        User = None
        Organization = None
    crud = None

fake = Faker()


# Dynamic authentication fixtures are now in conftest.py


# === 🎭 MOCK FIXTURES (Unit Tests - No Database) ===


@pytest.fixture
def mock_user_data() -> Dict[str, Any]:
    """
    Mock user data for unit tests

    Fast fixture that provides user data without database interaction.
    Perfect for unit tests that need user data but don't interact with the database.

    Returns:
        Dict containing mock user data
    """
    return {
        "id": fake.uuid4(),
        "email": fake.email(),
        "name": fake.name(),
        "given_name": fake.first_name(),
        "family_name": fake.last_name(),
        "is_active": True,
        "is_superuser": False,
        "organization_id": fake.uuid4(),
        "display_name": fake.name(),
    }


@pytest.fixture
def mock_admin_data(mock_user_data) -> Dict[str, Any]:
    """
    🎭👨‍💼 Mock admin user data for unit tests

    Returns:
        Dict containing mock admin user data
    """
    admin_data = mock_user_data.copy()
    admin_data.update(
        {
            "email": f"admin+{fake.uuid4()[:8]}@example.com",
            "name": f"Admin {fake.last_name()}",
            "given_name": "Admin",
            "is_superuser": True,
        }
    )
    return admin_data


@pytest.fixture
def mock_inactive_user_data(mock_user_data) -> Dict[str, Any]:
    """
    🎭🚫 Mock inactive user data for unit tests

    Returns:
        Dict containing mock inactive user data
    """
    inactive_data = mock_user_data.copy()
    inactive_data.update({"is_active": False, "email": f"inactive+{fake.uuid4()[:8]}@example.com"})
    return inactive_data


@pytest.fixture
def mock_user_object() -> Mock:
    """
    Mock User model object for unit tests

    Provides a mock User object that behaves like the SQLAlchemy User model
    without requiring database interaction.

    Returns:
        Mock object with User model properties
    """
    user = Mock()
    user.id = fake.uuid4()
    user.email = fake.email()
    user.name = fake.name()
    user.given_name = fake.first_name()
    user.family_name = fake.last_name()
    user.is_active = True
    user.is_superuser = False
    user.organization_id = fake.uuid4()
    user.display_name = user.name
    return user


# === 🗄️ DATABASE FIXTURES (Integration Tests - Real Database) ===


@pytest.fixture
def db_user(test_db, test_org_id):
    """
    Create real user in test database

    Creates an actual User record in the database for integration tests.
    Automatically uses the test organization to avoid foreign key issues.

    Args:
        test_db: Database session fixture
        test_org_id: Dynamic organization ID from API key

    Returns:
        User: Real user record from database
    """
    if User is None:
        pytest.skip("User model not available")

    import time
    import uuid

    # Generate truly unique data to avoid conflicts between tests
    unique_suffix = f"{int(time.time() * 1000000)}"  # microsecond timestamp

    user = User(
        email=f"test-{unique_suffix}@example.com",
        name=fake.name(),
        given_name=fake.first_name(),
        family_name=fake.last_name(),
        is_active=True,
        is_superuser=False,
        auth0_id=f"auth0|{uuid.uuid4()}",
        organization_id=test_org_id,
    )
    test_db.add(user)
    test_db.flush()  # Make sure the object gets an ID
    test_db.refresh(user)
    return user


@pytest.fixture
def db_admin(test_db, test_org_id):
    """
    🗄️👨‍💼 Create real admin user in test database

    Args:
        test_db: Database session fixture
        test_org_id: Dynamic organization ID from API key

    Returns:
        User: Real admin user record from database
    """
    if User is None:
        pytest.skip("User model not available")

    admin = User(
        email=f"admin+{fake.uuid4()[:8]}@example.com",
        name=f"Admin {fake.last_name()}",
        given_name="Admin",
        family_name=fake.last_name(),
        is_active=True,
        is_superuser=True,
        auth0_id=f"auth0|{fake.uuid4()}",
        organization_id=test_org_id,
    )
    test_db.add(admin)
    test_db.flush()  # Make sure the object gets an ID
    test_db.refresh(admin)
    return admin


@pytest.fixture
def db_inactive_user(test_db, test_org_id):
    """
    🗄️🚫 Create real inactive user in test database

    Args:
        test_db: Database session fixture
        test_org_id: Dynamic organization ID from API key

    Returns:
        User: Real inactive user record from database
    """
    if User is None:
        pytest.skip("User model not available")

    user = User(
        email=f"inactive+{fake.uuid4()[:8]}@example.com",
        name=f"Inactive {fake.last_name()}",
        is_active=False,
        is_superuser=False,
        auth0_id=f"auth0|{fake.uuid4()}",
        organization_id=test_org_id,
    )
    test_db.add(user)
    test_db.flush()  # Make sure the object gets an ID
    test_db.refresh(user)
    return user


@pytest.fixture
def db_owner_user(test_db, test_org_id):
    """
    🗄️🏠 Create real user for owner relationships

    Creates a user specifically for testing owner_id relationships.

    Args:
        test_db: Database session fixture
        test_org_id: Dynamic organization ID from API key

    Returns:
        User: Real user record for owner relationships
    """
    if User is None:
        pytest.skip("User model not available")

    import time

    unique_suffix = f"{int(time.time() * 1000000)}"  # microsecond timestamp
    owner = User(
        email=f"owner+{unique_suffix}@example.com",
        name=f"Owner {fake.last_name()}",
        given_name="Owner",
        family_name=fake.last_name(),
        is_active=True,
        is_superuser=False,
        auth0_id=f"auth0|{fake.uuid4()}",
        organization_id=test_org_id,
    )
    test_db.add(owner)
    test_db.flush()  # Make sure the object gets an ID
    test_db.refresh(owner)
    return owner


@pytest.fixture
def db_assignee_user(test_db, test_org_id):
    """
    🗄️📋 Create real user for assignee relationships

    Creates a user specifically for testing assignee_id relationships.

    Args:
        test_db: Database session fixture
        test_org_id: Dynamic organization ID from API key

    Returns:
        User: Real user record for assignee relationships
    """
    if User is None:
        pytest.skip("User model not available")

    import time

    unique_suffix = f"{int(time.time() * 1000000)}"  # microsecond timestamp
    assignee = User(
        email=f"assignee+{unique_suffix}@example.com",
        name=f"Assignee {fake.last_name()}",
        given_name="Assignee",
        family_name=fake.last_name(),
        is_active=True,
        is_superuser=False,
        auth0_id=f"auth0|{fake.uuid4()}",
        organization_id=test_org_id,
    )
    test_db.add(assignee)
    test_db.flush()  # Make sure the object gets an ID
    test_db.refresh(assignee)
    return assignee


# === 🔑 AUTHENTICATED FIXTURES (The Real Authenticated User) ===


@pytest.fixture
def authenticated_user(test_db, authenticated_user_id):
    """
    🔑👤 Get the real authenticated user from database

    Retrieves the actual user that corresponds to the API key used in tests.
    This is the user behind the authenticated_client fixture.

    Args:
        test_db: Database session fixture
        authenticated_user_id: Dynamic user ID from API key

    Returns:
        User: The authenticated user record
    """
    if User is None:
        pytest.skip("User model not available")

    user = test_db.query(User).filter(User.id == authenticated_user_id).first()
    if not user:
        pytest.skip(f"Authenticated user {authenticated_user_id} not found in test database")
    return user


@pytest.fixture
def authenticated_user_data(authenticated_user) -> Dict[str, Any]:
    """
    🔑📊 Get authenticated user data as dictionary

    Returns the authenticated user data in dictionary format for tests
    that need user data but not the SQLAlchemy object.

    Args:
        authenticated_user: The authenticated user fixture

    Returns:
        Dict containing authenticated user data
    """
    return {
        "id": str(authenticated_user.id),
        "email": authenticated_user.email,
        "name": authenticated_user.name,
        "given_name": authenticated_user.given_name,
        "family_name": authenticated_user.family_name,
        "is_active": authenticated_user.is_active,
        "is_superuser": authenticated_user.is_superuser,
        "organization_id": str(authenticated_user.organization_id),
        "display_name": authenticated_user.display_name,
    }


@pytest.fixture
def test_organization(test_db, test_org_id):
    """
    🔑🏢 Get the test organization from database

    Retrieves the test organization that all test users belong to.

    Args:
        test_db: Database session fixture
        test_org_id: Dynamic organization ID from API key

    Returns:
        Organization: The test organization record
    """
    if Organization is None:
        pytest.skip("Organization model not available")

    org = test_db.query(Organization).filter(Organization.id == test_org_id).first()
    if not org:
        pytest.skip(f"Test organization {test_org_id} not found in database")
    return org


# === 🎯 CONVENIENCE FIXTURES (Common Combinations) ===


@pytest.fixture
def user_trio(db_user, db_owner_user, db_assignee_user):
    """
    🎯👥 Three users for relationship testing

    Provides three different users for testing various user relationships:
    - Regular user
    - Owner user
    - Assignee user

    Returns:
        Dict with 'user', 'owner', and 'assignee' keys
    """
    return {"user": db_user, "owner": db_owner_user, "assignee": db_assignee_user}


@pytest.fixture
def admin_and_user(db_admin, db_user):
    """
    🎯👨‍💼👤 Admin and regular user for permission testing

    Returns:
        Dict with 'admin' and 'user' keys
    """
    return {"admin": db_admin, "user": db_user}


# LEGACY ALIASES (for backward compatibility - will be removed in future)
sample_user = mock_user_data
mock_user = mock_user_object
admin_user = mock_admin_data
inactive_user = mock_inactive_user_data
db_authenticated_user = authenticated_user
db_admin_user = db_admin


# Export all fixtures for easy discovery
__all__ = [
    # Mock fixtures (unit tests)
    "mock_user_data",
    "mock_admin_data",
    "mock_inactive_user_data",
    "mock_user_object",
    # Database fixtures (integration tests)
    "db_user",
    "db_admin",
    "db_inactive_user",
    "db_owner_user",
    "db_assignee_user",
    # Authenticated fixtures (the real user)
    "authenticated_user",
    "authenticated_user_data",
    "test_organization",
    # Convenience fixtures
    "user_trio",
    "admin_and_user",
    # Legacy aliases (deprecated)
    "sample_user",
    "mock_user",
    "admin_user",
    "inactive_user",
    "db_authenticated_user",
    "db_admin_user",
]
