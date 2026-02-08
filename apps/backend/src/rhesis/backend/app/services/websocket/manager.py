"""WebSocket connection manager.

This module provides the WebSocketManager class that handles:
- Connection lifecycle (connect, disconnect)
- Channel subscriptions
- Unified broadcasting via target abstraction
- Message handling and routing
"""

import asyncio
import logging
import uuid
from typing import Optional

from fastapi import WebSocket

from rhesis.backend.app.models.user import User
from rhesis.backend.app.schemas.websocket import (
    ChannelTarget,
    ConnectionTarget,
    EventType,
    OrgTarget,
    Target,
    UserTarget,
    WebSocketMessage,
)
from rhesis.backend.app.services.websocket.authorization import get_channel_authorizer
from rhesis.backend.app.services.websocket.handlers.chat import handle_chat_message
from rhesis.backend.app.services.websocket.rate_limiter import get_rate_limiter
from rhesis.backend.app.services.websocket.registry import ConnectionRegistry

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connections and broadcasting.

    This manager provides a unified interface for:
    - Registering and tracking connections
    - Managing channel subscriptions
    - Broadcasting messages to various targets (org, user, channel, connection)
    - Handling incoming messages

    The manager uses a ConnectionRegistry for efficient multi-index lookups
    and supports Redis pub/sub for multi-instance deployments.
    """

    def __init__(self):
        """Initialize the WebSocket manager."""
        self._registry = ConnectionRegistry()
        self._redis_listener_task: Optional[asyncio.Task] = None

    async def connect(self, websocket: WebSocket, user: User) -> str:
        """Register a new authenticated connection.

        Args:
            websocket: The WebSocket connection.
            user: The authenticated user.

        Returns:
            The unique connection ID for this connection.
        """
        # Generate unique connection ID
        conn_id = f"ws_{uuid.uuid4().hex[:12]}"

        # Register in the registry
        self._registry.add(
            conn_id=conn_id,
            websocket=websocket,
            user_id=str(user.id),
            org_id=str(user.organization_id),
        )

        logger.info(
            f"WebSocket connected: {conn_id} (user={user.email}, org={user.organization_id})"
        )
        return conn_id

    def disconnect(self, conn_id: str) -> None:
        """Clean up a connection and all its subscriptions.

        Args:
            conn_id: The connection ID to disconnect.
        """
        conn_info = self._registry.remove(conn_id)

        # Clean up rate limiter tracking
        rate_limiter = get_rate_limiter()
        rate_limiter.remove_connection(conn_id)

        if conn_info:
            logger.info(f"WebSocket disconnected: {conn_id}")
        else:
            logger.warning(f"Attempted to disconnect unknown connection: {conn_id}")

    def subscribe(self, conn_id: str, channel: str) -> bool:
        """Subscribe a connection to a channel.

        Args:
            conn_id: The connection ID.
            channel: The channel to subscribe to.

        Returns:
            True if subscription was successful, False otherwise.
        """
        return self._registry.add_subscription(conn_id, channel)

    def unsubscribe(self, conn_id: str, channel: str) -> bool:
        """Unsubscribe a connection from a channel.

        Args:
            conn_id: The connection ID.
            channel: The channel to unsubscribe from.

        Returns:
            True if unsubscription was successful, False otherwise.
        """
        return self._registry.remove_subscription(conn_id, channel)

    def get_subscriptions(self, conn_id: str) -> set[str]:
        """Get all channels a connection is subscribed to.

        Args:
            conn_id: The connection ID.

        Returns:
            Set of channel names.
        """
        return self._registry.get_subscriptions(conn_id)

    async def broadcast(self, message: WebSocketMessage, target: Target) -> int:
        """Broadcast a message to a target.

        This unified broadcast method handles all target types:
        - OrgTarget: Send to all connections in an organization
        - UserTarget: Send to all connections for a specific user
        - ChannelTarget: Send to all subscribers of a channel
        - ConnectionTarget: Send to a specific connection

        Args:
            message: The WebSocket message to send.
            target: The broadcast target.

        Returns:
            Number of connections the message was sent to.
        """
        websockets = self._resolve_target(target)
        return await self._send_to_websockets(message, websockets)

    def _resolve_target(self, target: Target) -> list[WebSocket]:
        """Resolve a target to a list of WebSocket connections.

        Args:
            target: The broadcast target.

        Returns:
            List of WebSocket connections matching the target.

        Raises:
            ValueError: If the target type is unknown.
        """
        if isinstance(target, OrgTarget):
            return self._registry.get_by_org(target.org_id)
        elif isinstance(target, UserTarget):
            return self._registry.get_by_user(target.user_id)
        elif isinstance(target, ChannelTarget):
            return self._registry.get_by_channel(target.channel)
        elif isinstance(target, ConnectionTarget):
            ws = self._registry.get_by_id(target.connection_id)
            return [ws] if ws else []
        else:
            raise ValueError(f"Unknown target type: {type(target)}")

    async def _send_to_websockets(
        self, message: WebSocketMessage, websockets: list[WebSocket]
    ) -> int:
        """Send a message to a list of WebSocket connections.

        Args:
            message: The message to send.
            websockets: List of WebSocket connections.

        Returns:
            Number of connections the message was successfully sent to.
        """
        if not websockets:
            return 0

        sent_count = 0
        message_dict = message.model_dump(mode="json")

        for ws in websockets:
            try:
                await ws.send_json(message_dict)
                sent_count += 1
            except Exception as e:
                logger.warning(f"Failed to send message to WebSocket: {e}")

        logger.debug(f"Broadcast {message.type} to {sent_count}/{len(websockets)} connections")
        return sent_count

    async def handle_message(self, conn_id: str, user: User, message: WebSocketMessage) -> None:
        """Route and handle an incoming WebSocket message.

        This method routes messages based on their EventType:
        - SUBSCRIBE/UNSUBSCRIBE: Manage channel subscriptions
        - PING: Respond with PONG
        - Other types: Can be extended for specific use cases

        Args:
            conn_id: The connection ID that sent the message.
            user: The authenticated user.
            message: The incoming message.
        """
        # Security: Check rate limit before processing
        rate_limiter = get_rate_limiter()
        if not rate_limiter.is_allowed(conn_id):
            logger.warning(f"Rate limit exceeded for connection {conn_id}")
            await self._send_error(conn_id, "Rate limit exceeded. Try again later.")
            return

        logger.debug(f"Handling message type={message.type} from conn={conn_id}")

        if message.type == EventType.SUBSCRIBE:
            await self._handle_subscribe(conn_id, user, message)
        elif message.type == EventType.UNSUBSCRIBE:
            await self._handle_unsubscribe(conn_id, message)
        elif message.type == EventType.PING:
            await self._handle_ping(conn_id)
        elif message.type == EventType.CHAT_MESSAGE:
            await handle_chat_message(self, conn_id, user, message)
        else:
            # Log unhandled message types - can be extended for specific use cases
            logger.debug(f"Unhandled message type: {message.type}")

    async def _handle_subscribe(self, conn_id: str, user: User, message: WebSocketMessage) -> None:
        """Handle a subscribe request with authorization.

        Args:
            conn_id: The connection ID.
            user: The authenticated user making the request.
            message: The subscribe message (channel in payload).
        """
        channel = message.payload.get("channel") if message.payload else None
        if not channel:
            await self._send_error(conn_id, "Missing channel in subscribe request")
            return

        # Security: Authorize channel subscription
        authorizer = get_channel_authorizer()
        authorized, error_message = await authorizer.authorize(user, channel)
        if not authorized:
            logger.warning(
                f"Unauthorized subscription attempt by user {user.id} to {channel}: {error_message}"
            )
            await self._send_error(conn_id, error_message or "Subscription denied")
            return

        success = self.subscribe(conn_id, channel)
        if success:
            await self.broadcast(
                WebSocketMessage(
                    type=EventType.SUBSCRIBED,
                    channel=channel,
                    correlation_id=message.correlation_id,
                ),
                ConnectionTarget(connection_id=conn_id),
            )
            logger.info(f"Connection {conn_id} subscribed to {channel}")
        else:
            await self._send_error(conn_id, "Failed to subscribe to channel")

    async def _handle_unsubscribe(self, conn_id: str, message: WebSocketMessage) -> None:
        """Handle an unsubscribe request.

        Args:
            conn_id: The connection ID.
            message: The unsubscribe message (channel in payload).
        """
        channel = message.payload.get("channel") if message.payload else None
        if not channel:
            await self._send_error(conn_id, "Missing channel in unsubscribe request")
            return

        success = self.unsubscribe(conn_id, channel)
        if success:
            await self.broadcast(
                WebSocketMessage(
                    type=EventType.UNSUBSCRIBED,
                    channel=channel,
                    correlation_id=message.correlation_id,
                ),
                ConnectionTarget(connection_id=conn_id),
            )
            logger.info(f"Connection {conn_id} unsubscribed from {channel}")
        else:
            await self._send_error(conn_id, f"Failed to unsubscribe from {channel}")

    async def _handle_ping(self, conn_id: str) -> None:
        """Handle a ping request by sending a pong response.

        Args:
            conn_id: The connection ID.
        """
        await self.broadcast(
            WebSocketMessage(type=EventType.PONG),
            ConnectionTarget(connection_id=conn_id),
        )

    async def _send_error(self, conn_id: str, error_message: str) -> None:
        """Send an error message to a specific connection.

        Args:
            conn_id: The connection ID.
            error_message: The error message to send.
        """
        await self.broadcast(
            WebSocketMessage(
                type=EventType.ERROR,
                payload={"error": error_message},
            ),
            ConnectionTarget(connection_id=conn_id),
        )

    def get_connection_info(self, conn_id: str):
        """Get information about a connection.

        Args:
            conn_id: The connection ID.

        Returns:
            ConnectionInfo or None if not found.
        """
        return self._registry.get_info_by_id(conn_id)

    @property
    def connection_count(self) -> int:
        """Get the total number of active connections."""
        return self._registry.connection_count

    def get_stats(self) -> dict:
        """Get manager statistics.

        Returns:
            Dictionary with connection statistics.
        """
        return self._registry.get_stats()


# Global WebSocket manager instance
ws_manager = WebSocketManager()
