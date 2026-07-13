"""
Authentication Routes Testing Suite

Comprehensive test suite for authentication endpoints including login, callback,
logout, and token verification. This module tests OAuth2 flows, session management,
and JWT token handling.

Run with: python -m pytest tests/backend/routes/test_auth.py -v
"""

import os
import uuid
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from faker import Faker
from fastapi import status
from fastapi.testclient import TestClient

from rhesis.backend.app.auth.constants import AuthProviderType
from rhesis.backend.app.auth.token_utils import (
    create_auth_code,
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


def _mock_application_settings(
    backend_env: str = "development",
    api_base_url: str = "https://api.rhesis.ai",
):
    env = backend_env.lower()
    settings = Mock(backend_env=env, api_base_url=api_base_url)
    settings.is_development = env != "production"
    settings.is_production = env == "production"
    return lambda: settings


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

    def test_get_providers_includes_password_policy(self, client: TestClient):
        """Test that /auth/providers includes password policy (min/max length)."""
        response = client.get("/auth/providers")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "password_policy" in data
        policy = data["password_policy"]
        assert "min_length" in policy
        assert "max_length" in policy
        assert isinstance(policy["min_length"], int)
        assert isinstance(policy["max_length"], int)
        assert policy["min_length"] >= 1
        assert policy["max_length"] >= policy["min_length"]

    def test_get_providers_oauth_disabled_without_credentials(self, client: TestClient):
        """Test OAuth providers are not enabled without credentials."""
        from rhesis.backend.app.auth.providers.registry import ProviderRegistry
        from rhesis.backend.app.config.settings import get_auth_settings

        with patch.dict(os.environ, {}, clear=True):
            # Clear the LRU-cached settings so is_enabled re-reads the (now empty) env
            get_auth_settings.cache_clear()
            ProviderRegistry.reset()

            try:
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
            finally:
                # Restore settings cache so subsequent tests see real credentials
                get_auth_settings.cache_clear()
                ProviderRegistry.reset()


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
        from rhesis.backend.app.auth.providers.registry import ProviderRegistry
        from rhesis.backend.app.config.settings import get_auth_settings

        with patch.dict(os.environ, {}, clear=True):
            get_auth_settings.cache_clear()
            ProviderRegistry.reset()

            try:
                response = client.get("/auth/login/google")

                assert response.status_code == status.HTTP_400_BAD_REQUEST
                assert "not configured" in response.json()["detail"]
            finally:
                get_auth_settings.cache_clear()
                ProviderRegistry.reset()

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
        """Test registration with password too short (policy validation)."""
        response = client.post(
            "/auth/register",
            json={"email": "test@example.com", "password": "short"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "at least" in data.get("detail", "").lower()

    def test_register_invalid_email_format(self, client: TestClient):
        """Test registration with invalid email format."""
        response = client.post(
            "/auth/register",
            json={"email": "not-an-email", "password": "password123"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


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
            from jwt import PyJWTError

            mock_verify.side_effect = PyJWTError("Invalid token")

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

    def test_logout_clears_session_cookie_secure_variants(self, client: TestClient):
        """Logout clears the backend session cookie with both Secure variants."""
        with patch.dict(os.environ, {"FRONTEND_URL": "https://app.example.com"}):
            response = client.get("/auth/logout", follow_redirects=False)

        assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT
        set_cookies = response.headers.get_list("set-cookie")
        session_clears = [h for h in set_cookies if h.startswith("session=")]
        assert len(session_clears) == 2
        assert any("Secure" in h for h in session_clears)
        assert any("Secure" not in h for h in session_clears)
        assert all("domain=" not in h.lower() for h in session_clears)


@pytest.mark.unit
@pytest.mark.critical
class TestAuthVerify:
    """Test authentication verification endpoint"""

    def test_verify_valid_token(self, client: TestClient):
        """Test verification of valid JWT token via POST"""
        user_data = {
            "id": str(uuid.uuid4()),
            "email": "test@example.com",
            "name": "Test User",
        }
        mock_payload = {"user": user_data}

        with patch("rhesis.backend.app.routers.auth.verify_jwt_token") as mock_verify:
            with patch("rhesis.backend.app.routers.auth.get_secret_key") as mock_secret:
                mock_verify.return_value = mock_payload
                mock_secret.return_value = "test_secret"

                response = client.post(
                    "/auth/verify",
                    json={"session_token": "valid_token"},
                )

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

                response = client.post(
                    "/auth/verify",
                    json={
                        "session_token": "valid_token",
                        "return_to": "/architect",
                    },
                )

                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["return_to"] == "/architect"

    def test_verify_invalid_token(self, client: TestClient):
        """Test verification of invalid JWT token"""
        with patch("rhesis.backend.app.routers.auth.verify_jwt_token") as mock_verify:
            with patch("rhesis.backend.app.routers.auth.get_secret_key") as mock_secret:
                from jwt import PyJWTError

                mock_verify.side_effect = PyJWTError("Invalid token")
                mock_secret.return_value = "test_secret"

                response = client.post(
                    "/auth/verify",
                    json={"session_token": "invalid_token"},
                )

                assert response.status_code == status.HTTP_401_UNAUTHORIZED
                assert "Invalid token" in response.json()["detail"]

    def test_verify_expired_token(self, client: TestClient):
        """Test verification of expired JWT token"""
        with patch("rhesis.backend.app.routers.auth.verify_jwt_token") as mock_verify:
            with patch("rhesis.backend.app.routers.auth.get_secret_key") as mock_secret:
                import jwt

                mock_verify.side_effect = jwt.ExpiredSignatureError("Signature has expired")
                mock_secret.return_value = "test_secret"

                response = client.post(
                    "/auth/verify",
                    json={"session_token": "expired_token"},
                )

                assert response.status_code == status.HTTP_401_UNAUTHORIZED
                assert "Token has expired" in response.json()["detail"]

    def test_verify_missing_session_token(self, client: TestClient):
        """Test verification without session token in body"""
        response = client.post("/auth/verify", json={})

        # Should return validation error for missing required field
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_verify_general_exception(self, client: TestClient):
        """Test verification handles general exceptions"""
        with patch("rhesis.backend.app.routers.auth.verify_jwt_token") as mock_verify:
            with patch("rhesis.backend.app.routers.auth.get_secret_key") as mock_secret:
                mock_verify.side_effect = Exception("Unexpected error")
                mock_secret.return_value = "test_secret"

                response = client.post(
                    "/auth/verify",
                    json={"session_token": "test_token"},
                )

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

    def test_callback_with_missing_parameters(self, client: TestClient):
        """🏃‍♂️ Test callback with missing required parameters"""
        response = client.get("/auth/callback")

        # Should handle missing code/state gracefully
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_verify_with_malformed_token(self, client: TestClient):
        """Test verify with malformed JWT token via POST"""
        malformed_tokens = [
            "not.a.jwt",
            "invalid_token_format",
            "",  # empty token
            "a.b.c.d.e",  # too many parts
            "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9",  # incomplete JWT
        ]

        for token in malformed_tokens:
            response = client.post(
                "/auth/verify",
                json={"session_token": token},
            )
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
                    response = client.post(
                        "/auth/verify",
                        json={"session_token": "test_token"},
                    )
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
        """Verify endpoint correctly requires session token in POST body"""
        response = client.post("/auth/verify", json={})
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
        assert "verified" in data["message"].lower()

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
        user.provider_type = AuthProviderType.EMAIL
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

    def test_magic_link_missing_accept_terms_returns_200(
        self, client: TestClient, test_db, test_org_id
    ):
        """Magic link stays enumeration-safe without accept_terms in the body."""
        response = client.post(
            "/auth/magic-link",
            json={"email": "nobody-magic@example.com"},
        )
        assert response.status_code == status.HTTP_200_OK

    def test_accept_terms_records_current_version(
        self, client: TestClient, test_db, test_org_id
    ):
        from rhesis.backend.app.auth.terms import CURRENT_TERMS_VERSION
        from rhesis.backend.app.auth.token_utils import create_session_token

        email = _unique_email("accept-terms")
        org = create_test_organization(test_db, "Accept Terms Org")
        user = create_test_user(test_db, org.id, email, "Accept Terms User")
        test_db.flush()

        token = create_session_token(user)
        response = client.post(
            "/auth/accept-terms",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"success": True, "terms_accepted": True}

        test_db.refresh(user)
        assert user.terms_accepted_at is not None
        assert user.terms_accepted_version == CURRENT_TERMS_VERSION

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
        assert "refresh_token" in data
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


# =============================================================================
# Auth Code Exchange Tests
# =============================================================================


@pytest.mark.unit
class TestAuthExchangeCode:
    """Test POST /auth/exchange-code for OAuth auth code exchange."""

    def test_exchange_valid_code(self, client: TestClient):
        """Exchange a valid auth code returns session + refresh tokens."""
        with patch(
            "rhesis.backend.app.auth.token_utils.get_secret_key",
            return_value="test-secret",
        ):
            code = create_auth_code(
                "real-session-token-123",
                refresh_token="refresh-tok-456",
            )
            response = client.post(
                "/auth/exchange-code",
                json={"code": code},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["session_token"] == "real-session-token-123"
        assert data["refresh_token"] == "refresh-tok-456"

    def test_exchange_invalid_code(self, client: TestClient):
        """Exchange an invalid auth code returns 400."""
        response = client.post(
            "/auth/exchange-code",
            json={"code": "invalid.jwt.code"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_exchange_expired_code(self, client: TestClient):
        """Exchange an expired auth code returns 400."""
        from datetime import datetime, timedelta, timezone

        import jwt

        payload = {
            "type": "auth_code",
            "session_token": "session-token-123",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=5),
            "iat": datetime.now(timezone.utc) - timedelta(minutes=10),
        }

        with patch(
            "rhesis.backend.app.auth.token_utils.get_secret_key",
            return_value="test-secret",
        ):
            expired_code = jwt.encode(payload, "test-secret", algorithm="HS256")
            response = client.post(
                "/auth/exchange-code",
                json={"code": expired_code},
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_exchange_code_missing_body(self, client: TestClient):
        """Exchange without code in body returns 422."""
        response = client.post(
            "/auth/exchange-code",
            json={},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# =============================================================================
# Verify-email enumeration safety tests
# =============================================================================


@pytest.mark.unit
class TestVerifyEmailEnumerationSafety:
    """Verify that /auth/verify-email does not leak email existence."""

    def test_verify_email_user_not_found_returns_200(
        self, client: TestClient, test_db, test_org_id
    ):
        """POST /auth/verify-email returns success even when user deleted."""
        # Create a verification token for a user, then delete the user
        email = _unique_email("deleted")
        org = create_test_organization(test_db, "Deleted Org")
        user = create_test_user(test_db, org.id, email, "Deleted User")

        with patch(
            "rhesis.backend.app.auth.token_utils.get_secret_key",
            return_value="test-secret",
        ):
            token = create_email_verification_token(str(user.id), user.email)

        # Delete the user
        test_db.delete(user)
        test_db.commit()

        with patch(
            "rhesis.backend.app.auth.token_utils.get_secret_key",
            return_value="test-secret",
        ):
            response = client.post(
                "/auth/verify-email",
                json={"token": token},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        # Should NOT contain session_token (no user to create session for)
        assert "session_token" not in data


# =============================================================================
# Refresh Token Tests
# =============================================================================


@pytest.mark.unit
class TestAuthRefreshToken:
    """Test POST /auth/refresh for access/refresh token rotation."""

    def test_refresh_valid_token(self, client: TestClient, test_db, test_org_id):
        """POST /auth/refresh with valid refresh token returns new tokens."""
        from rhesis.backend.app.auth.refresh_token_utils import (
            create_refresh_token as create_rt,
        )

        email = _unique_email("refresh")
        org = create_test_organization(test_db, "Refresh Org")
        user = create_test_user(test_db, org.id, email, "Refresh User")
        test_db.flush()

        raw_token = create_rt(test_db, str(user.id))
        test_db.commit()

        with patch(
            "rhesis.backend.app.auth.token_utils.get_secret_key",
            return_value="test-secret",
        ):
            response = client.post(
                "/auth/refresh",
                json={"refresh_token": raw_token},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        # New refresh token must differ from old one (rotation)
        assert data["refresh_token"] != raw_token

    def test_refresh_invalid_token(self, client: TestClient):
        """POST /auth/refresh with invalid refresh token returns 401."""
        response = client.post(
            "/auth/refresh",
            json={"refresh_token": "invalid-token"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_reuse_detection(self, client: TestClient, test_db, test_org_id):
        """POST /auth/refresh with reused token revokes entire family."""
        from rhesis.backend.app.auth.refresh_token_utils import (
            create_refresh_token as create_rt,
        )

        email = _unique_email("reuse")
        org = create_test_organization(test_db, "Reuse Org")
        user = create_test_user(test_db, org.id, email, "Reuse User")
        test_db.flush()

        raw_token = create_rt(test_db, str(user.id))
        test_db.commit()

        # First use should succeed
        with patch(
            "rhesis.backend.app.auth.token_utils.get_secret_key",
            return_value="test-secret",
        ):
            resp1 = client.post(
                "/auth/refresh",
                json={"refresh_token": raw_token},
            )
        assert resp1.status_code == status.HTTP_200_OK

        # Second use of the SAME token should fail (reuse detection).
        # The HTTP body is uniform across every 401 path so the
        # response cannot serve as an oracle for which failure mode
        # tripped (reuse vs expired vs unknown vs wrong client). The
        # detailed reason still lands in structured logs and the audit
        # stream; the public surface is intentionally generic.
        with patch(
            "rhesis.backend.app.auth.token_utils.get_secret_key",
            return_value="test-secret",
        ):
            resp2 = client.post(
                "/auth/refresh",
                json={"refresh_token": raw_token},
            )
        assert resp2.status_code == status.HTTP_401_UNAUTHORIZED
        assert resp2.json()["detail"] == "Invalid refresh token"

    def test_refresh_missing_body(self, client: TestClient):
        """POST /auth/refresh without body returns 422."""
        response = client.post("/auth/refresh", json={})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_refresh_rotated_token_works(self, client: TestClient, test_db, test_org_id):
        """After rotation the new refresh token can be used."""
        from rhesis.backend.app.auth.refresh_token_utils import (
            create_refresh_token as create_rt,
        )

        email = _unique_email("rotate")
        org = create_test_organization(test_db, "Rotate Org")
        user = create_test_user(test_db, org.id, email, "Rotate User")
        test_db.flush()

        raw_token = create_rt(test_db, str(user.id))
        test_db.commit()

        # First rotation
        with patch(
            "rhesis.backend.app.auth.token_utils.get_secret_key",
            return_value="test-secret",
        ):
            resp1 = client.post(
                "/auth/refresh",
                json={"refresh_token": raw_token},
            )
        assert resp1.status_code == status.HTTP_200_OK
        new_refresh = resp1.json()["refresh_token"]

        # Use the rotated token
        with patch(
            "rhesis.backend.app.auth.token_utils.get_secret_key",
            return_value="test-secret",
        ):
            resp2 = client.post(
                "/auth/refresh",
                json={"refresh_token": new_refresh},
            )
        assert resp2.status_code == status.HTTP_200_OK
        assert resp2.json()["refresh_token"] != new_refresh


# =============================================================================
# get_callback_url() Security Tests
# =============================================================================


def _make_mock_request(
    host: str = "localhost",
    port: int = 8080,
    scheme: str = "http",
    headers: dict = None,
):
    """Create a mock Request object for testing get_callback_url."""
    from starlette.datastructures import Headers

    request = MagicMock()
    request.scope = {"server": (host, port)}
    request.url = MagicMock()
    request.url.hostname = host

    if headers is None:
        headers = {"host": f"{host}:{port}"}
    request.headers = Headers(headers)

    return request


@pytest.mark.unit
class TestGetCallbackUrl:
    """Test get_callback_url() security against Host header poisoning."""

    @patch.dict(
        os.environ,
        {"QUICK_START": "true"},
        clear=False,
    )
    @patch(
        "rhesis.backend.app.routers.auth.is_quick_start_enabled",
        return_value=True,
    )
    def test_quick_start_mode_uses_localhost(self, mock_qs):
        """Quick start mode returns http://localhost:{port}/auth/callback."""
        from rhesis.backend.app.routers.auth import get_callback_url

        request = _make_mock_request(host="localhost", port=8080)
        url = get_callback_url(request)
        assert url == "http://localhost:8080/auth/callback"

    @patch(
        "rhesis.backend.app.routers.auth.is_quick_start_enabled",
        return_value=False,
    )
    @patch(
        "rhesis.backend.app.routers.auth.get_application_settings",
        new=_mock_application_settings(api_base_url="http://localhost:8080"),
    )
    def test_api_base_url_localhost_uses_localhost(self, mock_qs):
        """API_BASE_URL with localhost returns localhost callback."""
        from rhesis.backend.app.routers.auth import get_callback_url

        request = _make_mock_request(host="localhost", port=8080)
        url = get_callback_url(request)
        assert url == "http://localhost:8080/auth/callback"

    @patch(
        "rhesis.backend.app.routers.auth.is_quick_start_enabled",
        return_value=False,
    )
    @patch(
        "rhesis.backend.app.routers.auth.get_application_settings",
        new=_mock_application_settings(api_base_url="http://localhost:8080"),
    )
    def test_local_preserves_127_hostname(self, mock_qs):
        """Loopback API_BASE_URL via 127.0.0.1 preserves hostname for session cookies."""
        from rhesis.backend.app.routers.auth import get_callback_url

        request = _make_mock_request(host="127.0.0.1", port=8080)
        url = get_callback_url(request)
        assert url == "http://127.0.0.1:8080/auth/callback"

    @patch(
        "rhesis.backend.app.routers.auth.is_quick_start_enabled",
        return_value=False,
    )
    @patch(
        "rhesis.backend.app.routers.auth.get_application_settings",
        new=_mock_application_settings(api_base_url="http://localhost:8080"),
    )
    def test_local_rejects_non_local_hostname(self, mock_qs):
        """Loopback API_BASE_URL with evil Host falls back to localhost."""
        from rhesis.backend.app.routers.auth import get_callback_url

        request = _make_mock_request(host="evil.com", port=8080)
        url = get_callback_url(request)
        assert url == "http://localhost:8080/auth/callback"

    @patch(
        "rhesis.backend.app.routers.auth.is_quick_start_enabled",
        return_value=False,
    )
    @patch(
        "rhesis.backend.app.routers.auth.get_application_settings",
        new=_mock_application_settings("local", api_base_url="https://api.rhesis.ai"),
    )
    def test_backend_env_local_with_remote_api_base_url_uses_production_callback(
        self, mock_qs
    ):
        """BACKEND_ENV=local alone does not enable local callback behavior."""
        from rhesis.backend.app.routers.auth import get_callback_url

        request = _make_mock_request(host="localhost", port=8080)
        url = get_callback_url(request)
        assert url == "https://api.rhesis.ai/auth/callback"

    @patch(
        "rhesis.backend.app.routers.auth.is_quick_start_enabled",
        return_value=False,
    )
    @patch(
        "rhesis.backend.app.routers.auth.get_application_settings",
        new=_mock_application_settings("production"),
    )
    def test_production_uses_api_base_url(self, mock_qs):
        """Production (no local signals) uses API_BASE_URL."""
        from rhesis.backend.app.routers.auth import get_callback_url

        request = _make_mock_request(
            host="api.rhesis.ai",
            port=443,
            headers={"host": "api.rhesis.ai"},
        )
        url = get_callback_url(request)
        assert url == "https://api.rhesis.ai/auth/callback"

    @patch(
        "rhesis.backend.app.routers.auth.is_quick_start_enabled",
        return_value=False,
    )
    @patch(
        "rhesis.backend.app.routers.auth.get_application_settings",
        new=_mock_application_settings("production"),
    )
    def test_spoofed_localhost_host_header_uses_base_url(self, mock_qs):
        """Spoofed Host: localhost in production uses API_BASE_URL."""
        from rhesis.backend.app.routers.auth import get_callback_url

        request = _make_mock_request(
            host="api.rhesis.ai",
            port=443,
            headers={"host": "localhost"},
        )
        url = get_callback_url(request)
        assert url == "https://api.rhesis.ai/auth/callback"

    @patch(
        "rhesis.backend.app.routers.auth.is_quick_start_enabled",
        return_value=False,
    )
    @patch(
        "rhesis.backend.app.routers.auth.get_application_settings",
        new=_mock_application_settings("production"),
    )
    def test_spoofed_evil_host_header_uses_base_url(self, mock_qs):
        """Spoofed Host: evil.com in production uses API_BASE_URL."""
        from rhesis.backend.app.routers.auth import get_callback_url

        request = _make_mock_request(
            host="api.rhesis.ai",
            port=443,
            headers={"host": "evil.com"},
        )
        url = get_callback_url(request)
        assert url == "https://api.rhesis.ai/auth/callback"

    @patch(
        "rhesis.backend.app.routers.auth.is_quick_start_enabled",
        return_value=False,
    )
    @patch(
        "rhesis.backend.app.routers.auth.get_application_settings",
        new=_mock_application_settings("production"),
    )
    def test_localhost_attacker_com_uses_base_url(self, mock_qs):
        """localhost.attacker.com bypass attempt uses API_BASE_URL."""
        from rhesis.backend.app.routers.auth import get_callback_url

        request = _make_mock_request(
            host="api.rhesis.ai",
            port=443,
            headers={"host": "localhost.attacker.com"},
        )
        url = get_callback_url(request)
        assert url == "https://api.rhesis.ai/auth/callback"

    @patch(
        "rhesis.backend.app.routers.auth.is_quick_start_enabled",
        return_value=False,
    )
    @patch(
        "rhesis.backend.app.routers.auth.get_application_settings",
        new=_mock_application_settings(
            "production",
            api_base_url="http://staging.rhesis.ai",
        ),
    )
    def test_http_to_https_rewrite_for_non_localhost(self, mock_qs):
        """HTTP base URL for non-localhost gets rewritten to HTTPS."""
        from rhesis.backend.app.routers.auth import get_callback_url

        request = _make_mock_request(
            host="staging.rhesis.ai",
            port=443,
            headers={"host": "staging.rhesis.ai"},
        )
        url = get_callback_url(request)
        assert url == "https://staging.rhesis.ai/auth/callback"

    @patch.dict(
        os.environ,
        {"RHESIS_BASE_URL": "https://api.rhesis.ai"},
        clear=False,
    )
    @patch(
        "rhesis.backend.app.routers.auth.is_quick_start_enabled",
        return_value=False,
    )
    @patch(
        "rhesis.backend.app.routers.auth.get_application_settings",
        new=_mock_application_settings(
            "production",
            api_base_url="https://self-hosted.example.com",
        ),
    )
    def test_hybrid_split_uses_api_base_url_not_rhesis(self, mock_qs):
        """Hybrid setup: OAuth uses API_BASE_URL, not RHESIS_BASE_URL."""
        from rhesis.backend.app.routers.auth import get_callback_url

        request = _make_mock_request(
            host="self-hosted.example.com",
            port=443,
            headers={"host": "self-hosted.example.com"},
        )
        url = get_callback_url(request)
        assert url == "https://self-hosted.example.com/auth/callback"


@pytest.mark.unit
class TestTermsAcceptance:
    """Tests for T&C acceptance persistence and lookup."""

    def test_terms_status_unknown_email_returns_false(self, client: TestClient):
        response = client.get(
            "/auth/terms-status",
            params={"email": "nobody@example.com"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"terms_accepted": False}

    def test_terms_status_returns_true_for_current_version(
        self, client: TestClient, test_db, test_org_id
    ):
        from datetime import datetime, timezone

        from rhesis.backend.app.auth.terms import CURRENT_TERMS_VERSION

        email = _unique_email("terms")
        org = create_test_organization(test_db, "Terms Org")
        user = create_test_user(test_db, org.id, email, "Terms User")
        user.terms_accepted_at = datetime.now(timezone.utc)
        user.terms_accepted_version = CURRENT_TERMS_VERSION
        test_db.commit()

        response = client.get("/auth/terms-status", params={"email": email})
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"terms_accepted": True}

    def test_terms_status_returns_false_for_outdated_version(
        self, client: TestClient, test_db, test_org_id
    ):
        from datetime import datetime, timezone

        email = _unique_email("terms-old")
        org = create_test_organization(test_db, "Terms Old Org")
        user = create_test_user(test_db, org.id, email, "Terms Old User")
        user.terms_accepted_at = datetime.now(timezone.utc)
        user.terms_accepted_version = "0.9"
        test_db.commit()

        response = client.get("/auth/terms-status", params={"email": email})
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"terms_accepted": False}
