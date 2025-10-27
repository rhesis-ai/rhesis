"""
Tests for user utility functions in rhesis.backend.app.auth.user_utils

This module tests user utility functions including:
- find_or_create_user function
- get_current_user function
- get_user_from_jwt function
- get_authenticated_user_with_context function
- Tenant context setting in user authentication flows
"""

import pytest
import uuid
from unittest.mock import Mock, patch, MagicMock
from fastapi import Request, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from contextlib import contextmanager
from datetime import datetime, timezone

from rhesis.backend.app.auth.user_utils import (
    find_or_create_user,
    get_current_user,
    get_user_from_jwt,
    get_authenticated_user_with_context,
)
from rhesis.backend.app.models.user import User
from rhesis.backend.app.schemas import UserCreate


class TestFindOrCreateUser:
    """Test find_or_create_user function"""
    
    def test_find_user_by_email_existing(self, test_db: Session):
        """Test finding existing user by email"""
        auth0_id = "auth0|123456"
        email = "test@example.com"
        user_profile = {
            "name": "Test User",
            "given_name": "Test",
            "family_name": "User",
            "picture": "https://example.com/pic.jpg"
        }
        
        # Create existing user in the database
        existing_user = User(
            id=uuid.uuid4(),
            email=email,
            name="Old Name",
            given_name="Old",
            family_name="Name",
            picture="old_picture.jpg",
            auth0_id="old_auth0_id"
        )
        test_db.add(existing_user)
        test_db.flush()
        
        # Call the function with real database
        result = find_or_create_user(test_db, auth0_id, email, user_profile)
        
        assert result == existing_user
        
        # Verify user profile was updated
        assert existing_user.name == user_profile["name"]
        assert existing_user.given_name == user_profile["given_name"]
        assert existing_user.family_name == user_profile["family_name"]
        assert existing_user.picture == user_profile["picture"]
        assert existing_user.auth0_id == auth0_id
        
        # Note: db.commit is not called for existing users - transaction is handled by session context
    
    def test_find_user_by_auth0_id_matching_email(self, test_db: Session):
        """Test finding user by auth0_id with matching email"""
        auth0_id = "auth0|123456"
        email = "test@example.com"
        user_profile = {
            "name": "Test User",
            "given_name": "Test",
            "family_name": "User",
            "picture": "https://example.com/pic.jpg"
        }
        
        # Create existing user in the database with matching auth0_id
        existing_user = User(
            id=uuid.uuid4(),
            email=email,
            name="Old Name",
            given_name="Old",
            family_name="Name",
            picture="old_picture.jpg",
            auth0_id=auth0_id
        )
        test_db.add(existing_user)
        test_db.flush()
        
        # Call the function with real database
        result = find_or_create_user(test_db, auth0_id, email, user_profile)
        
        assert result == existing_user
        
        # Verify user profile was updated
        assert existing_user.name == user_profile["name"]
        assert existing_user.given_name == user_profile["given_name"]
        assert existing_user.family_name == user_profile["family_name"]
        assert existing_user.picture == user_profile["picture"]
        assert existing_user.auth0_id == auth0_id
        
        # Note: db.commit is not called for existing users - transaction is handled by session context
    
    def test_find_user_by_auth0_id_different_email_creates_new(self, test_db: Session):
        """Test finding user by auth0_id with different email creates new user"""
        auth0_id = "auth0|123456"
        email = f"new_user_{uuid.uuid4().hex[:8]}@example.com"
        different_email = f"existing_user_{uuid.uuid4().hex[:8]}@example.com"
        user_profile = {
            "name": "Test User",
            "given_name": "Test",
            "family_name": "User",
            "picture": "https://example.com/pic.jpg"
        }
        
        # Create existing user with same auth0_id but different email
        existing_user = User(
            id=uuid.uuid4(),
            email=different_email,
            name="Existing User",
            given_name="Existing",
            family_name="User",
            picture="old_picture.jpg",
            auth0_id=auth0_id
        )
        test_db.add(existing_user)
        test_db.flush()
        
        # Call function - should create new user because email is different
        result = find_or_create_user(test_db, auth0_id, email, user_profile)
        
        # Should be a new user (different from existing_user)
        assert result.id != existing_user.id
        assert result.email == email
        assert result.auth0_id == auth0_id
        assert result.name == user_profile["name"]
    
    def test_create_new_user_no_existing(self, test_db: Session):
        """Test creating new user when none exists"""
        auth0_id = f"auth0|{uuid.uuid4().hex[:12]}"
        email = f"new_user_{uuid.uuid4().hex[:8]}@example.com"
        user_profile = {
            "name": "Test User",
            "given_name": "Test",
            "family_name": "User",
            "picture": "https://example.com/pic.jpg"
        }
        
        # Call function - should create new user
        result = find_or_create_user(test_db, auth0_id, email, user_profile)
        
        # Verify new user was created with correct data
        assert result is not None
        assert result.email == email
        assert result.auth0_id == auth0_id
        assert result.name == user_profile["name"]
        assert result.given_name == user_profile["given_name"]
        assert result.family_name == user_profile["family_name"]
        assert result.picture == user_profile["picture"]


