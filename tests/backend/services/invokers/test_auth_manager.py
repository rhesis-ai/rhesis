"""Tests for authentication manager functionality."""

from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from rhesis.backend.app.services.invokers.auth.manager import AuthenticationManager


class TestAuthenticationManager:
    """Test AuthenticationManager class functionality."""

    def test_get_valid_token_with_bearer_token(self, mock_db, sample_endpoint_rest):
        """Test getting token with bearer token auth type."""
        manager = AuthenticationManager()

        token = manager.get_valid_token(mock_db, sample_endpoint_rest)

        assert token == "test-bearer-token"

    def test_get_valid_token_with_cached_token(self, mock_db, sample_endpoint_oauth):
        """Test getting cached token when still valid."""
        manager = AuthenticationManager()

        token = manager.get_valid_token(mock_db, sample_endpoint_oauth)

        assert token == "cached-access-token"

    def test_get_valid_token_with_expired_cache(self, mock_db, sample_endpoint_oauth):
        """Test getting new token when cache is expired."""
        manager = AuthenticationManager()

        # Set expired token
        sample_endpoint_oauth.last_token_expires_at = datetime.utcnow() - timedelta(hours=1)

        mock_response = Mock()
        mock_response.json.return_value = {
            "access_token": "new-access-token",
            "expires_in": 3600,
        }
        mock_response.raise_for_status = Mock()

        with patch("requests.post", return_value=mock_response):
            token = manager.get_valid_token(mock_db, sample_endpoint_oauth)

        assert token == "new-access-token"
        assert sample_endpoint_oauth.last_token == "new-access-token"

    def test_get_valid_token_no_auth(self, mock_db, sample_endpoint_rest):
        """Test getting token when no auth type and no auth token configured."""
        manager = AuthenticationManager()
        sample_endpoint_rest.auth_type = None
        sample_endpoint_rest.auth_token = None  # Also clear auth_token

        token = manager.get_valid_token(mock_db, sample_endpoint_rest)

        assert token is None

    def test_get_valid_token_no_auth_type_but_has_token(self, mock_db, sample_endpoint_rest):
        """Test getting token when no auth_type but auth_token exists (fallback to bearer)."""
        manager = AuthenticationManager()
        sample_endpoint_rest.auth_type = None
        # Keep auth_token from fixture

        token = manager.get_valid_token(mock_db, sample_endpoint_rest)

        assert token == "test-bearer-token"

    def test_get_client_credentials_token_success(self, mock_db, sample_endpoint_oauth):
        """Test successful OAuth client credentials flow."""
        manager = AuthenticationManager()

        mock_response = Mock()
        mock_response.json.return_value = {
            "access_token": "oauth-token",
            "expires_in": 7200,
        }
        mock_response.raise_for_status = Mock()

        with patch("requests.post", return_value=mock_response) as mock_post:
            token = manager.get_client_credentials_token(mock_db, sample_endpoint_oauth)

            # Verify correct payload was sent
            call_args = mock_post.call_args
            assert call_args[0][0] == "https://auth.example.com/oauth/token"
            payload = call_args[1]["json"]
            assert payload["client_id"] == "test-client-id"
            assert payload["client_secret"] == "test-client-secret"
            assert payload["audience"] == "https://api.example.com"
            assert payload["grant_type"] == "client_credentials"

        assert token == "oauth-token"

    def test_get_client_credentials_token_with_scopes(self, mock_db, sample_endpoint_oauth):
        """Test OAuth token request with scopes."""
        manager = AuthenticationManager()
        sample_endpoint_oauth.scopes = ["read:data", "write:data"]

        mock_response = Mock()
        mock_response.json.return_value = {
            "access_token": "scoped-token",
            "expires_in": 3600,
        }
        mock_response.raise_for_status = Mock()

        with patch("requests.post", return_value=mock_response) as mock_post:
            manager.get_client_credentials_token(mock_db, sample_endpoint_oauth)

            payload = mock_post.call_args[1]["json"]
            assert payload["scope"] == "read:data write:data"

    def test_get_client_credentials_token_with_extra_payload(self, mock_db, sample_endpoint_oauth):
        """Test OAuth token request with extra payload fields."""
        manager = AuthenticationManager()
        sample_endpoint_oauth.extra_payload = {"resource": "api.example.com"}

        mock_response = Mock()
        mock_response.json.return_value = {
            "access_token": "token-with-extra",
            "expires_in": 3600,
        }
        mock_response.raise_for_status = Mock()

        with patch("requests.post", return_value=mock_response) as mock_post:
            manager.get_client_credentials_token(mock_db, sample_endpoint_oauth)

            payload = mock_post.call_args[1]["json"]
            assert payload["resource"] == "api.example.com"

    def test_get_client_credentials_token_no_token_url(self, mock_db, sample_endpoint_oauth):
        """Test OAuth flow fails when token_url is missing."""
        manager = AuthenticationManager()
        sample_endpoint_oauth.token_url = None

        with pytest.raises(HTTPException) as exc_info:
            manager.get_client_credentials_token(mock_db, sample_endpoint_oauth)

        assert exc_info.value.status_code == 400
        assert "Token URL is required" in str(exc_info.value.detail)

    def test_get_client_credentials_token_request_fails(self, mock_db, sample_endpoint_oauth):
        """Test OAuth flow handles request failures."""
        manager = AuthenticationManager()

        with patch("requests.post", side_effect=Exception("Network error")):
            with pytest.raises(HTTPException) as exc_info:
                manager.get_client_credentials_token(mock_db, sample_endpoint_oauth)

            assert exc_info.value.status_code == 500
            assert "Failed to get client credentials token" in str(exc_info.value.detail)

    def test_get_client_credentials_token_http_error(self, mock_db, sample_endpoint_oauth):
        """Test OAuth flow handles HTTP errors."""
        manager = AuthenticationManager()

        mock_response = Mock()
        mock_response.raise_for_status.side_effect = Exception("401 Unauthorized")

        with patch("requests.post", return_value=mock_response):
            with pytest.raises(HTTPException) as exc_info:
                manager.get_client_credentials_token(mock_db, sample_endpoint_oauth)

            assert exc_info.value.status_code == 500

    def test_get_client_credentials_token_updates_endpoint_cache(
        self, mock_db, sample_endpoint_oauth
    ):
        """Test that successful token request updates endpoint cache."""
        manager = AuthenticationManager()

        # Clear cache
        sample_endpoint_oauth.last_token = None
        sample_endpoint_oauth.last_token_expires_at = None

        mock_response = Mock()
        mock_response.json.return_value = {
            "access_token": "fresh-token",
            "expires_in": 1800,
        }
        mock_response.raise_for_status = Mock()

        with patch("requests.post", return_value=mock_response):
            token = manager.get_client_credentials_token(mock_db, sample_endpoint_oauth)

        assert token == "fresh-token"
        assert sample_endpoint_oauth.last_token == "fresh-token"
        assert sample_endpoint_oauth.last_token_expires_at > datetime.utcnow()
        # Check expiry is approximately 1800 seconds in the future
        time_until_expiry = (
            sample_endpoint_oauth.last_token_expires_at - datetime.utcnow()
        ).total_seconds()
        assert 1790 < time_until_expiry < 1810
