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
    
    def test_find_user_by_email_existing(self):
        """Test finding existing user by email"""
        auth0_id = "auth0|123456"
        email = "test@example.com"
        user_profile = {
            "name": "Test User",
            "given_name": "Test",
            "family_name": "User",
            "picture": "https://example.com/pic.jpg"
        }
        
        # Mock existing user
        existing_user = Mock(spec=User)
        existing_user.id = "user123"
        existing_user.email = email
        existing_user.auth0_id = "old_auth0_id"
        
        db = Mock(spec=Session)
        
        with patch('rhesis.backend.app.auth.user_utils.crud.get_user_by_email', return_value=existing_user) as mock_get_by_email:
            result = find_or_create_user(db, auth0_id, email, user_profile)
            
            assert result == existing_user
            mock_get_by_email.assert_called_once_with(db, email)
            
            # Verify user profile was updated
            assert existing_user.name == user_profile["name"]
            assert existing_user.given_name == user_profile["given_name"]
            assert existing_user.family_name == user_profile["family_name"]
            assert existing_user.picture == user_profile["picture"]
            assert existing_user.auth0_id == auth0_id
            
            db.commit.assert_called_once()
    
    def test_find_user_by_auth0_id_matching_email(self):
        """Test finding user by auth0_id with matching email"""
        auth0_id = "auth0|123456"
        email = "test@example.com"
        user_profile = {
            "name": "Test User",
            "given_name": "Test",
            "family_name": "User",
            "picture": "https://example.com/pic.jpg"
        }
        
        # Mock user found by auth0_id with matching email
        existing_user = Mock(spec=User)
        existing_user.id = "user123"
        existing_user.email = email
        existing_user.auth0_id = auth0_id
        
        db = Mock(spec=Session)
        
        with patch('rhesis.backend.app.auth.user_utils.crud.get_user_by_email', return_value=None):
            with patch('rhesis.backend.app.auth.user_utils.crud.get_user_by_auth0_id', return_value=existing_user) as mock_get_by_auth0:
                result = find_or_create_user(db, auth0_id, email, user_profile)
                
                assert result == existing_user
                mock_get_by_auth0.assert_called_once_with(db, auth0_id)
                
                # Verify user profile was updated
                assert existing_user.name == user_profile["name"]
                db.commit.assert_called_once()
    
    def test_find_user_by_auth0_id_different_email_creates_new(self):
        """Test finding user by auth0_id with different email creates new user"""
        auth0_id = "auth0|123456"
        email = "test@example.com"
        different_email = "different@example.com"
        user_profile = {
            "name": "Test User",
            "given_name": "Test",
            "family_name": "User",
            "picture": "https://example.com/pic.jpg"
        }
        
        # Mock user found by auth0_id with different email
        existing_user = Mock(spec=User)
        existing_user.email = different_email
        
        # Mock new user creation
        new_user = Mock(spec=User)
        new_user.id = "user456"
        new_user.email = email
        
        db = Mock(spec=Session)
        
        with patch('rhesis.backend.app.auth.user_utils.crud.get_user_by_email', return_value=None):
            with patch('rhesis.backend.app.auth.user_utils.crud.get_user_by_auth0_id', return_value=existing_user):
                with patch('rhesis.backend.app.auth.user_utils.crud.create_user', return_value=new_user) as mock_create:
                    result = find_or_create_user(db, auth0_id, email, user_profile)
                    
                    assert result == new_user
                    mock_create.assert_called_once()
                    
                    # Verify UserCreate schema was used correctly
                    create_call_args = mock_create.call_args[0]
                    user_create_data = create_call_args[1]  # Second argument should be UserCreate
                    
                    assert user_create_data.email == email
                    assert user_create_data.auth0_id == auth0_id
    
    def test_create_new_user_no_existing(self):
        """Test creating new user when none exists"""
        auth0_id = "auth0|123456"
        email = "test@example.com"
        user_profile = {
            "name": "Test User",
            "given_name": "Test",
            "family_name": "User",
            "picture": "https://example.com/pic.jpg"
        }
        
        # Mock new user creation
        new_user = Mock(spec=User)
        new_user.id = "user456"
        new_user.email = email
        
        db = Mock(spec=Session)
        
        with patch('rhesis.backend.app.auth.user_utils.crud.get_user_by_email', return_value=None):
            with patch('rhesis.backend.app.auth.user_utils.crud.get_user_by_auth0_id', return_value=None):
                with patch('rhesis.backend.app.auth.user_utils.crud.create_user', return_value=new_user) as mock_create:
                    result = find_or_create_user(db, auth0_id, email, user_profile)
                    
                    assert result == new_user
                    mock_create.assert_called_once()


