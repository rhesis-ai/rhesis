"""Security tests for WebSocket token service.

These tests verify that the WebSocketTokenService correctly issues
and validates short-lived, single-use tokens for WebSocket connections.
"""

import time
from uuid import uuid4

import pytest

from rhesis.backend.app.services.websocket.token_service import (
    WebSocketTokenService,
    get_ws_token_service,
)


@pytest.fixture
def token_service():
    """Create a fresh token service with a test secret."""
    return WebSocketTokenService(secret_key="test_secret_key_12345")


@pytest.fixture
def user_id():
    """Create a test user ID."""
    return str(uuid4())


@pytest.fixture
def org_id():
    """Create a test organization ID."""
    return str(uuid4())


class TestWebSocketTokenSecurity:
    """Security tests for WebSocket token issuance and validation."""

    def test_valid_token_is_accepted(self, token_service, user_id, org_id):
        """Test that a valid token is accepted."""
        token = token_service.create_ws_token(user_id, org_id)

        payload = token_service.validate_ws_token(token)

        assert payload is not None
        assert payload["sub"] == user_id
        assert payload["org"] == org_id
        assert payload["purpose"] == "websocket"

    def test_expired_token_is_rejected(self, user_id, org_id):
        """Test that expired tokens are rejected."""
        # Create service with very short TTL
        short_ttl_service = WebSocketTokenService(secret_key="test_secret")
        short_ttl_service.WS_TOKEN_TTL_SECONDS = 1  # 1 second TTL

        token = short_ttl_service.create_ws_token(user_id, org_id)

        # Wait for token to expire
        time.sleep(1.5)

        payload = short_ttl_service.validate_ws_token(token)

        assert payload is None

    def test_token_with_wrong_purpose_is_rejected(self, token_service, user_id, org_id):
        """Test that tokens with wrong purpose are rejected.

        This prevents regular JWT tokens from being used as WebSocket tokens.
        """
        import jwt

        # Create a token with wrong purpose
        payload = {
            "sub": user_id,
            "org": org_id,
            "purpose": "api_access",  # Wrong purpose
            "jti": "test_jti",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
        }
        wrong_purpose_token = jwt.encode(
            payload,
            "test_secret_key_12345",
            algorithm="HS256",
        )

        result = token_service.validate_ws_token(wrong_purpose_token)

        assert result is None

    def test_token_cannot_be_reused(self, token_service, user_id, org_id):
        """Test that tokens cannot be reused (single-use).

        This prevents replay attacks.
        """
        token = token_service.create_ws_token(user_id, org_id)

        # First use should succeed
        payload1 = token_service.validate_ws_token(token)
        assert payload1 is not None

        # Second use should fail
        payload2 = token_service.validate_ws_token(token)
        assert payload2 is None


class TestWebSocketTokenEdgeCases:
    """Edge case tests for WebSocket token service."""

    def test_invalid_token_format_is_rejected(self, token_service):
        """Test that invalid token formats are rejected."""
        result = token_service.validate_ws_token("not_a_valid_jwt")
        assert result is None

    def test_empty_token_is_rejected(self, token_service):
        """Test that empty tokens are rejected."""
        result = token_service.validate_ws_token("")
        assert result is None

    def test_token_missing_jti_is_rejected(self, token_service, user_id, org_id):
        """Test that tokens without JTI are rejected."""
        import jwt

        # Create a token without JTI
        payload = {
            "sub": user_id,
            "org": org_id,
            "purpose": "websocket",
            # Missing jti
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
        }
        no_jti_token = jwt.encode(
            payload,
            "test_secret_key_12345",
            algorithm="HS256",
        )

        result = token_service.validate_ws_token(no_jti_token)

        assert result is None

    def test_token_with_wrong_secret_is_rejected(self, user_id, org_id):
        """Test that tokens signed with wrong secret are rejected."""
        # Create token with one secret
        service1 = WebSocketTokenService(secret_key="secret_one")
        token = service1.create_ws_token(user_id, org_id)

        # Try to validate with different secret
        service2 = WebSocketTokenService(secret_key="secret_two")
        result = service2.validate_ws_token(token)

        assert result is None


class TestWebSocketTokenServiceOperations:
    """Tests for token service operations."""

    def test_invalidate_token_prevents_use(self, token_service, user_id, org_id):
        """Test that manually invalidated tokens cannot be used."""
        import jwt

        # Get the JTI that will be used
        token = token_service.create_ws_token(user_id, org_id)
        decoded = jwt.decode(
            token,
            "test_secret_key_12345",
            algorithms=["HS256"],
        )
        jti = decoded["jti"]

        # Create a new token with the same JTI (simulating known JTI)
        # and invalidate it before validation
        token_service.invalidate_token(jti)

        # Now the original token should be rejected
        result = token_service.validate_ws_token(token)
        assert result is None

    def test_each_token_has_unique_jti(self, token_service, user_id, org_id):
        """Test that each token gets a unique JTI."""
        import jwt

        token1 = token_service.create_ws_token(user_id, org_id)
        token2 = token_service.create_ws_token(user_id, org_id)

        decoded1 = jwt.decode(token1, "test_secret_key_12345", algorithms=["HS256"])
        decoded2 = jwt.decode(token2, "test_secret_key_12345", algorithms=["HS256"])

        assert decoded1["jti"] != decoded2["jti"]


class TestWebSocketTokenServiceSingleton:
    """Tests for the token service singleton."""

    def test_get_ws_token_service_returns_singleton(self):
        """get_ws_token_service returns the same instance."""
        service1 = get_ws_token_service()
        service2 = get_ws_token_service()

        assert service1 is service2

    def test_singleton_is_token_service_instance(self):
        """Singleton is a WebSocketTokenService instance."""
        service = get_ws_token_service()

        assert isinstance(service, WebSocketTokenService)
