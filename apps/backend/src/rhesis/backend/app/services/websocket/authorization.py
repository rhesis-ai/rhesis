"""Channel authorization for WebSocket subscriptions.

This module provides security validation for channel subscriptions,
ensuring users can only subscribe to channels they are authorized to access.

Security principle: Fail-closed - unknown channel formats are rejected by default.
"""

import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from rhesis.backend.app.models.user import User

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from rhesis.backend.app.auth.principal import Principal

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _ResourceChannelRule:
    """How to authorize a protected resource channel (SP11).

    Attributes:
        capability: PDP capability checked for subscription (read access).
        model_name: ORM class name in ``rhesis.backend.app.models`` whose row
            carries the ``project_id``, or ``None`` when the channel id is not a
            persisted resource (ephemeral) — then no per-project scope is resolved.
        id_is_project: ``True`` when the channel id IS the project id
            (``project:{id}`` channels).
    """

    capability: str
    model_name: Optional[str]
    id_is_project: bool = False


# Protected resource channels → authorization rule, keyed by prefix WITHOUT the
# trailing colon.  ``ChannelAuthorizer.PROTECTED_RESOURCE_PREFIXES`` is derived
# from this map so the two never drift.
_RESOURCE_CHANNEL_RULES: dict[str, _ResourceChannelRule] = {
    "test_run": _ResourceChannelRule("test_run:read", "TestRun"),
    "test_set": _ResourceChannelRule("test_set:read", "TestSet"),
    "architect": _ResourceChannelRule("architect:read", "ArchitectSession"),
    "project": _ResourceChannelRule("project:read", None, id_is_project=True),
    # preflight:{correlation_id} is an ephemeral operation channel with no
    # persisted row; the server-generated correlation_id is returned only to the
    # initiator, so org membership + the unguessable id is the boundary.
    "preflight": _ResourceChannelRule("preflight:create", None),
}


