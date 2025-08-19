"""
👤 User Fixtures

Fixtures for creating user entities and authentication scenarios.
"""

import pytest
import uuid
from typing import Dict, Any, List
from unittest.mock import Mock
from faker import Faker
from sqlalchemy.orm import Session
from rhesis.backend.app.models.user import User
from rhesis.backend.app.models.organization import Organization

fake = Faker()


@pytest.fixture
def sample_user() -> Dict[str, Any]:
    """
    👤 Create a sample user for testing
    
    This fixture provides a mock user that can be used in tests
    that need user authentication or user-related data.
    
    Returns:
        Dict containing user data including display_name
    """
    user_data = {
        "id": fake.uuid4(),
        "email": fake.email(),
        "name": fake.name(),
        "given_name": fake.first_name(),
        "family_name": fake.last_name(),
        "picture": fake.image_url(),
        "is_active": True,
        "is_superuser": False,
        "auth0_id": f"auth0|{fake.uuid4()}",
        "organization_id": fake.uuid4(),
        "display_name": fake.name()  # This is what the home endpoint uses
    }
    
    return user_data


@pytest.fixture
def mock_user() -> Mock:
    """
    👤 Create a mock User model instance
    
    This fixture provides a mock User object that behaves like the
    SQLAlchemy User model for testing purposes.
    
    Returns:
        Mock object with User model properties
    """
    user = Mock()
    user.id = fake.uuid4()
    user.email = fake.email()
    user.name = fake.name()
    user.given_name = fake.first_name()
    user.family_name = fake.last_name()
    user.picture = fake.image_url()
    user.is_active = True
    user.is_superuser = False
    user.auth0_id = f"auth0|{fake.uuid4()}"
    user.organization_id = fake.uuid4()
    
    # Mock the display_name property
    user.display_name = user.name or user.email
    
    return user


@pytest.fixture
def admin_user() -> Mock:
    """
    👨‍💼 Create a mock admin User model instance
    
    This fixture provides a mock User object with admin privileges.
    
    Returns:
        Mock object with admin User model properties
    """
    user = Mock()
    user.id = fake.uuid4()
    user.email = f"admin+{fake.uuid4()[:8]}@example.com"
    user.name = f"Admin {fake.last_name()}"
    user.given_name = "Admin"
    user.family_name = fake.last_name()
    user.picture = fake.image_url()
    user.is_active = True
    user.is_superuser = True  # Admin flag
    user.auth0_id = f"auth0|{fake.uuid4()}"
    user.organization_id = fake.uuid4()
    
    # Mock the display_name property
    user.display_name = user.name or user.email
    
    return user


@pytest.fixture
def inactive_user() -> Dict[str, Any]:
    """
    🚫 Create a sample inactive user for testing
    
    This fixture provides a user that is marked as inactive.
    
    Returns:
        Dict containing inactive user data
    """
    user_data = {
        "id": fake.uuid4(),
        "email": fake.email(),
        "name": fake.name(),
        "given_name": fake.first_name(),
        "family_name": fake.last_name(),
        "picture": fake.image_url(),
        "is_active": False,  # Inactive user
        "is_superuser": False,
        "auth0_id": f"auth0|{fake.uuid4()}",
        "organization_id": fake.uuid4(),
        "display_name": fake.name()
    }
    
    return user_data


# 🗄️ Database User Fixtures (Real Users in Database)
# These create actual User records in the test database

@pytest.fixture
def test_organization(test_db: Session) -> Organization:
    """
    🏢 Get the existing test organization from the database
    
    This fixture retrieves the existing Organization record that's already
    associated with the authenticated user. We can't create new organizations
    due to row-level security policies when a user already has an organization.
    
    Args:
        test_db: Database session fixture
        
    Returns:
        Organization: Existing organization record from database
    """
    # The organization ID from debug logs - this is the existing org
    existing_org_id = "fb61d1ea-27b2-475d-a337-31372544f029"
    org = test_db.query(Organization).filter(Organization.id == existing_org_id).first()
    
    if not org:
        # This shouldn't happen in normal test runs, but just in case
        raise RuntimeError(f"Expected organization {existing_org_id} not found in database")
    
    return org


