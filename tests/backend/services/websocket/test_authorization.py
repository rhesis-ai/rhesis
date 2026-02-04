"""Security tests for WebSocket channel authorization.

These tests verify that the ChannelAuthorizer correctly enforces
access control for channel subscriptions, preventing unauthorized
cross-organization and cross-user data access.
"""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from rhesis.backend.app.services.websocket.authorization import (
    ChannelAuthorizer,
    get_channel_authorizer,
)


@pytest.fixture
def authorizer():
    """Create a fresh ChannelAuthorizer instance."""
    return ChannelAuthorizer()


@pytest.fixture
def mock_user():
    """Create a mock user with specific IDs."""
    user = MagicMock()
    user.id = uuid4()
    user.organization_id = uuid4()
    user.email = "test@example.com"
    return user


@pytest.fixture
def other_user():
    """Create another mock user (different org)."""
    user = MagicMock()
    user.id = uuid4()
    user.organization_id = uuid4()
    user.email = "other@example.com"
    return user


class TestChannelAuthorizationSecurity:
    """Security tests for channel authorization.

    These tests verify the security boundary between users and organizations.
    """

    @pytest.mark.asyncio
    async def test_user_cannot_subscribe_to_other_users_channel(
        self, authorizer, mock_user, other_user
    ):
        """SECURITY: User A cannot subscribe to user:{user_B_id}.

        This prevents unauthorized access to user-specific notifications.
        """
        # Attempt to subscribe to another user's channel
        other_user_channel = f"user:{other_user.id}"

        authorized, error = await authorizer.authorize(mock_user, other_user_channel)

        assert authorized is False
        assert error is not None
        assert "other user" in error.lower()

    @pytest.mark.asyncio
    async def test_user_cannot_subscribe_to_other_orgs_channel(
        self, authorizer, mock_user, other_user
    ):
        """SECURITY: User A cannot subscribe to org:{other_org_id}.

        This prevents cross-organization data leakage.
        """
        # Attempt to subscribe to another org's channel
        other_org_channel = f"org:{other_user.organization_id}"

        authorized, error = await authorizer.authorize(mock_user, other_org_channel)

        assert authorized is False
        assert error is not None
        assert "other organization" in error.lower()

    @pytest.mark.asyncio
    async def test_user_can_subscribe_to_own_user_channel(
        self, authorizer, mock_user
    ):
        """User CAN subscribe to their own user channel."""
        own_channel = f"user:{mock_user.id}"

        authorized, error = await authorizer.authorize(mock_user, own_channel)

        assert authorized is True
        assert error is None

    @pytest.mark.asyncio
    async def test_user_can_subscribe_to_own_org_channel(
        self, authorizer, mock_user
    ):
        """User CAN subscribe to their own organization's channel."""
        own_org_channel = f"org:{mock_user.organization_id}"

        authorized, error = await authorizer.authorize(mock_user, own_org_channel)

        assert authorized is True
        assert error is None

    @pytest.mark.asyncio
    async def test_unknown_channel_format_is_rejected(
        self, authorizer, mock_user
    ):
        """SECURITY: Unknown channel formats are rejected (fail-closed).

        This prevents potential bypasses using new/unknown channel types.
        """
        unknown_channel = f"unknown_type:{uuid4()}"

        authorized, error = await authorizer.authorize(mock_user, unknown_channel)

        assert authorized is False
        assert error is not None

    @pytest.mark.asyncio
    async def test_malformed_channel_id_is_rejected(
        self, authorizer, mock_user
    ):
        """SECURITY: Malformed resource IDs are rejected.

        This prevents injection attacks and malformed requests.
        """
        # Non-UUID resource ID
        malformed_channel = "test_run:not-a-valid-uuid"

        authorized, error = await authorizer.authorize(mock_user, malformed_channel)

        assert authorized is False
        assert error is not None
        assert "invalid" in error.lower()


class TestChannelAuthorizationEdgeCases:
    """Edge case tests for channel authorization."""

    @pytest.mark.asyncio
    async def test_empty_channel_is_rejected(self, authorizer, mock_user):
        """Empty channel name is rejected."""
        authorized, error = await authorizer.authorize(mock_user, "")

        assert authorized is False
        assert error is not None

    @pytest.mark.asyncio
    async def test_none_channel_is_rejected(self, authorizer, mock_user):
        """None channel is rejected."""
        authorized, error = await authorizer.authorize(mock_user, None)

        assert authorized is False
        assert error is not None

    @pytest.mark.asyncio
    async def test_channel_without_colon_is_rejected(self, authorizer, mock_user):
        """Channel without colon separator is rejected."""
        authorized, error = await authorizer.authorize(mock_user, "nocolon")

        assert authorized is False
        assert error is not None

    @pytest.mark.asyncio
    async def test_channel_with_multiple_colons_is_rejected(
        self, authorizer, mock_user
    ):
        """Channel with multiple colons is rejected."""
        authorized, error = await authorizer.authorize(
            mock_user, f"test:run:{uuid4()}"
        )

        assert authorized is False
        assert error is not None

    @pytest.mark.asyncio
    async def test_protected_resource_channels_allowed_for_authenticated_users(
        self, authorizer, mock_user
    ):
        """Protected resource channels are allowed for authenticated users.

        Note: Full authorization would verify resource ownership in database.
        """
        test_run_channel = f"test_run:{uuid4()}"

        authorized, error = await authorizer.authorize(mock_user, test_run_channel)

        assert authorized is True
        assert error is None

    @pytest.mark.asyncio
    async def test_test_set_channel_allowed(self, authorizer, mock_user):
        """Test set channels are allowed for authenticated users."""
        test_set_channel = f"test_set:{uuid4()}"

        authorized, error = await authorizer.authorize(mock_user, test_set_channel)

        assert authorized is True
        assert error is None

    @pytest.mark.asyncio
    async def test_project_channel_allowed(self, authorizer, mock_user):
        """Project channels are allowed for authenticated users."""
        project_channel = f"project:{uuid4()}"

        authorized, error = await authorizer.authorize(mock_user, project_channel)

        assert authorized is True
        assert error is None


class TestChannelAuthorizerSingleton:
    """Tests for the authorizer singleton."""

    def test_get_channel_authorizer_returns_singleton(self):
        """get_channel_authorizer returns the same instance."""
        authorizer1 = get_channel_authorizer()
        authorizer2 = get_channel_authorizer()

        assert authorizer1 is authorizer2

    def test_authorizer_is_channel_authorizer_instance(self):
        """Singleton is a ChannelAuthorizer instance."""
        authorizer = get_channel_authorizer()

        assert isinstance(authorizer, ChannelAuthorizer)
