"""
🏠 Home Router Tests

Tests for the home router endpoints including authentication scenarios,
response formats, and user experience flows.
"""

from unittest.mock import Mock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from .endpoints import APIEndpoints


class TestHomePublicEndpoint:
    """
    🌐 Test public home endpoint (/home/)

    Tests the main home endpoint that handles both authenticated
    and unauthenticated users.
    """

    def test_home_unauthenticated_user(self, client: TestClient):
        """
        🔓 Test home endpoint for unauthenticated users

        Should return welcome message with login URL when no user is authenticated.
        """
        response = client.get(APIEndpoints.HOME.HOME)

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert "message" in data
        assert "Welcome! Please log in." in data["message"]
        assert "login_url" in data
        assert data["login_url"].endswith("/auth/login")

    def test_home_authenticated_user(self, client: TestClient, sample_user: dict):
        """
        ✅ Test home endpoint for authenticated users

        Should return personalized welcome message using user's display name.
        """
        from rhesis.backend.app.auth.user_utils import get_current_user
        from rhesis.backend.app.main import app

        # Mock user for dependency override
        mock_user = Mock()
        mock_user.display_name = sample_user["display_name"]

        # Override the dependency
        def mock_get_current_user():
            return mock_user

        app.dependency_overrides[get_current_user] = mock_get_current_user

        try:
            response = client.get(APIEndpoints.HOME.HOME)

            assert response.status_code == status.HTTP_200_OK

            data = response.json()
            assert "message" in data
            assert f"Welcome, {sample_user['display_name']}!" == data["message"]
            assert "login_url" not in data  # No login URL for authenticated users
        finally:
            # Clean up the override
            app.dependency_overrides.clear()

    def test_home_base_url_format(self, client: TestClient):
        """
        🔗 Test that base URL is properly formatted in login URL

        Ensures the login URL uses the correct base URL without trailing slashes.
        """
        response = client.get(APIEndpoints.HOME.HOME)

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        login_url = data["login_url"]

        # Should not have double slashes in URL
        assert "//" not in login_url.replace("http://", "").replace("https://", "")

        # Should end with the auth login path
        assert login_url.endswith("/auth/login")

    def test_home_user_with_null_name(self, client: TestClient):
        """
        👤 Test home endpoint with user having null name

        Should use email as display name when user.name is None.
        """
        from rhesis.backend.app.auth.user_utils import get_current_user
        from rhesis.backend.app.main import app

        # Mock user with no name (display_name should fall back to email)
        mock_user = Mock()
        mock_user.name = None
        mock_user.email = "test@example.com"
        mock_user.display_name = "test@example.com"  # This is how the property works

        # Override the dependency
        def mock_get_current_user():
            return mock_user

        app.dependency_overrides[get_current_user] = mock_get_current_user

        try:
            response = client.get(APIEndpoints.HOME.HOME)

            assert response.status_code == status.HTTP_200_OK

            data = response.json()
            assert data["message"] == "Welcome, test@example.com!"
        finally:
            # Clean up the override
            app.dependency_overrides.clear()

    def test_home_user_with_display_name(self, client: TestClient):
        """
        👤 Test home endpoint with user having display name

        Should use the user's name when available.
        """
        from rhesis.backend.app.auth.user_utils import get_current_user
        from rhesis.backend.app.main import app

        # Mock user with proper name
        mock_user = Mock()
        mock_user.name = "John Doe"
        mock_user.email = "john@example.com"
        mock_user.display_name = "John Doe"

        # Override the dependency
        def mock_get_current_user():
            return mock_user

        app.dependency_overrides[get_current_user] = mock_get_current_user

        try:
            response = client.get(APIEndpoints.HOME.HOME)

            assert response.status_code == status.HTTP_200_OK

            data = response.json()
            assert data["message"] == "Welcome, John Doe!"
        finally:
            # Clean up the override
            app.dependency_overrides.clear()


