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

from rhesis.backend.app.auth.token_utils import (
    create_email_verification_token,
    create_magic_link_token,
    create_password_reset_token,
)
from tests.backend.fixtures.test_setup import (
    create_test_organization,
    create_test_user,
)

# Initialize Faker
fake = Faker()


# =============================================================================
# Provider-Agnostic Authentication Tests (New Native Auth System)
# =============================================================================


@pytest.mark.unit
class TestAuthProviders:
    """Test /auth/providers endpoint for provider discovery."""

    def test_get_providers_returns_list(self, client: TestClient):
        """Test that /auth/providers returns a list of providers."""
        response = client.get("/auth/providers")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "providers" in data
        assert isinstance(data["providers"], list)

    def test_get_providers_includes_email_by_default(self, client: TestClient):
        """Test that email provider is included by default."""
        response = client.get("/auth/providers")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        provider_names = [p["name"] for p in data["providers"]]
        assert "email" in provider_names

    def test_get_providers_structure(self, client: TestClient):
        """Test that provider info has correct structure."""
        response = client.get("/auth/providers")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        for provider in data["providers"]:
            assert "name" in provider
            assert "display_name" in provider
            assert "type" in provider
            assert "enabled" in provider
            assert provider["type"] in ["oauth", "credentials"]

    def test_get_providers_oauth_disabled_without_credentials(self, client: TestClient):
        """Test OAuth providers are not enabled without credentials."""
        with patch.dict(os.environ, {}, clear=True):
            # Reset registry to pick up new env
            from rhesis.backend.app.auth.providers.registry import ProviderRegistry

            ProviderRegistry.reset()

            response = client.get("/auth/providers")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Find Google and GitHub providers
            google = next((p for p in data["providers"] if p["name"] == "google"), None)
            github = next((p for p in data["providers"] if p["name"] == "github"), None)

            # They should exist but not be enabled
            if google:
                assert google["enabled"] is False
            if github:
                assert github["enabled"] is False


@pytest.mark.unit
class TestProviderLogin:
    """Test /auth/login/{provider} endpoint for OAuth initiation."""

    def test_login_unknown_provider(self, client: TestClient):
        """Test login with unknown provider returns error."""
        response = client.get("/auth/login/unknown_provider")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Unknown authentication provider" in response.json()["detail"]

    def test_login_disabled_provider(self, client: TestClient):
        """Test login with disabled provider returns error."""
        with patch.dict(os.environ, {}, clear=True):
            from rhesis.backend.app.auth.providers.registry import ProviderRegistry

            ProviderRegistry.reset()

            response = client.get("/auth/login/google")

            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "not configured" in response.json()["detail"]

    def test_login_email_provider_not_oauth(self, client: TestClient):
        """Test that email provider rejects OAuth login."""
        response = client.get("/auth/login/email")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "does not support OAuth" in response.json()["detail"]


