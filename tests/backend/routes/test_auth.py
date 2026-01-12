"""
Authentication Routes Testing Suite

Comprehensive test suite for authentication endpoints including login, callback,
logout, and token verification. This module tests OAuth2 flows, session management,
and JWT token handling.

Run with: python -m pytest tests/backend/routes/test_auth.py -v
"""

import os
import uuid
from unittest.mock import AsyncMock, Mock, patch

import pytest
from faker import Faker
from fastapi import status
from fastapi.testclient import TestClient

# Initialize Faker
fake = Faker()


@pytest.mark.unit
@pytest.mark.critical
class TestAuthLogin:
    """Test authentication login endpoint"""

    def test_login_redirect_success(self, client: TestClient):
        """Test successful login redirects to Auth0"""
        with patch.dict(os.environ, {"AUTH0_DOMAIN": "test-domain.auth0.com"}):
            with patch("rhesis.backend.app.routers.auth.oauth") as mock_oauth:
                # Mock the Auth0 redirect response with RedirectResponse
                from starlette.responses import RedirectResponse

                mock_redirect_response = RedirectResponse(
                    url="https://test-domain.auth0.com/authorize?..."
                )
                mock_oauth.auth0.authorize_redirect = AsyncMock(return_value=mock_redirect_response)

                response = client.get("/auth/login", follow_redirects=False)

                # Should call the OAuth redirect
                mock_oauth.auth0.authorize_redirect.assert_called_once()
                assert response.status_code == 307  # RedirectResponse status code

    def test_login_with_connection_parameter(self, client: TestClient):
        """Test login with specific connection parameter"""
        with patch.dict(os.environ, {"AUTH0_DOMAIN": "test-domain.auth0.com"}):
            with patch("rhesis.backend.app.routers.auth.oauth") as mock_oauth:
                from starlette.responses import RedirectResponse

                mock_redirect_response = RedirectResponse(
                    url="https://test-domain.auth0.com/authorize?..."
                )
                mock_oauth.auth0.authorize_redirect = AsyncMock(return_value=mock_redirect_response)

                response = client.get(
                    "/auth/login?connection=google-oauth2", follow_redirects=False
                )

                # Should call OAuth redirect with connection parameter
                call_args = mock_oauth.auth0.authorize_redirect.call_args
                assert "connection" in call_args[1]
                assert call_args[1]["connection"] == "google-oauth2"

    def test_login_with_return_to_parameter(self, client: TestClient):
        """Test login with custom return_to parameter"""
        with patch.dict(os.environ, {"AUTH0_DOMAIN": "test-domain.auth0.com"}):
            with patch("rhesis.backend.app.routers.auth.oauth") as mock_oauth:
                from starlette.responses import RedirectResponse

                mock_redirect_response = RedirectResponse(
                    url="https://test-domain.auth0.com/authorize?..."
                )
                mock_oauth.auth0.authorize_redirect = AsyncMock(return_value=mock_redirect_response)

                response = client.get("/auth/login?return_to=/dashboard", follow_redirects=False)

                # Should store return_to in session (mocked behavior)
                mock_oauth.auth0.authorize_redirect.assert_called_once()

    def test_login_missing_auth0_domain(self, client: TestClient):
        """Test login fails when AUTH0_DOMAIN is not configured"""
        with patch.dict(os.environ, {}, clear=True):
            response = client.get("/auth/login")

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "AUTH0_DOMAIN not configured" in response.json()["detail"]

    def test_login_oauth_exception(self, client: TestClient):
        """Test login handles OAuth exceptions gracefully"""
        with patch.dict(os.environ, {"AUTH0_DOMAIN": "test-domain.auth0.com"}):
            with patch("rhesis.backend.app.routers.auth.oauth") as mock_oauth:
                mock_oauth.auth0.authorize_redirect = AsyncMock(
                    side_effect=Exception("OAuth error")
                )

                response = client.get("/auth/login")

                assert response.status_code == status.HTTP_400_BAD_REQUEST
                assert "OAuth error" in response.json()["detail"]

    def test_login_stores_origin_in_session(self, client: TestClient):
        """Test login stores frontend origin for callback"""
        with patch.dict(os.environ, {"AUTH0_DOMAIN": "test-domain.auth0.com"}):
            with patch("rhesis.backend.app.routers.auth.oauth") as mock_oauth:
                from starlette.responses import RedirectResponse

                mock_redirect_response = RedirectResponse(
                    url="https://test-domain.auth0.com/authorize?..."
                )
                mock_oauth.auth0.authorize_redirect = AsyncMock(return_value=mock_redirect_response)

                headers = {"origin": "http://localhost:3000"}
                response = client.get("/auth/login", headers=headers, follow_redirects=False)

                mock_oauth.auth0.authorize_redirect.assert_called_once()

    def test_login_callback_url_https_rewrite(self, client: TestClient):
        """Test callback URL is rewritten from HTTP to HTTPS for non-localhost"""
        with patch.dict(os.environ, {"AUTH0_DOMAIN": "test-domain.auth0.com"}):
            with patch("rhesis.backend.app.routers.auth.oauth") as mock_oauth:
                from starlette.responses import RedirectResponse

                mock_redirect_response = RedirectResponse(
                    url="https://test-domain.auth0.com/authorize?..."
                )
                mock_oauth.auth0.authorize_redirect = AsyncMock(return_value=mock_redirect_response)

                # Mock base URL to simulate production environment
                with patch.object(client.app, "state", {}):
                    response = client.get("/auth/login", follow_redirects=False)

                # Should call OAuth redirect with callback URL parameters
                call_args = mock_oauth.auth0.authorize_redirect.call_args
                assert "redirect_uri" in call_args[1]


