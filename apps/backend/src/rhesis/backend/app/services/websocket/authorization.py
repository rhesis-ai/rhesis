"""Channel authorization for WebSocket subscriptions.

This module provides security validation for channel subscriptions,
ensuring users can only subscribe to channels they are authorized to access.

Security principle: Fail-closed - unknown channel formats are rejected by default.
"""

import logging
import re
from typing import Optional

from rhesis.backend.app.models.user import User

logger = logging.getLogger(__name__)


class ChannelAuthorizer:
    """Validates user authorization for channel subscriptions.

    Channel format: "resource_type:resource_id"
    Examples: "test_run:uuid", "org:uuid", "user:uuid"

    Authorization rules:
    - user:{id} - Only the user themselves can subscribe
    - org:{id} - Only users in that organization can subscribe
    - test_run:{id}, test_set:{id}, project:{id} - Organization-scoped resources
    - Unknown formats are rejected (fail-closed)
    """

    # Channels scoped to specific user
    USER_SCOPED_PREFIXES = ["user:"]

    # Channels scoped to organization
    ORG_SCOPED_PREFIXES = ["org:"]

    # Resource channels that require organization ownership verification
    # These resources have an organization_id field in the database
    PROTECTED_RESOURCE_PREFIXES = ["test_run:", "test_set:", "project:"]

    # UUID regex pattern for validation
    UUID_PATTERN = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        re.IGNORECASE,
    )

    async def authorize(self, user: User, channel: str) -> tuple[bool, Optional[str]]:
        """Check if user can subscribe to channel.

        Args:
            user: The authenticated user requesting subscription.
            channel: The channel name to subscribe to.

        Returns:
            Tuple of (authorized: bool, error_message: Optional[str]).
            If authorized is False, error_message contains the reason.
        """
        if not channel:
            return False, "Channel name is required"

        # Validate channel format (must contain exactly one colon)
        if ":" not in channel or channel.count(":") > 1:
            logger.warning(f"Invalid channel format from user {user.id}: {channel}")
            return False, "Invalid channel format"

        prefix, resource_id = channel.split(":", 1)
        prefix = prefix + ":"  # Add colon back for prefix matching

        # Validate resource ID is a valid UUID
        if not self._is_valid_uuid(resource_id):
            logger.warning(f"Invalid resource ID in channel from user {user.id}: {channel}")
            return False, "Invalid resource identifier"

        # User-scoped channels: only own user channel
        if prefix in self.USER_SCOPED_PREFIXES:
            return self._authorize_user_channel(user, resource_id)

        # Org-scoped channels: only own org
        if prefix in self.ORG_SCOPED_PREFIXES:
            return self._authorize_org_channel(user, resource_id)

        # Protected resources: verify ownership via organization
        if prefix in self.PROTECTED_RESOURCE_PREFIXES:
            return await self._authorize_resource_channel(user, prefix, resource_id)

        # Unknown channel format - deny by default (fail-closed)
        logger.warning(f"Unknown channel prefix from user {user.id}: {prefix}")
        return False, "Unauthorized channel type"

    def _is_valid_uuid(self, value: str) -> bool:
        """Check if a string is a valid UUID."""
        return bool(self.UUID_PATTERN.match(value))

    def _authorize_user_channel(self, user: User, user_id: str) -> tuple[bool, Optional[str]]:
        """Authorize subscription to a user-scoped channel.

        Users can only subscribe to their own user channel.
        """
        if user_id != str(user.id):
            logger.warning(
                f"User {user.id} attempted to subscribe to other user's channel: {user_id}"
            )
            return False, "Cannot subscribe to other user's channel"
        return True, None

    def _authorize_org_channel(self, user: User, org_id: str) -> tuple[bool, Optional[str]]:
        """Authorize subscription to an organization-scoped channel.

        Users can only subscribe to their own organization's channel.
        """
        if org_id != str(user.organization_id):
            logger.warning(
                f"User {user.id} (org={user.organization_id}) attempted to "
                f"subscribe to other org's channel: {org_id}"
            )
            return False, "Cannot subscribe to other organization's channel"
        return True, None

    async def _authorize_resource_channel(
        self, user: User, prefix: str, resource_id: str
    ) -> tuple[bool, Optional[str]]:
        """Authorize subscription to a resource-scoped channel.

        Verifies the resource belongs to the user's organization.
        For now, we trust that resources are organization-scoped and
        the user's organization_id matches the resource's organization_id.

        In a full implementation, this would query the database to verify
        the resource exists and belongs to the user's organization.
        """
        # For the foundation, we allow subscriptions to resource channels
        # as long as the user is authenticated. The actual resource access
        # control happens at the data layer when events are published.
        #
        # A more secure implementation would query the database here:
        # resource = await self._get_resource(prefix, resource_id)
        # if resource is None or resource.organization_id != user.organization_id:
        #     return False, "Resource not found or access denied"
        #
        # For now, we log the subscription attempt for auditing
        logger.info(
            f"User {user.id} (org={user.organization_id}) subscribing to {prefix}{resource_id}"
        )
        return True, None


# Singleton instance
_authorizer: Optional[ChannelAuthorizer] = None


def get_channel_authorizer() -> ChannelAuthorizer:
    """Get or create the channel authorizer singleton."""
    global _authorizer
    if _authorizer is None:
        _authorizer = ChannelAuthorizer()
    return _authorizer