class TestGetCurrentUser:
    """Test get_current_user function"""
    
    def test_get_current_user_no_session(self):
        """Test get_current_user returns None when no user_id in session"""
        request = Mock()
        request.session = {}
        
        result = pytest.run(get_current_user(request))
        assert result is None
    
    def test_get_current_user_with_organization(self):
        """Test get_current_user with user having organization"""
        mock_user = Mock(spec=User)
        mock_user.id = "user123"
        mock_user.organization_id = "org456"
        
        request = Mock()
        request.session = {"user_id": "user123"}
        
        # Mock get_db context manager and get_user_by_id since the function uses get_db()
        mock_db = Mock(spec=Session)
        
        @contextmanager
        def mock_get_db():
            yield mock_db
        
        with patch('rhesis.backend.app.database.get_db', mock_get_db):
            with patch('rhesis.backend.app.crud.get_user_by_id', return_value=mock_user) as mock_get_user:
                result = pytest.run(get_current_user(request))
                
                assert result == mock_user
                mock_get_user.assert_called_once_with(mock_db, "user123")
    
    def test_get_current_user_without_organization(self):
        """Test get_current_user with user having no organization - should return None"""
        mock_user = Mock(spec=User)
        mock_user.id = "user123"
        mock_user.organization_id = None
        
        request = Mock()
        request.session = {"user_id": "user123"}
        
        # Mock get_db context manager and get_user_by_id since the function uses get_db()
        mock_db = Mock(spec=Session)
        
        @contextmanager
        def mock_get_db():
            yield mock_db
        
        with patch('rhesis.backend.app.database.get_db', mock_get_db):
            with patch('rhesis.backend.app.crud.get_user_by_id', return_value=mock_user) as mock_get_user:
                result = pytest.run(get_current_user(request))
                
                # Should return None because user has no organization_id
                assert result is None
                mock_get_user.assert_called_once_with(mock_db, "user123")


class TestGetUserFromJwt:
    """Test get_user_from_jwt function"""
    
    def test_get_user_from_jwt_success(self):
        """Test successful JWT user retrieval"""
        token = "valid.jwt.token"
        secret_key = "test-secret"
        
        mock_user = Mock(spec=User)
        mock_user.id = "user123"
        mock_user.organization_id = "org456"
        
        jwt_payload = {"user": {"id": "user123"}}
        
        # Mock get_db context manager and get_user_by_id since the function uses get_db()
        mock_db = Mock(spec=Session)
        
        @contextmanager
        def mock_get_db():
            yield mock_db
        
        with patch('rhesis.backend.app.database.get_db', mock_get_db):
            with patch('rhesis.backend.app.auth.user_utils.verify_jwt_token', return_value=jwt_payload) as mock_verify:
                with patch('rhesis.backend.app.crud.get_user_by_id', return_value=mock_user) as mock_get_user:
                    result = pytest.run(get_user_from_jwt(token, secret_key))
                    
                    assert result == mock_user
                    mock_verify.assert_called_once_with(token, secret_key)
                    mock_get_user.assert_called_once_with(mock_db, "user123")
    
    def test_get_user_from_jwt_user_not_found(self):
        """Test JWT user retrieval when user not found"""
        token = "valid.jwt.token"
        secret_key = "test-secret"
        
        jwt_payload = {"user": {"id": "user123"}}
        
        # Mock get_db context manager and get_user_by_id since the function uses get_db()
        mock_db = Mock(spec=Session)
        
        @contextmanager
        def mock_get_db():
            yield mock_db
        
        with patch('rhesis.backend.app.database.get_db', mock_get_db):
            with patch('rhesis.backend.app.auth.user_utils.verify_jwt_token', return_value=jwt_payload):
                with patch('rhesis.backend.app.crud.get_user_by_id', return_value=None):
                    result = pytest.run(get_user_from_jwt(token, secret_key))
                    assert result is None
    
    def test_get_user_from_jwt_invalid_token(self):
        """Test JWT user retrieval with invalid token"""
        token = "invalid.jwt.token"
        secret_key = "test-secret"
        
        with patch('rhesis.backend.app.auth.user_utils.verify_jwt_token', side_effect=HTTPException(status_code=401)):
            result = pytest.run(get_user_from_jwt(token, secret_key))
            assert result is None