class TestGetCurrentUser:
    """Test get_current_user function"""
    
    def test_get_current_user_no_session(self):
        """Test get_current_user returns None when no user_id in session"""
        request = Mock()
        request.session = {}
        
        result = pytest.run(get_current_user(request))
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_current_user_with_organization(self, test_db: Session, test_org_id: str):
        """Test get_current_user with user having organization"""
        from tests.backend.fixtures.test_setup import create_test_user
        
        # Create a real user with organization in the database
        user = create_test_user(
            test_db,
            organization_id=uuid.UUID(test_org_id),
            email=f"test_current_user_{uuid.uuid4().hex[:8]}@example.com",  # Unique email
            name="Test Current User"
        )
        test_db.commit()
        
        # Get user ID and organization ID before the session closes
        user_id = str(user.id)
        user_email = user.email
        user_org_id = user.organization_id
        
        # Create request with user_id in session
        request = Mock()
        request.session = {"user_id": user_id}
        
        # Call the async function
        result = await get_current_user(request)
        
        # Verify the user is returned
        assert result is not None
        assert str(result.id) == user_id
        assert result.organization_id == user_org_id
        assert result.email == user_email
    
    @pytest.mark.asyncio
    async def test_get_current_user_without_organization(self, test_db: Session):
        """Test get_current_user with user having no organization - should return None"""
        from rhesis.backend.app import crud
        from rhesis.backend.app.schemas import UserCreate
        
        # Create a user WITHOUT an organization (unique email for each run)
        user_data = UserCreate(
            email=f"user_no_org_{uuid.uuid4().hex[:8]}@example.com",  # Unique email
            name="User Without Org",
            given_name="User",
            family_name="Without Org",
            auth0_id=f"test-auth0-no-org-{uuid.uuid4()}",
            is_active=True,
            is_superuser=False,
            organization_id=None,  # No organization
            last_login_at=datetime.now(timezone.utc)
        )
        user = crud.create_user(test_db, user_data)
        test_db.commit()
        
        # Get user ID before the session closes
        user_id = str(user.id)
        
        # Create request with user_id in session
        request = Mock()
        request.session = {"user_id": user_id}
        
        # Call the async function
        result = await get_current_user(request)
        
        # Should return None because user has no organization_id
        assert result is None


class TestGetUserFromJwt:
    """Test get_user_from_jwt function"""
    
    @pytest.mark.asyncio
    async def test_get_user_from_jwt_success(self, test_db: Session, test_org_id: str):
        """Test successful JWT user retrieval"""
        from tests.backend.fixtures.test_setup import create_test_user
        
        # Create a real user in the database
        user = create_test_user(
            test_db,
            organization_id=uuid.UUID(test_org_id),
            email=f"jwt_user_{uuid.uuid4().hex[:8]}@example.com",
            name="JWT Test User"
        )
        test_db.commit()
        
        # Get user data before session closes
        user_id = str(user.id)
        user_email = user.email
        user_org_id = user.organization_id
        
        token = "valid.jwt.token"
        secret_key = "test-secret"
        jwt_payload = {"user": {"id": user_id}}
        
        # Only mock JWT verification - use real database for user lookup
        with patch('rhesis.backend.app.auth.user_utils.verify_jwt_token', return_value=jwt_payload):
            result = await get_user_from_jwt(token, secret_key)
            
            assert result is not None
            assert str(result.id) == user_id
            assert result.email == user_email
            assert result.organization_id == user_org_id
    
    @pytest.mark.asyncio
    async def test_get_user_from_jwt_user_not_found(self):
        """Test JWT user retrieval when user not found"""
        token = "valid.jwt.token"
        secret_key = "test-secret"
        nonexistent_user_id = str(uuid.uuid4())
        jwt_payload = {"user": {"id": nonexistent_user_id}}
        
        # Only mock JWT verification - use real database for user lookup
        with patch('rhesis.backend.app.auth.user_utils.verify_jwt_token', return_value=jwt_payload):
            result = await get_user_from_jwt(token, secret_key)
            assert result is None
    
    @pytest.mark.asyncio
    async def test_get_user_from_jwt_invalid_token(self):
        """Test JWT user retrieval with invalid token"""
        token = "invalid.jwt.token"
        secret_key = "test-secret"
        
        # Mock JWT verification to raise an exception
        with patch('rhesis.backend.app.auth.user_utils.verify_jwt_token', side_effect=Exception("Invalid token")):
            result = await get_user_from_jwt(token, secret_key)
            assert result is None