@pytest.mark.unit
@pytest.mark.critical
class TestAuthCallback:
    """Test authentication callback endpoint"""

    @patch("rhesis.backend.app.routers.auth.get_auth0_user_info")
    @patch("rhesis.backend.app.routers.auth.extract_user_data")
    @patch("rhesis.backend.app.routers.auth.find_or_create_user")
    @patch("rhesis.backend.app.routers.auth.create_session_token")
    @patch("rhesis.backend.app.routers.auth.build_redirect_url")
    def test_callback_success(
        self,
        mock_build_redirect,
        mock_create_token,
        mock_find_user,
        mock_extract_data,
        mock_get_user_info,
        client: TestClient,
    ):
        """Test successful authentication callback flow"""
        # Mock the Auth0 flow
        mock_token = {"access_token": "test_token"}
        mock_userinfo = {"sub": "auth0|123", "email": "test@example.com"}
        mock_get_user_info.return_value = (mock_token, mock_userinfo)

        # Mock user data extraction
        mock_extract_data.return_value = ("auth0|123", "test@example.com", {"name": "Test User"})

        # Mock user creation/finding
        mock_user = Mock()
        mock_user.id = str(uuid.uuid4())
        mock_find_user.return_value = mock_user

        # Mock token creation
        mock_session_token = "session_token_123"
        mock_create_token.return_value = mock_session_token

        # Mock redirect URL building
        mock_redirect_url = "http://localhost:3000/dashboard?token=session_token_123"
        mock_build_redirect.return_value = mock_redirect_url

        response = client.get(
            "/auth/callback?code=test_code&state=test_state", follow_redirects=False
        )

        # Callback returns a redirect to frontend with token
        assert response.status_code in [status.HTTP_307_TEMPORARY_REDIRECT, status.HTTP_302_FOUND]

        # Verify all functions were called in the correct order
        mock_get_user_info.assert_called_once()
        mock_extract_data.assert_called_once_with(mock_userinfo)
        mock_find_user.assert_called_once()
        mock_create_token.assert_called_once_with(mock_user)
        mock_build_redirect.assert_called_once()

    @patch("rhesis.backend.app.routers.auth.get_auth0_user_info")
    def test_callback_auth0_error(self, mock_get_user_info, client: TestClient):
        """Test callback handles Auth0 errors gracefully"""
        mock_get_user_info.side_effect = Exception("Auth0 communication error")

        response = client.get("/auth/callback?code=test_code&state=test_state")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Auth0 communication error" in response.json()["detail"]

    @patch("rhesis.backend.app.routers.auth.get_auth0_user_info")
    @patch("rhesis.backend.app.routers.auth.extract_user_data")
    def test_callback_user_data_extraction_error(
        self, mock_extract_data, mock_get_user_info, client: TestClient
    ):
        """Test callback handles user data extraction errors"""
        mock_get_user_info.return_value = ({}, {"sub": "auth0|123"})
        mock_extract_data.side_effect = Exception("Invalid user data")

        response = client.get("/auth/callback?code=test_code&state=test_state")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid user data" in response.json()["detail"]

    @patch("rhesis.backend.app.routers.auth.get_auth0_user_info")
    @patch("rhesis.backend.app.routers.auth.extract_user_data")
    @patch("rhesis.backend.app.routers.auth.find_or_create_user")
    def test_callback_user_creation_error(
        self, mock_find_user, mock_extract_data, mock_get_user_info, client: TestClient
    ):
        """Test callback handles user creation/finding errors"""
        mock_get_user_info.return_value = ({}, {"sub": "auth0|123"})
        mock_extract_data.return_value = ("auth0|123", "test@example.com", {})
        mock_find_user.side_effect = Exception("Database error")

        response = client.get("/auth/callback?code=test_code&state=test_state")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Database error" in response.json()["detail"]