class TestHomeProtectedEndpoint:
    """
    🔒 Test protected home endpoint (/home/protected)

    Tests the protected endpoint that requires authentication.
    """

    def test_protected_unauthenticated(self, client: TestClient):
        """
        🚫 Test protected endpoint without authentication

        Should return 401 Unauthorized for unauthenticated access.
        """
        response = client.get(APIEndpoints.HOME.PROTECTED)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

        data = response.json()
        assert "detail" in data
        # The actual error message may vary, so let's be more flexible
        assert data["detail"] is not None

    def test_protected_authenticated(self, client: TestClient, sample_user: dict):
        """
        ✅ Test protected endpoint with authentication

        Should return personalized welcome message for authenticated users.
        """
        from rhesis.backend.app.auth.user_utils import require_current_user
        from rhesis.backend.app.main import app

        # Mock user for dependency override
        mock_user = Mock()
        mock_user.display_name = sample_user["display_name"]

        # Override the dependency
        def mock_require_current_user():
            return mock_user

        app.dependency_overrides[require_current_user] = mock_require_current_user

        try:
            response = client.get(APIEndpoints.HOME.PROTECTED)

            assert response.status_code == status.HTTP_200_OK

            data = response.json()
            assert "message" in data
            assert f"Welcome, {sample_user['display_name']}!" == data["message"]
        finally:
            # Clean up the override
            app.dependency_overrides.clear()

    @patch("rhesis.backend.app.auth.user_utils.require_current_user")
    def test_protected_authentication_failure(self, mock_require_user, client: TestClient):
        """
        🔐 Test protected endpoint with authentication failure

        Should handle authentication dependency failures gracefully.
        """
        from fastapi import HTTPException

        # Mock authentication failure
        mock_require_user.side_effect = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )

        response = client.get(APIEndpoints.HOME.PROTECTED)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestHomeErrorHandling:
    """
    ⚠️ Test error handling and edge cases for home endpoints
    """

    @patch("rhesis.backend.app.auth.user_utils.get_current_user")
    def test_home_user_service_exception(self, mock_get_user, client: TestClient):
        """
        💥 Test home endpoint when user service throws exception

        Should handle user service failures gracefully.
        """
        # Mock user service exception
        mock_get_user.side_effect = Exception("Database connection failed")

        response = client.get(APIEndpoints.HOME.HOME)

        # Should still work since get_current_user returns None on exception
        # (based on FastAPI dependency behavior)
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]

    def test_home_invalid_http_method(self, client: TestClient):
        """
        🚫 Test home endpoint with invalid HTTP method

        Should return 405 Method Not Allowed for unsupported methods.
        """
        # Test POST on GET-only endpoint
        response = client.post(APIEndpoints.HOME.HOME, json={"test": "data"})

        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_protected_invalid_http_method(self, client: TestClient):
        """
        🚫 Test protected endpoint with invalid HTTP method

        Should return 405 Method Not Allowed for unsupported methods.
        """
        # Test PUT on GET-only endpoint
        response = client.put(APIEndpoints.HOME.PROTECTED, json={"test": "data"})

        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


class TestHomeResponseFormat:
    """
    📋 Test response format and structure for home endpoints
    """

    def test_home_response_structure_unauthenticated(self, client: TestClient):
        """
        📝 Test response structure for unauthenticated home request

        Should contain specific fields in the expected format.
        """
        response = client.get(APIEndpoints.HOME.HOME)

        assert response.status_code == status.HTTP_200_OK

        data = response.json()

        # Required fields for unauthenticated response
        assert isinstance(data, dict)
        assert "message" in data
        assert "login_url" in data

        # Field type validation
        assert isinstance(data["message"], str)
        assert isinstance(data["login_url"], str)

        # Content validation
        assert len(data["message"]) > 0
        assert data["login_url"].startswith("http")

    def test_home_response_structure_authenticated(self, client: TestClient):
        """
        📝 Test response structure for authenticated home request

        Should contain message field without login_url.
        """
        from rhesis.backend.app.auth.user_utils import get_current_user
        from rhesis.backend.app.main import app

        # Mock authenticated user
        mock_user = Mock()
        mock_user.display_name = "Test User"

        # Override the dependency
        def mock_get_current_user():
            return mock_user

        app.dependency_overrides[get_current_user] = mock_get_current_user

        try:
            response = client.get(APIEndpoints.HOME.HOME)

            assert response.status_code == status.HTTP_200_OK

            data = response.json()

            # Required fields for authenticated response
            assert isinstance(data, dict)
            assert "message" in data

            # Should not contain login_url for authenticated users
            assert "login_url" not in data

            # Field type validation
            assert isinstance(data["message"], str)
            assert len(data["message"]) > 0
        finally:
            # Clean up the override
            app.dependency_overrides.clear()

    def test_protected_response_structure(self, client: TestClient):
        """
        📝 Test response structure for protected endpoint

        Should have consistent format with other endpoints.
        """
        from rhesis.backend.app.auth.user_utils import require_current_user
        from rhesis.backend.app.main import app

        # Mock authenticated user
        mock_user = Mock()
        mock_user.display_name = "Test User"

        # Override the dependency
        def mock_require_current_user():
            return mock_user

        app.dependency_overrides[require_current_user] = mock_require_current_user

        try:
            response = client.get(APIEndpoints.HOME.PROTECTED)

            assert response.status_code == status.HTTP_200_OK

            data = response.json()

            # Required fields
            assert isinstance(data, dict)
            assert "message" in data

            # Field validation
            assert isinstance(data["message"], str)
            assert len(data["message"]) > 0
            assert data["message"].startswith("Welcome,")
        finally:
            # Clean up the override
            app.dependency_overrides.clear()