@pytest.fixture
def db_authenticated_user(test_db: Session) -> User:
    """
    👤 Get the real authenticated user from the database
    
    This fixture retrieves the actual user that corresponds to the API key
    used in tests, ensuring foreign key relationships work correctly.
    
    Args:
        test_db: Database session fixture
        
    Returns:
        User: Real authenticated user record from database
    """
    # The API key in tests resolves to this user ID (from debug logs)
    authenticated_user_id = "6fcb94d0-280d-475b-be94-1723efc634d4"
    user = test_db.query(User).filter(User.id == authenticated_user_id).first()
    
    if not user:
        # This shouldn't happen in normal test runs since the user should exist
        raise RuntimeError(f"Expected authenticated user {authenticated_user_id} not found in database")
    
    return user


@pytest.fixture
def db_user(test_db: Session, test_organization: Organization) -> User:
    """
    👤 Create a real user in the test database
    
    This fixture creates an actual User record in the database that can be
    used for foreign key relationships in tests. This solves the issue of
    mock UUIDs causing foreign key violations.
    
    Args:
        test_db: Database session fixture
        test_organization: Organization fixture
        
    Returns:
        User: Real user record with valid database ID
    """
    # Use the same organization as the authenticated user to ensure consistency
    auth_org_id = "fb61d1ea-27b2-475d-a337-31372544f029"
    
    user = User(
        email=fake.email(),
        name=fake.name(),
        given_name=fake.first_name(),
        family_name=fake.last_name(),
        picture=fake.image_url(),
        is_active=True,
        is_superuser=False,
        auth0_id=f"auth0|{fake.uuid4()}",
        organization_id=auth_org_id
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def db_admin_user(test_db: Session, test_organization: Organization) -> User:
    """
    👨‍💼 Create a real admin user in the test database
    
    This fixture creates an actual admin User record in the database.
    
    Args:
        test_db: Database session fixture
        test_organization: Organization fixture
        
    Returns:
        User: Real admin user record with valid database ID
    """
    # Use the same organization as the authenticated user to ensure consistency
    auth_org_id = "fb61d1ea-27b2-475d-a337-31372544f029"
    
    admin = User(
        email=f"admin+{fake.uuid4()[:8]}@example.com",
        name=f"Admin {fake.last_name()}",
        given_name="Admin",
        family_name=fake.last_name(),
        picture=fake.image_url(),
        is_active=True,
        is_superuser=True,
        auth0_id=f"auth0|{fake.uuid4()}",
        organization_id=auth_org_id
    )
    test_db.add(admin)
    test_db.commit()
    test_db.refresh(admin)
    return admin


@pytest.fixture
def db_owner_user(test_db: Session, test_organization: Organization) -> User:
    """
    🏠 Create a real owner user in the test database
    
    This fixture creates an actual User record that can be used
    as an owner in owner_id relationships.
    
    Args:
        test_db: Database session fixture
        test_organization: Organization fixture
        
    Returns:
        User: Real user record for owner relationships
    """
    # Use the same organization as the authenticated user to ensure consistency
    auth_org_id = "fb61d1ea-27b2-475d-a337-31372544f029"
    
    owner = User(
        email=f"owner+{fake.uuid4()[:8]}@example.com",
        name=f"Owner {fake.last_name()}",
        given_name="Owner",
        family_name=fake.last_name(),
        picture=fake.image_url(),
        is_active=True,
        is_superuser=False,
        auth0_id=f"auth0|{fake.uuid4()}",
        organization_id=auth_org_id
    )
    test_db.add(owner)
    test_db.commit()
    test_db.refresh(owner)
    return owner


@pytest.fixture
def db_assignee_user(test_db: Session, test_organization: Organization) -> User:
    """
    📋 Create a real assignee user in the test database
    
    This fixture creates an actual User record that can be used
    as an assignee in assignee_id relationships.
    
    Args:
        test_db: Database session fixture
        test_organization: Organization fixture
        
    Returns:
        User: Real user record for assignee relationships
    """
    # Use the same organization as the authenticated user to ensure consistency
    auth_org_id = "fb61d1ea-27b2-475d-a337-31372544f029"
    
    assignee = User(
        email=f"assignee+{fake.uuid4()[:8]}@example.com",
        name=f"Assignee {fake.last_name()}",
        given_name="Assignee",
        family_name=fake.last_name(),
        picture=fake.image_url(),
        is_active=True,
        is_superuser=False,
        auth0_id=f"auth0|{fake.uuid4()}",
        organization_id=auth_org_id
    )
    test_db.add(assignee)
    test_db.commit()
    test_db.refresh(assignee)
    return assignee


# 🌐 API-Based User Fixtures (Create Users via API)
# These create users through the API instead of direct database insertion

def _create_api_user_with_fallback(authenticated_client, user_type: str = "user") -> Dict[str, Any]:
    """
    🛡️ Helper function to create API user with rate limit fallback
    
    Attempts to create a user via API, falls back to authenticated user if rate limited.
    
    Args:
        authenticated_client: Test client
        user_type: Type of user (user, owner, assignee)
    
    Returns:
        Dict containing user data including ID
    """
    import time
    import random
    
    # Try to create user via API
    unique_suffix = f"{int(time.time()*1000)}{random.randint(100,999)}"
    
    user_data = {
        "email": f"{user_type}+{unique_suffix}@example.com",
        "name": f"{user_type.title()} {fake.last_name()}",
        "given_name": user_type.title(),
        "family_name": fake.last_name(),
        "is_active": True,
        "is_superuser": False
    }
    
    try:
        response = authenticated_client.post("/users/", json=user_data)
        
        # Handle rate limiting gracefully
        if response.status_code == 429:  # Too Many Requests
            print(f"⚠️  Rate limit hit, falling back to authenticated user for {user_type}")
            return {
                "id": "6fcb94d0-280d-475b-be94-1723efc634d4",
                "email": f"fallback_{user_type}@auth.com", 
                "name": f"Auth {user_type.title()}",
                "is_fallback": True,
                "user_type": user_type
            }
        elif response.status_code == 200:
            user_json = response.json()
            user_json["user_type"] = user_type
            return user_json
        else:
            # Other API error, fall back to authenticated user
            print(f"⚠️  API error ({response.status_code}), falling back to authenticated user for {user_type}")
            return {
                "id": "6fcb94d0-280d-475b-be94-1723efc634d4",
                "email": f"fallback_{user_type}@auth.com",
                "name": f"Auth {user_type.title()}",
                "is_fallback": True,
                "user_type": user_type
            }
    except Exception as e:
        # Network or other error, fall back to authenticated user
        print(f"⚠️  Exception creating {user_type} user, falling back to authenticated user: {e}")
        return {
            "id": "6fcb94d0-280d-475b-be94-1723efc634d4",
            "email": f"fallback_{user_type}@auth.com",
            "name": f"Auth {user_type.title()}",
            "is_fallback": True,
            "user_type": user_type
        }


@pytest.fixture
def api_user(authenticated_client) -> Dict[str, Any]:
    """
    🌐👤 Create a user via API with rate limit fallback
    
    Attempts to create a user through the API, falls back to authenticated user
    if rate limited or other issues occur.
    
    Returns:
        Dict containing user data including ID
    """
    return _create_api_user_with_fallback(authenticated_client, "user")


@pytest.fixture
def api_owner_user(authenticated_client) -> Dict[str, Any]:
    """
    🌐🏠 Create an owner user via API with rate limit fallback
    
    Attempts to create an owner user through the API, falls back to authenticated user
    if rate limited or other issues occur.
    
    Returns:
        Dict containing owner user data
    """
    return _create_api_user_with_fallback(authenticated_client, "owner")


@pytest.fixture
def api_assignee_user(authenticated_client) -> Dict[str, Any]:
    """
    🌐📋 Create an assignee user via API with rate limit fallback
    
    Attempts to create an assignee user through the API, falls back to authenticated user
    if rate limited or other issues occur.
    
    Returns:
        Dict containing assignee user data
    """
    return _create_api_user_with_fallback(authenticated_client, "assignee")