class TestGetAuthenticatedUserWithContext:
    """Test get_authenticated_user_with_context function"""
    
    def test_session_only_authentication(self):
        """Test authentication using session only"""
        mock_user = Mock(spec=User)
        mock_user.id = "user123"
        mock_user.organization_id = "org456"
        
        request = Mock()
        
        with patch('rhesis.backend.app.auth.user_utils.get_current_user', return_value=mock_user) as mock_get_current:
            result = pytest.run(get_authenticated_user_with_context(
                request, session_only=True
            ))
            
            assert result == mock_user
            mock_get_current.assert_called_once_with(request)
    
    def test_jwt_authentication_success(self):
        """Test successful JWT authentication"""
        mock_user = Mock(spec=User)
        mock_user.id = "user123"
        mock_user.organization_id = "org456"
        
        request = Mock()
        request.session = {}  # Mock empty session
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="jwt-token")
        
        # Mock get_current_user to return None (no session auth)
        with patch('rhesis.backend.app.auth.user_utils.get_current_user', return_value=None):
            with patch('rhesis.backend.app.auth.user_utils.get_user_from_jwt', return_value=mock_user) as mock_get_jwt_user:
                result = pytest.run(get_authenticated_user_with_context(
                    request, credentials=credentials, secret_key="secret"
                ))
                
                assert result == mock_user
                mock_get_jwt_user.assert_called_once_with("jwt-token", "secret")
    
    def test_fallback_to_session_when_jwt_fails(self):
        """Test fallback to session when JWT authentication fails"""
        mock_user = Mock(spec=User)
        mock_user.id = "user123"
        mock_user.organization_id = "org456"
        
        request = Mock()
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid-jwt")
        
        # Mock get_current_user to return the user (fallback to session)
        with patch('rhesis.backend.app.auth.user_utils.get_current_user', return_value=mock_user) as mock_get_current:
            with patch('rhesis.backend.app.auth.user_utils.get_user_from_jwt', return_value=None):
                result = pytest.run(get_authenticated_user_with_context(
                    request, credentials=credentials, secret_key="secret"
                ))
                
                assert result == mock_user
                mock_get_current.assert_called_once_with(request)
    
    def test_without_context_flag(self):
        """Test authentication without setting tenant context"""
        mock_user = Mock(spec=User)
        mock_user.id = "user123"
        mock_user.organization_id = "org456"
        
        request = Mock()
        db = Mock(spec=Session)
        
        # Mock get_current_user to return user without organization
        with patch('rhesis.backend.app.auth.user_utils.get_current_user', return_value=mock_user) as mock_get_current:
            result = pytest.run(get_authenticated_user_with_context(
                request, without_context=True
            ))
            
            assert result == mock_user
            mock_get_current.assert_called_once_with(request)


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
