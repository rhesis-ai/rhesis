"""
Tests for service delegation token functionality.

This module tests:
- Creation of delegation tokens
- Token payload structure
- Custom expiration times
- Integration with JWT utilities
"""

from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
from jose import jwt

from rhesis.backend.app.auth.token_utils import (
    ALGORITHM,
    create_service_delegation_token,
    get_secret_key,
)
from rhesis.backend.app.models.user import User


class TestDelegationTokens:
    """Test service delegation token creation and structure."""

    @pytest.fixture
    def test_user(self):
        """Create a mock user for testing."""
        user = Mock(spec=User)
        user.id = "user-123"
        user.email = "test@example.com"
        user.organization_id = "org-456"
        return user

    def test_create_token(self, test_user):
        """Test basic token creation."""
        token = create_service_delegation_token(test_user, "polyphemus")
        assert isinstance(token, str)
        assert len(token) > 0

        # Decode and verify payload
        payload = jwt.decode(token, get_secret_key(), algorithms=[ALGORITHM])
        assert payload["type"] == "service_delegation"
        assert payload["target_service"] == "polyphemus"
        assert payload["user"]["id"] == str(test_user.id)
        assert payload["user"]["email"] == test_user.email
        assert payload["user"]["organization_id"] == str(test_user.organization_id)

    def test_token_expiration(self, test_user):
        """Test custom expiration time."""
        token = create_service_delegation_token(test_user, "polyphemus", expires_minutes=10)
        payload = jwt.decode(token, get_secret_key(), algorithms=[ALGORITHM])

        exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        iat_time = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
        delta = (exp_time - iat_time).total_seconds() / 60

        # Allow small margin for execution time
        assert 9 < delta < 11  # ~10 minutes

    def test_token_default_expiration(self, test_user):
        """Test default expiration time (5 minutes)."""
        token = create_service_delegation_token(test_user, "polyphemus")
        payload = jwt.decode(token, get_secret_key(), algorithms=[ALGORITHM])

        exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        iat_time = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
        delta = (exp_time - iat_time).total_seconds() / 60

        # Should be ~5 minutes by default
        assert 4 < delta < 6

    def test_token_includes_nbf(self, test_user):
        """Test token includes 'not before' claim."""
        token = create_service_delegation_token(test_user, "polyphemus")
        payload = jwt.decode(token, get_secret_key(), algorithms=[ALGORITHM])

        assert "nbf" in payload
        assert "iat" in payload

        nbf_time = datetime.fromtimestamp(payload["nbf"], tz=timezone.utc)
        iat_time = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)

        # NBF should be same as IAT (token valid immediately)
        assert abs((nbf_time - iat_time).total_seconds()) < 1

    def test_token_for_different_services(self, test_user):
        """Test creating tokens for different target services."""
        polyphemus_token = create_service_delegation_token(test_user, "polyphemus")
        other_token = create_service_delegation_token(test_user, "other-service")

        polyphemus_payload = jwt.decode(polyphemus_token, get_secret_key(), algorithms=[ALGORITHM])
        other_payload = jwt.decode(other_token, get_secret_key(), algorithms=[ALGORITHM])

        assert polyphemus_payload["target_service"] == "polyphemus"
        assert other_payload["target_service"] == "other-service"

    def test_user_without_org(self, test_user):
        """Test token creation for user without organization."""
        test_user.organization_id = None

        token = create_service_delegation_token(test_user, "polyphemus")
        payload = jwt.decode(token, get_secret_key(), algorithms=[ALGORITHM])

        assert payload["user"]["organization_id"] is None
        assert payload["user"]["id"] == str(test_user.id)
        assert payload["user"]["email"] == test_user.email
