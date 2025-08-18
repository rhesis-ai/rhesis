"""
👤 User Fixtures

Fixtures for creating user entities and authentication scenarios.
"""

import pytest
from typing import Dict, Any
from unittest.mock import Mock
from faker import Faker

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