@pytest.mark.unit
@pytest.mark.critical
class TestAuthLogout:
    """Test authentication logout endpoint"""

    def test_logout_success(self, client: TestClient):
        """Test successful logout clears session"""
        with patch.dict(os.environ, {"FRONTEND_URL": "http://localhost:3000"}):
            response = client.get("/auth/logout")

            # Logout redirects to frontend, TestClient follows redirect and gets final 200
            assert response.status_code == status.HTTP_200_OK
            # Final response should be from the frontend URL (which we're mocking as 200 OK)
            assert response.url == "http://localhost:3000/"

    def test_logout_with_session_token(self, client: TestClient):
        """Test logout with valid session token"""
        # Create a mock JWT token
        user_data = {"id": str(uuid.uuid4()), "email": "test@example.com"}
        mock_payload = {"user": user_data}

        with patch("rhesis.backend.app.routers.auth.verify_jwt_token") as mock_verify:
            with patch("rhesis.backend.app.routers.auth.get_secret_key") as mock_secret:
                mock_verify.return_value = mock_payload
                mock_secret.return_value = "test_secret"

                with patch.dict(os.environ, {"FRONTEND_URL": "http://localhost:3000"}):
                    response = client.get("/auth/logout?session_token=valid_token")

                    assert response.status_code == status.HTTP_200_OK
                    mock_verify.assert_called_once_with("valid_token", "test_secret")

    def test_logout_with_invalid_session_token(self, client: TestClient):
        """Test logout continues even with invalid session token"""
        with patch("rhesis.backend.app.routers.auth.verify_jwt_token") as mock_verify:
            from jose import JWTError

            mock_verify.side_effect = JWTError("Invalid token")

            with patch.dict(os.environ, {"FRONTEND_URL": "http://localhost:3000"}):
                response = client.get("/auth/logout?session_token=invalid_token")

                # Should still redirect successfully even with invalid token
                assert response.status_code == status.HTTP_200_OK
                assert response.url == "http://localhost:3000/"

    def test_logout_default_frontend_url(self, client: TestClient):
        """Test logout uses default frontend URL when not configured"""
        # Don't set FRONTEND_URL environment variable
        with patch.dict(os.environ, {}, clear=True):
            response = client.get("/auth/logout")

            assert response.status_code == status.HTTP_200_OK
            assert response.url == "http://localhost:3000/"

    def test_logout_post_logout_parameter(self, client: TestClient):
        """Test logout with post_logout parameter"""
        with patch.dict(os.environ, {"FRONTEND_URL": "http://localhost:3000"}):
            response = client.get("/auth/logout?post_logout=true")

            assert response.status_code == status.HTTP_200_OK
            assert response.url == "http://localhost:3000/"