class TestGetAuthenticatedUserWithContext:
    """Test get_authenticated_user_with_context function"""
    
    @pytest.mark.asyncio
    async def test_session_only_authentication(self, test_db: Session, test_org_id: str):
        """Test authentication using session only"""
        from tests.backend.fixtures.test_setup import create_test_user
        
        # Create a real user in the database
        user = create_test_user(
            test_db,
            organization_id=uuid.UUID(test_org_id),
            email=f"session_user_{uuid.uuid4().hex[:8]}@example.com",
            name="Session Test User"
        )
        test_db.commit()
        
        # Get user data before session closes
        user_id = str(user.id)
        
        # Create request with session
        request = Mock()
        request.session = {"user_id": user_id}
        
        result = await get_authenticated_user_with_context(request, session_only=True)
        
        assert result is not None
        assert str(result.id) == user_id
    
    @pytest.mark.asyncio
    async def test_jwt_authentication_success(self, test_db: Session, test_org_id: str):
        """Test successful JWT authentication"""
        from tests.backend.fixtures.test_setup import create_test_user
        
        # Create a real user in the database
        user = create_test_user(
            test_db,
            organization_id=uuid.UUID(test_org_id),
            email=f"jwt_auth_user_{uuid.uuid4().hex[:8]}@example.com",
            name="JWT Auth Test User"
        )
        test_db.commit()
        
        # Get user data before session closes
        user_id = str(user.id)
        
        request = Mock()
        request.session = {}  # Empty session
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="jwt-token")
        jwt_payload = {"user": {"id": user_id}}
        
        # Mock JWT verification to return real user ID
        with patch('rhesis.backend.app.auth.user_utils.verify_jwt_token', return_value=jwt_payload):
            result = await get_authenticated_user_with_context(
                request, credentials=credentials, secret_key="secret"
            )
            
            assert result is not None
            assert str(result.id) == user_id
    
    @pytest.mark.asyncio
    async def test_fallback_to_session_when_jwt_fails(self, test_db: Session, test_org_id: str):
        """Test fallback to session when JWT authentication fails"""
        from tests.backend.fixtures.test_setup import create_test_user
        
        # Create a real user in the database
        user = create_test_user(
            test_db,
            organization_id=uuid.UUID(test_org_id),
            email=f"fallback_user_{uuid.uuid4().hex[:8]}@example.com",
            name="Fallback Test User"
        )
        test_db.commit()
        
        # Get user data before session closes
        user_id = str(user.id)
        
        request = Mock()
        request.session = {"user_id": user_id}
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid-jwt")
        
        # Mock JWT verification to fail
        with patch('rhesis.backend.app.auth.user_utils.verify_jwt_token', side_effect=Exception("Invalid token")):
            result = await get_authenticated_user_with_context(
                request, credentials=credentials, secret_key="secret"
            )
            
            assert result is not None
            assert str(result.id) == user_id
    
    @pytest.mark.asyncio
    async def test_without_context_flag(self, test_db: Session, test_org_id: str):
        """Test authentication without setting tenant context"""
        from tests.backend.fixtures.test_setup import create_test_user
        
        # Create a real user in the database
        user = create_test_user(
            test_db,
            organization_id=uuid.UUID(test_org_id),
            email=f"no_context_user_{uuid.uuid4().hex[:8]}@example.com",
            name="No Context Test User"
        )
        test_db.commit()
        
        # Get user data before session closes
        user_id = str(user.id)
        
        request = Mock()
        request.session = {"user_id": user_id}
        
        result = await get_authenticated_user_with_context(request, without_context=True)
        
        assert result is not None
        assert str(result.id) == user_id


# Helper fixture for async testing
@pytest.fixture(autouse=True)
def setup_async_helper():
    """Set up async helper for all tests"""
    import asyncio
    
    def run_async(coro):
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        if loop.is_running():
            # If loop is already running, create a new one
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result()
        else:
            return loop.run_until_complete(coro)
    
    pytest.run = run_async
    yield
    if hasattr(pytest, 'run'):
        delattr(pytest, 'run')
