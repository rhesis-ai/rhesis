"""
Tests for auth utility functions in rhesis.backend.app.auth.auth_utils

This module tests authentication utility functions including:
- get_current_user function
- JWT token verification
- Token validation
- get_authenticated_user_with_context function
- Tenant context setting in authentication flows
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi import Request, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from contextlib import contextmanager
from jose import JWTError
from datetime import datetime, timezone

from rhesis.backend.app.auth.auth_utils import (
    get_current_user,
    verify_jwt_token,
    validate_token,
    get_authenticated_user_with_context,
    get_secret_key,
)
from rhesis.backend.app.models.user import User
from rhesis.backend.app.models.token import Token


class TestGetSecretKey:
    """Test get_secret_key function"""

    def test_get_secret_key_success(self):
        """Test successful retrieval of JWT secret key"""
        with patch("os.getenv", return_value="test-secret-key"):
            secret_key = get_secret_key()
            assert secret_key == "test-secret-key"

    def test_get_secret_key_missing(self):
        """Test HTTPException when JWT_SECRET_KEY is not configured"""
        with patch("os.getenv", return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                get_secret_key()
            assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "JWT_SECRET_KEY not configured" in str(exc_info.value.detail)


class TestGetCurrentUser:
    """Test get_current_user function"""

    def test_get_current_user_no_session(self):
        """Test get_current_user returns None when no user_id in session"""
        request = Mock()
        request.session = {}

        result = pytest.run(get_current_user(request))
        assert result is None

    def test_get_current_user_with_session_user_found(self):
        """Test get_current_user returns user when found in session"""
        # Create mock user with organization
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

        with patch("rhesis.backend.app.database.get_db", mock_get_db):
            with patch(
                "rhesis.backend.app.auth.auth_utils.get_user_by_id", return_value=mock_user
            ) as mock_get_user:
                result = pytest.run(get_current_user(request))

                assert result == mock_user
                mock_get_user.assert_called_once_with(mock_db, "user123")

    def test_get_current_user_with_session_no_org(self):
        """Test get_current_user with user but no organization - should return None"""
        # Create mock user without organization
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

        with patch("rhesis.backend.app.database.get_db", mock_get_db):
            with patch(
                "rhesis.backend.app.auth.auth_utils.get_user_by_id", return_value=mock_user
            ) as mock_get_user:
                result = pytest.run(get_current_user(request))

                # Should return None because user has no organization_id
                assert result is None
                mock_get_user.assert_called_once_with(mock_db, "user123")

    def test_get_current_user_user_not_found(self):
        """Test get_current_user returns None when user not found in database"""
        request = Mock()
        request.session = {"user_id": "user123"}

        # Mock get_db context manager and get_user_by_id since the function uses get_db()
        mock_db = Mock(spec=Session)

        @contextmanager
        def mock_get_db():
            yield mock_db

        with patch("rhesis.backend.app.database.get_db", mock_get_db):
            with patch("rhesis.backend.app.auth.auth_utils.get_user_by_id", return_value=None):
                result = pytest.run(get_current_user(request))
                assert result is None


class TestVerifyJwtToken:
    """Test verify_jwt_token function"""

    def test_verify_jwt_token_success(self):
        """Test successful JWT token verification"""
        token = "valid.jwt.token"
        secret_key = "test-secret"
        expected_payload = {
            "sub": "user123",
            "organization_id": "org456",
            "type": "session",  # Required for token validation
            "exp": 9999999999,  # Future expiration
            "iat": 1000000000,  # Past issued time
        }

        with patch(
            "rhesis.backend.app.auth.auth_utils.jwt.decode", return_value=expected_payload
        ) as mock_decode:
            result = verify_jwt_token(token, secret_key)

            assert result == expected_payload
            mock_decode.assert_called_once_with(
                token,
                secret_key,
                algorithms=["HS256"],
                options={
                    "verify_exp": True,
                    "verify_iat": True,
                    "require_exp": True,
                    "require_iat": True,
                },
            )

    def test_verify_jwt_token_invalid(self):
        """Test JWT token verification with invalid token"""
        token = "invalid.jwt.token"
        secret_key = "test-secret"

        with patch(
            "rhesis.backend.app.auth.auth_utils.jwt.decode", side_effect=JWTError("Invalid token")
        ):
            # The function should re-raise the JWTError, not convert to HTTPException
            with pytest.raises(JWTError) as exc_info:
                verify_jwt_token(token, secret_key)

            assert "Invalid token" in str(exc_info.value)


class TestValidateToken:
    """Test validate_token function"""

    def test_validate_token_success_with_usage_update(self):
        """Test successful token validation with usage update"""
        token_value = "rh-valid-token"  # Must start with 'rh-'
        mock_token = Mock(spec=Token)
        mock_token.is_valid = True
        mock_token.usage_count = 5
        mock_token.last_used_at = datetime.now(timezone.utc)
        mock_token.expires_at = None  # No expiration

        db = Mock(spec=Session)

        with patch(
            "rhesis.backend.app.auth.auth_utils.get_token_by_value", return_value=mock_token
        ) as mock_get_token:
            result = validate_token(token_value, update_usage=True, db=db)

            assert result == (True, None)
            mock_get_token.assert_called_once_with(db, token_value)

    def test_validate_token_success_without_usage_update(self):
        """Test successful token validation without usage update"""
        token_value = "rh-valid-token"  # Must start with 'rh-'
        mock_token = Mock(spec=Token)
        mock_token.is_valid = True
        mock_token.expires_at = None  # No expiration

        db = Mock(spec=Session)

        with patch(
            "rhesis.backend.app.auth.auth_utils.get_token_by_value", return_value=mock_token
        ):
            result = validate_token(token_value, update_usage=False, db=db)

            assert result == (True, None)

    def test_validate_token_not_found(self):
        """Test token validation when token not found"""
        token_value = "rh-nonexistent-token"  # Must start with 'rh-'
        db = Mock(spec=Session)

        with patch("rhesis.backend.app.auth.auth_utils.get_token_by_value", return_value=None):
            result = validate_token(token_value, db=db)

            assert result == (False, "Invalid or revoked token")

    def test_validate_token_invalid_format(self):
        """Test token validation with invalid format"""
        token_value = "invalid-token"  # Doesn't start with 'rh-'
        db = Mock(spec=Session)

        result = validate_token(token_value, db=db)

        assert result == (False, "Invalid token format. Token must start with 'rh-'")


class TestGetAuthenticatedUserWithContext:
    """Test get_authenticated_user_with_context function"""

    def test_get_authenticated_user_session_only_success(self):
        """Test authentication with session only"""
        mock_user = Mock(spec=User)
        mock_user.id = "user123"
        mock_user.organization_id = "org456"

        request = Mock()

        with patch(
            "rhesis.backend.app.auth.auth_utils.get_current_user", return_value=mock_user
        ) as mock_get_current:
            result = pytest.run(get_authenticated_user_with_context(request, session_only=True))

            assert result == mock_user
            mock_get_current.assert_called_once_with(request)

    def test_get_authenticated_user_jwt_success(self):
        """Test authentication with JWT token"""
        mock_user = Mock(spec=User)
        mock_user.id = "user123"
        mock_user.organization_id = "org456"

        request = Mock()
        request.session = {}  # Mock empty session
        db = Mock(spec=Session)
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="jwt-token")

        # Mock the get_user_from_jwt function directly since it has complex internal logic
        with patch(
            "rhesis.backend.app.auth.auth_utils.get_user_from_jwt", return_value=mock_user
        ) as mock_get_jwt_user:
            # Mock get_current_user to return None (no session auth)
            with patch("rhesis.backend.app.auth.auth_utils.get_current_user", return_value=None):
                result = pytest.run(
                    get_authenticated_user_with_context(
                        request, credentials=credentials, secret_key="secret"
                    )
                )

                assert result == mock_user
                mock_get_jwt_user.assert_called_once_with("jwt-token", "secret")

    def test_get_authenticated_user_without_context(self):
        """Test authentication with without_context flag (still calls set_tenant)"""
        mock_user = Mock(spec=User)
        mock_user.id = "user123"
        mock_user.organization_id = None  # No organization, but without_context=True allows this

        request = Mock()
        request.session = {"user_id": "user123"}  # Mock session
        db = Mock(spec=Session)

        # Mock get_current_user directly to return user without organization
        with patch(
            "rhesis.backend.app.auth.auth_utils.get_current_user", return_value=mock_user
        ) as mock_get_current:
            result = pytest.run(get_authenticated_user_with_context(request, without_context=True))

            assert result == mock_user
            mock_get_current.assert_called_once_with(request)

    def test_get_authenticated_user_no_user_found(self):
        """Test authentication when no user is found"""
        request = Mock()
        db = Mock(spec=Session)

        with patch("rhesis.backend.app.auth.auth_utils.get_current_user", return_value=None):
            result = pytest.run(get_authenticated_user_with_context(request))
            assert result is None


@pytest.fixture
def mock_async():
    """Fixture to handle async function testing"""
    import asyncio

    def run_async(coro):
        """Helper to run async functions in tests"""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    return run_async


# Add the run helper to pytest namespace for convenience
pytest.run = (
    lambda coro: pytest.run_async_helper(coro) if hasattr(pytest, "run_async_helper") else None
)


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
    if hasattr(pytest, "run"):
        delattr(pytest, "run")