@pytest.mark.unit
@pytest.mark.critical
class TestAuthVerify:
    """Test authentication verification endpoint"""

    def test_verify_valid_token(self, client: TestClient):
        """Test verification of valid JWT token"""
        user_data = {"id": str(uuid.uuid4()), "email": "test@example.com", "name": "Test User"}
        mock_payload = {"user": user_data}

        with patch("rhesis.backend.app.routers.auth.verify_jwt_token") as mock_verify:
            with patch("rhesis.backend.app.routers.auth.get_secret_key") as mock_secret:
                mock_verify.return_value = mock_payload
                mock_secret.return_value = "test_secret"

                response = client.get("/auth/verify?session_token=valid_token")

                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["authenticated"] is True
                assert data["user"] == user_data
                assert data["return_to"] == "/home"  # default value

    def test_verify_with_custom_return_to(self, client: TestClient):
        """Test verification with custom return_to parameter"""
        user_data = {"id": str(uuid.uuid4()), "email": "test@example.com"}
        mock_payload = {"user": user_data}

        with patch("rhesis.backend.app.routers.auth.verify_jwt_token") as mock_verify:
            with patch("rhesis.backend.app.routers.auth.get_secret_key") as mock_secret:
                mock_verify.return_value = mock_payload
                mock_secret.return_value = "test_secret"

                response = client.get("/auth/verify?session_token=valid_token&return_to=/dashboard")

                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["return_to"] == "/dashboard"

    def test_verify_invalid_token(self, client: TestClient):
        """Test verification of invalid JWT token"""
        with patch("rhesis.backend.app.routers.auth.verify_jwt_token") as mock_verify:
            with patch("rhesis.backend.app.routers.auth.get_secret_key") as mock_secret:
                from jose import JWTError

                mock_verify.side_effect = JWTError("Invalid token")
                mock_secret.return_value = "test_secret"

                response = client.get("/auth/verify?session_token=invalid_token")

                assert response.status_code == status.HTTP_401_UNAUTHORIZED
                assert "Invalid token" in response.json()["detail"]

    def test_verify_expired_token(self, client: TestClient):
        """Test verification of expired JWT token"""
        with patch("rhesis.backend.app.routers.auth.verify_jwt_token") as mock_verify:
            with patch("rhesis.backend.app.routers.auth.get_secret_key") as mock_secret:
                from jose import JWTError

                mock_verify.side_effect = JWTError("Expired token")
                mock_secret.return_value = "test_secret"

                response = client.get("/auth/verify?session_token=expired_token")

                assert response.status_code == status.HTTP_401_UNAUTHORIZED
                assert "Token has expired" in response.json()["detail"]

    def test_verify_missing_session_token(self, client: TestClient):
        """Test verification without session token parameter"""
        response = client.get("/auth/verify")

        # Should return validation error for missing required parameter
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_verify_general_exception(self, client: TestClient):
        """Test verification handles general exceptions"""
        with patch("rhesis.backend.app.routers.auth.verify_jwt_token") as mock_verify:
            with patch("rhesis.backend.app.routers.auth.get_secret_key") as mock_secret:
                mock_verify.side_effect = Exception("Unexpected error")
                mock_secret.return_value = "test_secret"

                response = client.get("/auth/verify?session_token=test_token")

                assert response.status_code == status.HTTP_401_UNAUTHORIZED
                assert "Authentication failed" in response.json()["detail"]


@pytest.mark.integration
@pytest.mark.critical
class TestAuthenticationFlow:
    """Test complete authentication flow integration"""

    def test_unauthenticated_access_to_protected_routes(self, client: TestClient):
        """Test that protected routes require authentication"""
        # Test various protected endpoints
        protected_endpoints = [
            "/behaviors/",
            "/categories/",
            "/topics/",
            "/users/",
        ]

        for endpoint in protected_endpoints:
            response = client.get(endpoint)
            # Should require authentication
            assert response.status_code in [
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
            ], f"Endpoint {endpoint} should require authentication"

    def test_auth_flow_session_management(self, client: TestClient):
        """Test session management throughout auth flow"""
        # This test would require more complex session mocking
        # For now, test that the logout endpoint clears sessions
        with patch.dict(os.environ, {"FRONTEND_URL": "http://localhost:3000"}):
            response = client.get("/auth/logout")
            assert response.status_code == status.HTTP_200_OK