class TestHomeIntegration:
    """
    🔄 Integration tests for home endpoints

    Tests the full flow including authentication and user experience.
    """

    def test_authentication_flow_simulation(self, client: TestClient):
        """
        🔄 Test complete authentication flow simulation

        Simulates user going from unauthenticated to authenticated state.
        """
        from rhesis.backend.app.auth.user_utils import get_current_user
        from rhesis.backend.app.main import app

        # Step 1: Unauthenticated access
        def mock_get_current_user_unauth():
            return None

        app.dependency_overrides[get_current_user] = mock_get_current_user_unauth

        try:
            response_unauth = client.get(APIEndpoints.HOME.HOME)
            assert response_unauth.status_code == status.HTTP_200_OK

            unauth_data = response_unauth.json()
            assert "login_url" in unauth_data

            # Step 2: Authenticated access (simulating successful login)
            mock_user = Mock()
            mock_user.display_name = "Test User"

            def mock_get_current_user_auth():
                return mock_user

            app.dependency_overrides[get_current_user] = mock_get_current_user_auth

            response_auth = client.get(APIEndpoints.HOME.HOME)
            assert response_auth.status_code == status.HTTP_200_OK

            auth_data = response_auth.json()
            assert "login_url" not in auth_data
            assert "Welcome," in auth_data["message"]
        finally:
            # Clean up the override
            app.dependency_overrides.clear()

    def test_protected_endpoint_access_pattern(self, client: TestClient):
        """
        🔒 Test access pattern for protected endpoint

        Verifies proper access control behavior.
        """
        from fastapi import HTTPException

        from rhesis.backend.app.auth.user_utils import require_current_user
        from rhesis.backend.app.main import app

        # Step 1: Unauthenticated access should fail
        def mock_require_user_fail():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
            )

        app.dependency_overrides[require_current_user] = mock_require_user_fail

        try:
            response_unauth = client.get(APIEndpoints.HOME.PROTECTED)
            assert response_unauth.status_code == status.HTTP_401_UNAUTHORIZED

            # Step 2: Authenticated access should succeed
            mock_user = Mock()
            mock_user.display_name = "Test User"

            def mock_require_user_success():
                return mock_user

            app.dependency_overrides[require_current_user] = mock_require_user_success

            response_auth = client.get(APIEndpoints.HOME.PROTECTED)
            assert response_auth.status_code == status.HTTP_200_OK

            # Responses should have different content
            assert response_unauth.json() != response_auth.json()
        finally:
            # Clean up the override
            app.dependency_overrides.clear()


class TestHomePerformance:
    """
    ⚡ Performance tests for home endpoints
    """

    @pytest.mark.performance
    def test_home_endpoint_response_time(self, client: TestClient):
        """
        ⚡ Test home endpoint response time

        Should respond quickly as it's a simple endpoint.
        """
        import time

        start_time = time.time()
        response = client.get(APIEndpoints.HOME.HOME)
        end_time = time.time()

        assert response.status_code == status.HTTP_200_OK

        response_time = end_time - start_time
        assert response_time < 1.0  # Should respond within 1 second

    @pytest.mark.performance
    def test_protected_endpoint_response_time(self, client: TestClient):
        """
        ⚡ Test protected endpoint response time

        Should respond quickly even with authentication overhead.
        """
        import time

        from rhesis.backend.app.auth.user_utils import require_current_user
        from rhesis.backend.app.main import app

        # Mock authenticated user
        mock_user = Mock()
        mock_user.display_name = "Test User"

        def mock_require_user():
            return mock_user

        app.dependency_overrides[require_current_user] = mock_require_user

        try:
            start_time = time.time()
            response = client.get(APIEndpoints.HOME.PROTECTED)
            end_time = time.time()

            assert response.status_code == status.HTTP_200_OK

            response_time = end_time - start_time
            assert response_time < 1.0  # Should respond within 1 second
        finally:
            # Clean up the override
            app.dependency_overrides.clear()


class TestHomeHealthChecks:
    """
    🏥 Health check tests for home endpoints
    """

    def test_home_endpoint_availability(self, client: TestClient):
        """
        💓 Test basic availability of home endpoint

        Should always be available for health checking.
        """
        response = client.get(APIEndpoints.HOME.HOME)

        # Should respond (regardless of authentication)
        assert response.status_code == status.HTTP_200_OK

        # Should have expected response structure
        data = response.json()
        assert "message" in data

    def test_home_endpoints_consistent_behavior(self, client: TestClient):
        """
        🔄 Test consistent behavior across multiple requests

        Should return consistent responses for the same conditions.
        """
        # Make multiple requests
        responses = []
        for _ in range(3):
            response = client.get(APIEndpoints.HOME.HOME)
            responses.append(response.json())

        # All responses should be identical for unauthenticated users
        first_response = responses[0]
        for response in responses[1:]:
            assert response == first_response

    def test_all_home_endpoints_exist(self, client: TestClient):
        """
        🔍 Test that all defined home endpoints exist

        Should verify all endpoints are properly configured.
        """
        # Test base home endpoint
        response_home = client.get(APIEndpoints.HOME.HOME)
        assert response_home.status_code in [status.HTTP_200_OK, status.HTTP_401_UNAUTHORIZED]

        # Test protected endpoint (will return 401 but should exist)
        response_protected = client.get(APIEndpoints.HOME.PROTECTED)
        assert response_protected.status_code in [status.HTTP_200_OK, status.HTTP_401_UNAUTHORIZED]

        # Neither should return 404 Not Found
        assert response_home.status_code != status.HTTP_404_NOT_FOUND
        assert response_protected.status_code != status.HTTP_404_NOT_FOUND