class ChannelAuthorizer:
    """Validates user authorization for channel subscriptions.

    Channel format: "resource_type:resource_id"
    Examples: "test_run:uuid", "org:uuid", "user:uuid"

    Authorization rules:
    - user:{id} - Only the user themselves can subscribe
    - org:{id} - Only users in that organization can subscribe
    - test_run:{id}, test_set:{id}, project:{id}, architect:{id} - PDP-checked
      against the resource's project (per-project separation, SP11)
    - Unknown formats are rejected (fail-closed)
    """

    # Channels scoped to specific user
    USER_SCOPED_PREFIXES = ["user:"]

    # Channels scoped to organization
    ORG_SCOPED_PREFIXES = ["org:"]

    # Resource channels that require PDP authorization against the resource's
    # project.  Derived from _RESOURCE_CHANNEL_RULES so it cannot drift.
    PROTECTED_RESOURCE_PREFIXES = [f"{name}:" for name in _RESOURCE_CHANNEL_RULES]

    # UUID regex pattern for validation
    UUID_PATTERN = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        re.IGNORECASE,
    )

    async def authorize(
        self,
        user: User,
        channel: str,
        db: "Optional[Session]" = None,
        principal: "Optional[Principal]" = None,
    ) -> tuple[bool, Optional[str]]:
        """Check if user can subscribe to channel.

        Args:
            user: The authenticated user requesting subscription.
            channel: The channel name to subscribe to.
            db: Optional SQLAlchemy session.  When provided,
                :meth:`_authorize_resource_channel` calls :func:`authorize`
                (SP11) to verify the caller holds the channel resource's read
                capability via the active PDP.

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
            return await self._authorize_resource_channel(
                user, prefix, resource_id, db=db, principal=principal
            )

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
        self,
        user: User,
        prefix: str,
        resource_id: str,
        db: "Optional[Session]" = None,
        principal: "Optional[Principal]" = None,
    ) -> tuple[bool, Optional[str]]:
        """Authorize subscription to a resource-scoped channel.

        SP11: when *db* is provided, the channel resource's ``project_id`` is
        resolved and the caller's read capability is verified for *that project*
        via :func:`~rhesis.backend.app.auth.rbac.authorize` — true per-project
        separation, not just org membership.  Without *db*, any authenticated
        org member is allowed (legacy path).

        A persisted resource that is not visible in the caller's organization is
        denied (fail-closed), which also blocks cross-org channel subscription.
        """
        rule = _RESOURCE_CHANNEL_RULES.get(prefix.rstrip(":"))
        if rule is None:
            # Defensive: PROTECTED_RESOURCE_PREFIXES is derived from the rules
            # map, so this should be unreachable.
            logger.warning("No channel rule for prefix %s (user %s)", prefix, user.id)
            return False, "Unauthorized channel type"

        if db is None:
            # Legacy path (no session available): allow any authenticated org member.
            logger.info(
                "User %s subscribing to %s%s (no PDP session)", user.id, prefix, resource_id
            )
            return True, None

        # Resolve the project scope of the channel resource so the PDP enforces
        # per-project membership rather than mere org membership.
        project_id, resolvable = self._resolve_channel_project_id(user, rule, resource_id, db)
        expects_persisted = rule.id_is_project or rule.model_name is not None
        if expects_persisted and not resolvable:
            # Persisted resource not visible in the caller's org → deny.
            logger.warning(
                "WebSocket subscription denied: %s%s not found in org %s (user %s)",
                prefix,
                resource_id,
                user.organization_id,
                user.id,
            )
            return False, "Resource not found or access denied"

        from rhesis.backend.app.auth.principal import resolve_principal
        from rhesis.backend.app.auth.rbac import authorize

        if principal is None:
            principal = resolve_principal(user)
        if not authorize(principal, rule.capability, project_id=project_id, db=db):
            logger.warning(
                "WebSocket subscription denied: user %s lacks '%s' for %s%s (project=%s)",
                user.id,
                rule.capability,
                prefix,
                resource_id,
                project_id,
            )
            return False, "Subscription denied: insufficient permissions"

        logger.info(
            "User %s authorized for %s%s (project=%s)",
            user.id,
            prefix,
            resource_id,
            project_id,
        )
        return True, None

    def _resolve_channel_project_id(
        self,
        user: User,
        rule: _ResourceChannelRule,
        resource_id: str,
        db: "Session",
    ) -> tuple[Optional[UUID], bool]:
        """Resolve the project a channel resource belongs to.

        Returns ``(project_id, resolvable)``:

        - ``project_id``: the resource's project ``UUID`` (the resource's own id
          for ``project:`` channels), or ``None`` when the resource has no
          project or the channel id is ephemeral (no backing model).
        - ``resolvable``: ``True`` when a persisted row was found in the caller's
          org, or when the rule has no backing model (ephemeral channel).
          ``False`` means a persisted resource was expected but not found — the
          caller should deny (fail-closed).

        The lookup bypasses the ORM auto-filter (which, with no project in the WS
        session scope, would otherwise hide project-scoped rows by appending
        ``project_id IS NULL``) and applies an explicit ``organization_id`` filter
        so cross-org rows stay invisible.
        """
        from rhesis.backend.app.scope import bypass_tenant_filter

        try:
            if rule.id_is_project:
                from rhesis.backend.app.models.project import Project

                with bypass_tenant_filter():
                    row = (
                        db.query(Project)
                        .filter_by(id=resource_id, organization_id=user.organization_id)
                        .first()
                    )
                if row is None:
                    return None, False
                return row.id, True

            if rule.model_name is None:
                # Ephemeral channel (e.g. preflight): no persisted resource.
                return None, True

            from rhesis.backend.app import models

            model = getattr(models, rule.model_name)
            with bypass_tenant_filter():
                row = (
                    db.query(model)
                    .filter_by(id=resource_id, organization_id=user.organization_id)
                    .first()
                )
            if row is None:
                return None, False
            return getattr(row, "project_id", None), True
        except Exception:
            # Fail-closed: a lookup error must not grant access to a persisted
            # resource channel.
            logger.exception(
                "Error resolving project for %s channel %s (user %s) — denying",
                rule.model_name,
                resource_id,
                user.id,
            )
            return None, False


# Singleton instance
_authorizer: Optional[ChannelAuthorizer] = None


def get_channel_authorizer() -> ChannelAuthorizer:
    """Get or create the channel authorizer singleton."""
    global _authorizer
    if _authorizer is None:
        _authorizer = ChannelAuthorizer()
    return _authorizer