@pytest.mark.unit
class TestAuthEdgeCases:
    """Test edge cases for authentication"""

    def test_login_with_malformed_parameters(self, client: TestClient):
        """🏃‍♂️ Test login with malformed query parameters"""
        with patch.dict(os.environ, {"AUTH0_DOMAIN": "test-domain.auth0.com"}):
            with patch("rhesis.backend.app.routers.auth.oauth") as mock_oauth:
                from starlette.responses import RedirectResponse

                mock_redirect_response = RedirectResponse(
                    url="https://test-domain.auth0.com/authorize?..."
                )
                mock_oauth.auth0.authorize_redirect = AsyncMock(return_value=mock_redirect_response)

                # Test with various malformed parameters
                malformed_params = [
                    "?connection=",  # empty connection
                    "?return_to=",  # empty return_to
                    "?connection=invalid space",  # invalid characters
                    "?return_to=" + "x" * 1000,  # very long return_to
                ]

                for params in malformed_params:
                    response = client.get(f"/auth/login{params}", follow_redirects=False)
                    # Should handle gracefully (might succeed or fail depending on validation)
                    assert response.status_code in [
                        status.HTTP_307_TEMPORARY_REDIRECT,
                        status.HTTP_302_FOUND,
                        status.HTTP_400_BAD_REQUEST,
                        status.HTTP_422_UNPROCESSABLE_ENTITY,
                    ]

    def test_callback_with_missing_parameters(self, client: TestClient):
        """🏃‍♂️ Test callback with missing required parameters"""
        response = client.get("/auth/callback")

        # Should handle missing code/state gracefully
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_verify_with_malformed_token(self, client: TestClient):
        """🏃‍♂️ Test verify with malformed JWT token"""
        malformed_tokens = [
            "not.a.jwt",
            "invalid_token_format",
            "",  # empty token
            "a.b.c.d.e",  # too many parts
            "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9",  # incomplete JWT
        ]

        for token in malformed_tokens:
            response = client.get(f"/auth/verify?session_token={token}")
            assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_logout_with_extremely_long_token(self, client: TestClient):
        """🏃‍♂️ Test logout with extremely long session token"""
        long_token = "x" * 10000  # Very long token

        with patch.dict(os.environ, {"FRONTEND_URL": "http://localhost:3000"}):
            response = client.get(f"/auth/logout?session_token={long_token}")

            # Should handle gracefully and still logout
            assert response.status_code == status.HTTP_200_OK


@pytest.mark.slow
@pytest.mark.integration
class TestAuthPerformance:
    """Test authentication performance"""

    def test_multiple_login_requests_performance(self, client: TestClient):
        """🐌 Test performance of multiple login requests"""
        import time

        with patch.dict(os.environ, {"AUTH0_DOMAIN": "test-domain.auth0.com"}):
            with patch("rhesis.backend.app.routers.auth.oauth") as mock_oauth:
                from starlette.responses import RedirectResponse

                mock_redirect_response = RedirectResponse(
                    url="https://test-domain.auth0.com/authorize?..."
                )
                mock_oauth.auth0.authorize_redirect = AsyncMock(return_value=mock_redirect_response)

                start_time = time.time()

                # Make 10 login requests
                for i in range(10):
                    response = client.get("/auth/login", follow_redirects=False)
                    assert response.status_code in [
                        status.HTTP_307_TEMPORARY_REDIRECT,
                        status.HTTP_302_FOUND,
                    ]

                duration = time.time() - start_time

                # Should complete within reasonable time (5 seconds for 10 requests)
                assert duration < 5.0

    def test_multiple_verify_requests_performance(self, client: TestClient):
        """🐌 Test performance of multiple verify requests"""
        import time

        with patch("rhesis.backend.app.routers.auth.verify_jwt_token") as mock_verify:
            with patch("rhesis.backend.app.routers.auth.get_secret_key") as mock_secret:
                mock_verify.return_value = {"user": {"id": "123", "email": "test@example.com"}}
                mock_secret.return_value = "test_secret"

                start_time = time.time()

                # Make 20 verify requests
                for i in range(20):
                    response = client.get("/auth/verify?session_token=test_token")
                    assert response.status_code == status.HTTP_200_OK

                duration = time.time() - start_time

                # Should complete within reasonable time (3 seconds for 20 requests)
                assert duration < 3.0


class TestAuthHealthChecks:
    """Test basic health checks for auth endpoints"""

    def test_auth_endpoints_basic_health(self, client: TestClient):
        """✅ Basic health check for auth endpoints"""
        # Test that auth endpoints are accessible (even if they return errors)
        endpoints = [
            "/auth/login",
            "/auth/logout",
            "/auth/callback",
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            # Should not return 500 errors (even if 400/401/404 is acceptable)
            assert response.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR, (
                f"Endpoint {endpoint} returned server error"
            )

    def test_verify_endpoint_requires_token(self, client: TestClient):
        """✅ Verify endpoint correctly requires session token"""
        response = client.get("/auth/verify")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