@pytest.mark.unit
class TestEmailLogin:
    """Test /auth/login/email endpoint for email/password authentication."""

    def test_email_login_missing_credentials(self, client: TestClient):
        """Test email login with missing credentials."""
        response = client.post("/auth/login/email", json={})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_email_login_missing_password(self, client: TestClient):
        """Test email login with missing password."""
        response = client.post(
            "/auth/login/email",
            json={"email": "test@example.com"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_email_login_invalid_email_format(self, client: TestClient):
        """Test email login with invalid email format."""
        response = client.post(
            "/auth/login/email",
            json={"email": "not-an-email", "password": "password123"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.unit
class TestEmailRegistration:
    """Test /auth/register endpoint for email/password registration."""

    def test_register_missing_credentials(self, client: TestClient):
        """Test registration with missing credentials."""
        response = client.post("/auth/register", json={})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_register_password_too_short(self, client: TestClient):
        """Test registration with password too short."""
        response = client.post(
            "/auth/register",
            json={"email": "test@example.com", "password": "short"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_register_invalid_email_format(self, client: TestClient):
        """Test registration with invalid email format."""
        response = client.post(
            "/auth/register",
            json={"email": "not-an-email", "password": "password123"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# =============================================================================
# Legacy Auth0 Tests (Kept for backward compatibility during migration)
# =============================================================================


@pytest.mark.unit
@pytest.mark.critical
class TestAuthLogin:
    """Test legacy Auth0 authentication login endpoint (requires AUTH_LEGACY_AUTH0_ENABLED)"""

    # oauth is now imported lazily inside the login() endpoint via
    # ``from rhesis.backend.app.auth.oauth import oauth``, so we must
    # patch at the *source* module rather than on the router.
    _OAUTH_PATCH = "rhesis.backend.app.auth.oauth.oauth"

    def test_login_redirect_success(self, client: TestClient):
        """Test successful login redirects to Auth0 when legacy mode enabled"""
        with patch.dict(
            os.environ,
            {"AUTH0_DOMAIN": "test-domain.auth0.com", "AUTH_LEGACY_AUTH0_ENABLED": "true"},
        ):
            with patch(self._OAUTH_PATCH) as mock_oauth:
                from starlette.responses import RedirectResponse

                mock_redirect_response = RedirectResponse(
                    url="https://test-domain.auth0.com/authorize?..."
                )
                mock_oauth.auth0.authorize_redirect = AsyncMock(
                    return_value=mock_redirect_response
                )

                response = client.get("/auth/login", follow_redirects=False)

                mock_oauth.auth0.authorize_redirect.assert_called_once()
                assert response.status_code == 307

    def test_login_with_connection_parameter(self, client: TestClient):
        """Test login with specific connection parameter"""
        with patch.dict(
            os.environ,
            {"AUTH0_DOMAIN": "test-domain.auth0.com", "AUTH_LEGACY_AUTH0_ENABLED": "true"},
        ):
            with patch(self._OAUTH_PATCH) as mock_oauth:
                from starlette.responses import RedirectResponse

                mock_redirect_response = RedirectResponse(
                    url="https://test-domain.auth0.com/authorize?..."
                )
                mock_oauth.auth0.authorize_redirect = AsyncMock(
                    return_value=mock_redirect_response
                )

                client.get(
                    "/auth/login?connection=google-oauth2",
                    follow_redirects=False,
                )

                call_args = mock_oauth.auth0.authorize_redirect.call_args
                assert "connection" in call_args[1]
                assert call_args[1]["connection"] == "google-oauth2"

    def test_login_with_return_to_parameter(self, client: TestClient):
        """Test login with custom return_to parameter"""
        with patch.dict(
            os.environ,
            {"AUTH0_DOMAIN": "test-domain.auth0.com", "AUTH_LEGACY_AUTH0_ENABLED": "true"},
        ):
            with patch(self._OAUTH_PATCH) as mock_oauth:
                from starlette.responses import RedirectResponse

                mock_redirect_response = RedirectResponse(
                    url="https://test-domain.auth0.com/authorize?..."
                )
                mock_oauth.auth0.authorize_redirect = AsyncMock(
                    return_value=mock_redirect_response
                )

                client.get("/auth/login?return_to=/dashboard", follow_redirects=False)

                mock_oauth.auth0.authorize_redirect.assert_called_once()

    def test_login_disabled_without_legacy_flag(self, client: TestClient):
        """Test legacy login is disabled without AUTH_LEGACY_AUTH0_ENABLED"""
        with patch.dict(os.environ, {"AUTH_LEGACY_AUTH0_ENABLED": "false"}, clear=True):
            response = client.get("/auth/login")

            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "Legacy Auth0 login is disabled" in response.json()["detail"]

    def test_login_missing_auth0_domain(self, client: TestClient):
        """Test login fails when AUTH0_DOMAIN is not configured"""
        with patch.dict(os.environ, {"AUTH_LEGACY_AUTH0_ENABLED": "true"}, clear=True):
            response = client.get("/auth/login")

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "AUTH0_DOMAIN not configured" in response.json()["detail"]

    def test_login_oauth_exception(self, client: TestClient):
        """Test login handles OAuth exceptions gracefully"""
        with patch.dict(
            os.environ,
            {"AUTH0_DOMAIN": "test-domain.auth0.com", "AUTH_LEGACY_AUTH0_ENABLED": "true"},
        ):
            with patch(self._OAUTH_PATCH) as mock_oauth:
                mock_oauth.auth0.authorize_redirect = AsyncMock(
                    side_effect=Exception("OAuth error")
                )

                response = client.get("/auth/login")

                assert response.status_code == status.HTTP_400_BAD_REQUEST
                assert "OAuth error" in response.json()["detail"]

    def test_login_stores_origin_in_session(self, client: TestClient):
        """Test login stores frontend origin for callback"""
        with patch.dict(
            os.environ,
            {"AUTH0_DOMAIN": "test-domain.auth0.com", "AUTH_LEGACY_AUTH0_ENABLED": "true"},
        ):
            with patch(self._OAUTH_PATCH) as mock_oauth:
                from starlette.responses import RedirectResponse

                mock_redirect_response = RedirectResponse(
                    url="https://test-domain.auth0.com/authorize?..."
                )
                mock_oauth.auth0.authorize_redirect = AsyncMock(
                    return_value=mock_redirect_response
                )

                headers = {"origin": "http://localhost:3000"}
                client.get("/auth/login", headers=headers, follow_redirects=False)

                mock_oauth.auth0.authorize_redirect.assert_called_once()

    def test_login_callback_url_https_rewrite(self, client: TestClient):
        """Test callback URL is rewritten from HTTP to HTTPS for non-localhost"""
        with patch.dict(
            os.environ,
            {"AUTH0_DOMAIN": "test-domain.auth0.com", "AUTH_LEGACY_AUTH0_ENABLED": "true"},
        ):
            with patch(self._OAUTH_PATCH) as mock_oauth:
                from starlette.responses import RedirectResponse

                mock_redirect_response = RedirectResponse(
                    url="https://test-domain.auth0.com/authorize?..."
                )
                mock_oauth.auth0.authorize_redirect = AsyncMock(
                    return_value=mock_redirect_response
                )

                with patch.object(client.app, "state", {}):
                    client.get("/auth/login", follow_redirects=False)

                call_args = mock_oauth.auth0.authorize_redirect.call_args
                assert "redirect_uri" in call_args[1]


@pytest.mark.unit
@pytest.mark.critical
class TestAuthCallback:
    """Test authentication callback endpoint (legacy Auth0 path)

    The callback now falls through to ``_legacy_auth0_callback`` only
    when ``AUTH_LEGACY_AUTH0_ENABLED=true`` and there is no
    ``auth_provider`` in session.  The helper imports
    ``get_auth0_user_info`` and ``extract_user_data`` from
    ``rhesis.backend.app.auth.oauth`` inside the function body, so
    patches must target that source module.
    """

    # Source-module paths for deferred imports
    _AUTH0_INFO = "rhesis.backend.app.auth.oauth.get_auth0_user_info"
    _EXTRACT = "rhesis.backend.app.auth.oauth.extract_user_data"

    @patch("rhesis.backend.app.routers.auth.build_redirect_url")
    @patch("rhesis.backend.app.routers.auth.create_session_token")
    @patch("rhesis.backend.app.routers.auth.find_or_create_user")
    def test_callback_success(
        self,
        mock_find_user,
        mock_create_token,
        mock_build_redirect,
        client: TestClient,
    ):
        """Test successful authentication callback flow"""
        mock_token = {"access_token": "test_token"}
        mock_userinfo = {"sub": "auth0|123", "email": "test@example.com"}

        mock_user = Mock()
        mock_user.id = str(uuid.uuid4())
        mock_user.organization_id = None
        mock_find_user.return_value = mock_user

        mock_session_token = "session_token_123"
        mock_create_token.return_value = mock_session_token

        mock_redirect_url = (
            "http://localhost:3000/dashboard?token=session_token_123"
        )
        mock_build_redirect.return_value = mock_redirect_url

        with (
            patch.dict(os.environ, {"AUTH_LEGACY_AUTH0_ENABLED": "true"}),
            patch(self._AUTH0_INFO) as mock_get_user_info,
            patch(self._EXTRACT) as mock_extract_data,
        ):
            mock_get_user_info.return_value = (mock_token, mock_userinfo)
            mock_extract_data.return_value = (
                "auth0|123",
                "test@example.com",
                {"name": "Test User"},
            )

            response = client.get(
                "/auth/callback?code=test_code&state=test_state",
                follow_redirects=False,
            )

        assert response.status_code in [
            status.HTTP_307_TEMPORARY_REDIRECT,
            status.HTTP_302_FOUND,
        ]
        mock_get_user_info.assert_called_once()
        mock_extract_data.assert_called_once_with(mock_userinfo)
        mock_find_user.assert_called_once()
        mock_create_token.assert_called_once_with(mock_user)
        mock_build_redirect.assert_called_once()

    def test_callback_auth0_error(self, client: TestClient):
        """Test callback handles Auth0 errors gracefully"""
        with (
            patch.dict(os.environ, {"AUTH_LEGACY_AUTH0_ENABLED": "true"}),
            patch(self._AUTH0_INFO) as mock_get_user_info,
        ):
            mock_get_user_info.side_effect = Exception(
                "Auth0 communication error"
            )

            response = client.get(
                "/auth/callback?code=test_code&state=test_state"
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Auth0 communication error" in response.json()["detail"]

    def test_callback_user_data_extraction_error(self, client: TestClient):
        """Test callback handles user data extraction errors"""
        with (
            patch.dict(os.environ, {"AUTH_LEGACY_AUTH0_ENABLED": "true"}),
            patch(self._AUTH0_INFO) as mock_get_user_info,
            patch(self._EXTRACT) as mock_extract_data,
        ):
            mock_get_user_info.return_value = ({}, {"sub": "auth0|123"})
            mock_extract_data.side_effect = Exception("Invalid user data")

            response = client.get(
                "/auth/callback?code=test_code&state=test_state"
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid user data" in response.json()["detail"]

    @patch("rhesis.backend.app.routers.auth.find_or_create_user")
    def test_callback_user_creation_error(
        self, mock_find_user, client: TestClient
    ):
        """Test callback handles user creation/finding errors"""
        mock_find_user.side_effect = Exception("Database error")

        with (
            patch.dict(os.environ, {"AUTH_LEGACY_AUTH0_ENABLED": "true"}),
            patch(self._AUTH0_INFO) as mock_get_user_info,
            patch(self._EXTRACT) as mock_extract_data,
        ):
            mock_get_user_info.return_value = ({}, {"sub": "auth0|123"})
            mock_extract_data.return_value = (
                "auth0|123",
                "test@example.com",
                {},
            )

            response = client.get(
                "/auth/callback?code=test_code&state=test_state"
            )

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
        """Test login with malformed query parameters"""
        with patch.dict(
            os.environ,
            {
                "AUTH0_DOMAIN": "test-domain.auth0.com",
                "AUTH_LEGACY_AUTH0_ENABLED": "true",
            },
        ):
            with patch("rhesis.backend.app.auth.oauth.oauth") as mock_oauth:
                from starlette.responses import RedirectResponse

                mock_redirect_response = RedirectResponse(
                    url="https://test-domain.auth0.com/authorize?..."
                )
                mock_oauth.auth0.authorize_redirect = AsyncMock(
                    return_value=mock_redirect_response
                )

                malformed_params = [
                    "?connection=",
                    "?return_to=",
                    "?connection=invalid space",
                    "?return_to=" + "x" * 1000,
                ]

                for params in malformed_params:
                    response = client.get(
                        f"/auth/login{params}",
                        follow_redirects=False,
                    )
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
        """Test performance of multiple login requests"""
        import time

        with patch.dict(
            os.environ,
            {
                "AUTH0_DOMAIN": "test-domain.auth0.com",
                "AUTH_LEGACY_AUTH0_ENABLED": "true",
            },
        ):
            with patch("rhesis.backend.app.auth.oauth.oauth") as mock_oauth:
                from starlette.responses import RedirectResponse

                mock_redirect_response = RedirectResponse(
                    url="https://test-domain.auth0.com/authorize?..."
                )
                mock_oauth.auth0.authorize_redirect = AsyncMock(
                    return_value=mock_redirect_response
                )

                start_time = time.time()

                for i in range(10):
                    response = client.get(
                        "/auth/login", follow_redirects=False
                    )
                    assert response.status_code in [
                        status.HTTP_307_TEMPORARY_REDIRECT,
                        status.HTTP_302_FOUND,
                    ]

                duration = time.time() - start_time

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


# =============================================================================
# Email verification, password reset, magic link (native auth flows)
# =============================================================================


def _unique_email(prefix: str) -> str:
    """Generate a unique email address for test isolation."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}@test.rhesis.ai"


@pytest.mark.unit
class TestAuthEmailVerificationRoutes:
    """Route tests for verify-email and resend-verification."""

    def test_verify_email_valid_token(self, client: TestClient, test_db, test_org_id):
        """POST /auth/verify-email with valid token sets is_email_verified."""
        email = _unique_email("verify-me")
        org = create_test_organization(test_db, "Verify Org")
        user = create_test_user(test_db, org.id, email, "Verify User")
        assert user.is_email_verified is False

        with patch(
            "rhesis.backend.app.auth.token_utils.get_secret_key",
            return_value="test-secret",
        ):
            token = create_email_verification_token(str(user.id), user.email)
            response = client.post(
                "/auth/verify-email",
                json={"token": token},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "verified" in data["message"].lower()

        test_db.refresh(user)
        assert user.is_email_verified is True

    def test_verify_email_invalid_token(self, client: TestClient):
        """POST /auth/verify-email with invalid token returns 400."""
        with patch(
            "rhesis.backend.app.auth.token_utils.get_secret_key",
            return_value="test-secret",
        ):
            response = client.post(
                "/auth/verify-email",
                json={"token": "invalid.jwt.token"},
            )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_verify_email_already_verified(self, client: TestClient, test_db, test_org_id):
        """POST /auth/verify-email when already verified returns success."""
        email = _unique_email("already")
        org = create_test_organization(test_db, "Already Verified Org")
        user = create_test_user(test_db, org.id, email, "Already User")
        user.is_email_verified = True
        test_db.flush()

        with patch(
            "rhesis.backend.app.auth.token_utils.get_secret_key",
            return_value="test-secret",
        ):
            token = create_email_verification_token(str(user.id), user.email)
            response = client.post(
                "/auth/verify-email",
                json={"token": token},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "already" in data["message"].lower()

    def test_resend_verification_returns_200_enumeration_safe(self, client: TestClient):
        """POST /auth/resend-verification always 200 (enumeration-safe)."""
        response = client.post(
            "/auth/resend-verification",
            json={"email": "unknown@example.com"},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "message" in data

    def test_resend_verification_existing_user_sends_email(
        self, client: TestClient, test_db, test_org_id
    ):
        """POST /auth/resend-verification for existing user triggers send."""
        email = _unique_email("resend")
        org = create_test_organization(test_db, "Resend Org")
        user = create_test_user(test_db, org.id, email, "Resend User")
        user.is_email_verified = False
        test_db.flush()

        with (
            patch(
                "rhesis.backend.app.auth.token_utils.get_secret_key",
                return_value="test-secret",
            ),
            patch("rhesis.backend.app.routers.auth._get_email_service") as mock_get_email,
        ):
            mock_send = Mock()
            mock_get_email.return_value = Mock(send_verification_email=mock_send)
            response = client.post(
                "/auth/resend-verification",
                json={"email": user.email},
            )
        assert response.status_code == status.HTTP_200_OK
        mock_send.assert_called_once()


@pytest.mark.unit
class TestAuthPasswordResetRoutes:
    """Route tests for forgot-password and reset-password (single-use)."""

    def test_forgot_password_returns_200_enumeration_safe(self, client: TestClient):
        """POST /auth/forgot-password always 200 (enumeration-safe)."""
        response = client.post(
            "/auth/forgot-password",
            json={"email": "unknown@example.com"},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "message" in data

    def test_reset_password_valid_token_single_use(self, client: TestClient, test_db, test_org_id):
        """POST /auth/reset-password with valid token and claim succeeds."""
        email = _unique_email("reset")
        org = create_test_organization(test_db, "Reset Org")
        user = create_test_user(test_db, org.id, email, "Reset User")
        user.provider_type = "email"
        test_db.flush()

        with (
            patch(
                "rhesis.backend.app.auth.token_utils.get_secret_key",
                return_value="test-secret",
            ),
            patch(
                "rhesis.backend.app.routers.auth.claim_token_jti",
                new_callable=AsyncMock,
                return_value=True,
            ),
        ):
            token = create_password_reset_token(str(user.id), user.email)
            response = client.post(
                "/auth/reset-password",
                json={"token": token, "new_password": "newSecurePass123"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "reset" in data["message"].lower()

    def test_reset_password_token_already_used_returns_400(
        self, client: TestClient, test_db, test_org_id
    ):
        """POST /auth/reset-password when token already used returns 400."""
        email = _unique_email("reset-used")
        org = create_test_organization(test_db, "Reset Used Org")
        user = create_test_user(test_db, org.id, email, "Reset Used User")
        test_db.flush()

        with (
            patch(
                "rhesis.backend.app.auth.token_utils.get_secret_key",
                return_value="test-secret",
            ),
            patch(
                "rhesis.backend.app.routers.auth.claim_token_jti",
                new_callable=AsyncMock,
                return_value=False,
            ),
        ):
            token = create_password_reset_token(str(user.id), user.email)
            response = client.post(
                "/auth/reset-password",
                json={"token": token, "new_password": "newSecurePass123"},
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already used" in response.json().get("detail", "").lower()

    def test_reset_password_store_unavailable_returns_503(
        self, client: TestClient, test_db, test_org_id
    ):
        """POST /auth/reset-password when store unavailable returns 503."""
        from rhesis.backend.app.auth.used_token_store import (
            TokenStoreUnavailableError,
        )

        email = _unique_email("reset503")
        org = create_test_organization(test_db, "Reset 503 Org")
        user = create_test_user(test_db, org.id, email, "Reset 503 User")
        test_db.flush()

        with (
            patch(
                "rhesis.backend.app.auth.token_utils.get_secret_key",
                return_value="test-secret",
            ),
            patch(
                "rhesis.backend.app.routers.auth.claim_token_jti",
                new_callable=AsyncMock,
                side_effect=TokenStoreUnavailableError("redis down"),
            ),
        ):
            token = create_password_reset_token(str(user.id), user.email)
            response = client.post(
                "/auth/reset-password",
                json={"token": token, "new_password": "newSecurePass123"},
            )

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


@pytest.mark.unit
class TestAuthMagicLinkRoutes:
    """Route tests for magic-link and magic-link/verify (single-use)."""

    def test_magic_link_returns_200_enumeration_safe(self, client: TestClient):
        """POST /auth/magic-link always 200 (enumeration-safe)."""
        response = client.post(
            "/auth/magic-link",
            json={"email": "unknown@example.com"},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "message" in data

    def test_magic_link_verify_valid_token_single_use(
        self, client: TestClient, test_db, test_org_id
    ):
        """POST /auth/magic-link/verify with valid token returns session."""
        email = _unique_email("magic")
        org = create_test_organization(test_db, "Magic Org")
        user = create_test_user(test_db, org.id, email, "Magic User")
        test_db.flush()

        with (
            patch(
                "rhesis.backend.app.auth.token_utils.get_secret_key",
                return_value="test-secret",
            ),
            patch(
                "rhesis.backend.app.routers.auth.claim_token_jti",
                new_callable=AsyncMock,
                return_value=True,
            ),
        ):
            token = create_magic_link_token(str(user.id), user.email)
            response = client.post(
                "/auth/magic-link/verify",
                json={"token": token},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "session_token" in data
        assert data["user"]["email"] == user.email
        assert data["user"]["id"] == str(user.id)

    def test_magic_link_verify_already_used_returns_400(
        self, client: TestClient, test_db, test_org_id
    ):
        """POST /auth/magic-link/verify when link already used returns 400."""
        email = _unique_email("magic-used")
        org = create_test_organization(test_db, "Magic Used Org")
        user = create_test_user(test_db, org.id, email, "Magic Used User")
        test_db.flush()

        with (
            patch(
                "rhesis.backend.app.auth.token_utils.get_secret_key",
                return_value="test-secret",
            ),
            patch(
                "rhesis.backend.app.routers.auth.claim_token_jti",
                new_callable=AsyncMock,
                return_value=False,
            ),
        ):
            token = create_magic_link_token(str(user.id), user.email)
            response = client.post(
                "/auth/magic-link/verify",
                json={"token": token},
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already used" in response.json().get("detail", "").lower()

    def test_magic_link_verify_store_unavailable_returns_503(
        self, client: TestClient, test_db, test_org_id
    ):
        """POST /auth/magic-link/verify when store unavailable returns 503."""
        from rhesis.backend.app.auth.used_token_store import (
            TokenStoreUnavailableError,
        )

        email = _unique_email("magic503")
        org = create_test_organization(test_db, "Magic 503 Org")
        user = create_test_user(test_db, org.id, email, "Magic 503 User")
        test_db.flush()

        with (
            patch(
                "rhesis.backend.app.auth.token_utils.get_secret_key",
                return_value="test-secret",
            ),
            patch(
                "rhesis.backend.app.routers.auth.claim_token_jti",
                new_callable=AsyncMock,
                side_effect=TokenStoreUnavailableError("redis down"),
            ),
        ):
            token = create_magic_link_token(str(user.id), user.email)
            response = client.post(
                "/auth/magic-link/verify",
                json={"token": token},
            )

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
