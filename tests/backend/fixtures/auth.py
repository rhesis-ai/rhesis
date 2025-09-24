"""
🔑 Authentication Fixtures Module

This module contains authentication-related fixtures for testing, including:
- User authentication and organization setup
- API key management
- Dynamic authentication fixtures

Extracted from conftest.py for better modularity and maintainability.
"""

import os
import pytest
from datetime import datetime
import uuid
from typing import Tuple

from .database import TestingSessionLocal


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


@pytest.fixture
def rhesis_api_key():
    """🔑 API key from environment for testing"""
    api_key = os.getenv("RHESIS_API_KEY")
    masked_key = f"{api_key[:3]}...{api_key[-4:]}" if api_key else None
    print(f"🔍 DEBUG: RHESIS_API_KEY from environment: {masked_key}")
    if not api_key:
        # Fallback to mock key if no real key is available
        fallback_key = "rh-test1234567890abcdef"
        fallback_masked = f"{fallback_key[:3]}...{fallback_key[-4:]}"
        print(f"🔍 DEBUG: Using fallback key: {fallback_masked}")
        return fallback_key
    print(f"🔍 DEBUG: Using environment API key: {masked_key}")
    return api_key


@pytest.fixture(scope="function")
def authenticated_user_info() -> tuple[str, str]:
    """
    🔑 Create fresh test user and organization for each test
    
    This fixture creates a completely self-contained test environment without
    relying on external API keys or environment variables.
        
    Returns:
        Tuple of (organization_id, user_id) as strings
    """
    from tests.backend.fixtures.test_setup import create_test_organization_and_user
    
    # Create a temporary database session
    session = TestingSessionLocal()
    try:
        # Generate unique names for this test
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_suffix = str(uuid.uuid4())[:8]
        test_org_name = f"Test Organization {timestamp}_{unique_suffix}"
        test_user_email = f"test_{timestamp}_{unique_suffix}@rhesis-test.com"
        test_user_name = "Test User"
        
        # Create fresh test data
        organization, user, token = create_test_organization_and_user(
            session, test_org_name, test_user_email, test_user_name
        )
        
        print(f"🆕 Created fresh test auth data: user={user.id}, org={organization.id}")
        
        return str(organization.id), str(user.id)
        
    except Exception as e:
        print(f"❌ Failed to create test auth data: {e}")
        pytest.skip(f"Could not create test authentication data: {e}")
    finally:
        session.close()


@pytest.fixture(scope="function") 
def test_org_id(authenticated_user_info) -> str:
    """🏢 Get the test organization ID from fresh test data"""
    org_id, _ = authenticated_user_info
    return org_id


@pytest.fixture(scope="function")
def authenticated_user_id(authenticated_user_info) -> str:
    """👤 Get the authenticated user ID from fresh test data"""
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
        user_id=authenticated_user_id
    )
    test_db.add(entity_type)
    test_db.commit()
    test_db.refresh(entity_type)
    return entity_type
