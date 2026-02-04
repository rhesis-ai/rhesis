"""Connection registry for WebSocket connections.

This module provides a multi-index registry for tracking WebSocket connections
with efficient lookups by organization, user, channel, or connection ID.
"""

import logging
from dataclasses import dataclass, field
from threading import Lock
from typing import Optional

from fastapi import WebSocket

logger = logging.getLogger(__name__)


@dataclass
class ConnectionInfo:
    """Information about a WebSocket connection.

    Attributes:
        websocket: The WebSocket connection object.
        user_id: The ID of the authenticated user.
        org_id: The ID of the user's organization.
        channels: Set of channels this connection is subscribed to.
    """

    websocket: WebSocket
    user_id: str
    org_id: str
    channels: set[str] = field(default_factory=set)


class ConnectionRegistry:
    """Tracks WebSocket connections with multi-index lookups.

    This registry maintains multiple indexes for efficient lookups:
    - By connection ID (primary key)
    - By organization ID (for org-wide broadcasts)
    - By user ID (for user-specific messages)
    - By channel (for pub/sub style messaging)

    Thread-safety is ensured via a lock for all mutating operations.
    """

    def __init__(self):
        """Initialize the connection registry."""
        self._lock = Lock()

        # Primary storage: connection_id -> ConnectionInfo
        self._connections: dict[str, ConnectionInfo] = {}

        # Indexes for efficient lookups
        self._by_org: dict[str, set[str]] = {}  # org_id -> set of connection_ids
        self._by_user: dict[str, set[str]] = {}  # user_id -> set of connection_ids
        self._by_channel: dict[str, set[str]] = {}  # channel -> set of connection_ids

    def add(
        self,
        conn_id: str,
        websocket: WebSocket,
        user_id: str,
        org_id: str,
    ) -> None:
        """Register a new connection.

        Args:
            conn_id: Unique connection identifier.
            websocket: The WebSocket connection object.
            user_id: The authenticated user's ID.
            org_id: The user's organization ID.
        """
        with self._lock:
            # Create connection info
            conn_info = ConnectionInfo(
                websocket=websocket,
                user_id=user_id,
                org_id=org_id,
            )
            self._connections[conn_id] = conn_info

            # Update org index
            if org_id not in self._by_org:
                self._by_org[org_id] = set()
            self._by_org[org_id].add(conn_id)

            # Update user index
            if user_id not in self._by_user:
                self._by_user[user_id] = set()
            self._by_user[user_id].add(conn_id)

            logger.debug(f"Registered connection {conn_id} for user {user_id} in org {org_id}")

    def remove(self, conn_id: str) -> Optional[ConnectionInfo]:
        """Remove a connection and clean up all indexes.

        Args:
            conn_id: The connection ID to remove.

        Returns:
            The removed ConnectionInfo, or None if not found.
        """
        with self._lock:
            conn_info = self._connections.pop(conn_id, None)
            if conn_info is None:
                return None

            # Clean up org index
            org_conns = self._by_org.get(conn_info.org_id)
            if org_conns:
                org_conns.discard(conn_id)
                if not org_conns:
                    del self._by_org[conn_info.org_id]

            # Clean up user index
            user_conns = self._by_user.get(conn_info.user_id)
            if user_conns:
                user_conns.discard(conn_id)
                if not user_conns:
                    del self._by_user[conn_info.user_id]

            # Clean up channel subscriptions
            for channel in conn_info.channels:
                channel_conns = self._by_channel.get(channel)
                if channel_conns:
                    channel_conns.discard(conn_id)
                    if not channel_conns:
                        del self._by_channel[channel]

            logger.debug(f"Removed connection {conn_id}")
            return conn_info

    def get_by_id(self, conn_id: str) -> Optional[WebSocket]:
        """Get a specific connection by ID.

        Args:
            conn_id: The connection ID.

        Returns:
            The WebSocket connection, or None if not found.
        """
        conn_info = self._connections.get(conn_id)
        return conn_info.websocket if conn_info else None

    def get_info_by_id(self, conn_id: str) -> Optional[ConnectionInfo]:
        """Get connection info by ID.

        Args:
            conn_id: The connection ID.

        Returns:
            The ConnectionInfo, or None if not found.
        """
        return self._connections.get(conn_id)

    def get_by_org(self, org_id: str) -> list[WebSocket]:
        """Get all connections for an organization.

        Args:
            org_id: The organization ID.

        Returns:
            List of WebSocket connections for the organization.
        """
        conn_ids = self._by_org.get(org_id, set())
        return [self._connections[cid].websocket for cid in conn_ids if cid in self._connections]

    def get_by_user(self, user_id: str) -> list[WebSocket]:
        """Get all connections for a user.

        Args:
            user_id: The user ID.

        Returns:
            List of WebSocket connections for the user.
        """
        conn_ids = self._by_user.get(user_id, set())
        return [self._connections[cid].websocket for cid in conn_ids if cid in self._connections]

    def get_by_channel(self, channel: str) -> list[WebSocket]:
        """Get all connections subscribed to a channel.

        Args:
            channel: The channel name.

        Returns:
            List of WebSocket connections subscribed to the channel.
        """
        conn_ids = self._by_channel.get(channel, set())
        return [self._connections[cid].websocket for cid in conn_ids if cid in self._connections]

    def add_subscription(self, conn_id: str, channel: str) -> bool:
        """Subscribe a connection to a channel.

        Args:
            conn_id: The connection ID.
            channel: The channel to subscribe to.

        Returns:
            True if subscription was added, False if connection not found.
        """
        with self._lock:
            conn_info = self._connections.get(conn_id)
            if conn_info is None:
                return False

            # Add to connection's channels
            conn_info.channels.add(channel)

            # Update channel index
            if channel not in self._by_channel:
                self._by_channel[channel] = set()
            self._by_channel[channel].add(conn_id)

            logger.debug(f"Connection {conn_id} subscribed to channel {channel}")
            return True

    def remove_subscription(self, conn_id: str, channel: str) -> bool:
        """Unsubscribe a connection from a channel.

        Args:
            conn_id: The connection ID.
            channel: The channel to unsubscribe from.

        Returns:
            True if subscription was removed, False if not found.
        """
        with self._lock:
            conn_info = self._connections.get(conn_id)
            if conn_info is None:
                return False

            # Remove from connection's channels
            conn_info.channels.discard(channel)

            # Update channel index
            channel_conns = self._by_channel.get(channel)
            if channel_conns:
                channel_conns.discard(conn_id)
                if not channel_conns:
                    del self._by_channel[channel]

            logger.debug(f"Connection {conn_id} unsubscribed from channel {channel}")
            return True

    def get_subscriptions(self, conn_id: str) -> set[str]:
        """Get all channels a connection is subscribed to.

        Args:
            conn_id: The connection ID.

        Returns:
            Set of channel names, or empty set if connection not found.
        """
        conn_info = self._connections.get(conn_id)
        return set(conn_info.channels) if conn_info else set()

    @property
    def connection_count(self) -> int:
        """Get the total number of active connections."""
        return len(self._connections)

    def get_stats(self) -> dict:
        """Get registry statistics.

        Returns:
            Dictionary with connection counts by various dimensions.
        """
        return {
            "total_connections": len(self._connections),
            "organizations": len(self._by_org),
            "users": len(self._by_user),
            "channels": len(self._by_channel),
        }
