"""WebSocket event types, message schemas, and broadcast targets.

This module defines the core schemas for the WebSocket infrastructure:
- EventType: Enum of all supported event types
- WebSocketMessage: Pydantic model for WebSocket messages
- Target types: Modular broadcast targets (OrgTarget, UserTarget, ChannelTarget, ConnectionTarget)
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, Union

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """WebSocket event types.

    Connection lifecycle events handle the WebSocket connection state.
    Subscription events manage channel subscriptions.
    Generic events are extensible for use-case specific implementations.

    Note: Use-case specific event types (e.g., CHAT_*, TEST_RUN_*) will be
    added when those integrations are implemented.
    """

    # Connection lifecycle
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    PING = "ping"
    PONG = "pong"

    # Subscriptions
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    SUBSCRIBED = "subscribed"
    UNSUBSCRIBED = "unsubscribed"

    # Generic events (use-case specific events added as needed)
    NOTIFICATION = "notification"
    MESSAGE = "message"

    # Chat events (for playground)
    CHAT_MESSAGE = "chat.message"  # User sends message to endpoint
    CHAT_RESPONSE = "chat.response"  # Complete response from endpoint
    CHAT_ERROR = "chat.error"  # Error during endpoint invocation


class WebSocketMessage(BaseModel):
    """WebSocket message schema.

    All messages sent over WebSocket connections follow this schema.

    Attributes:
        type: The event type determining how the message is handled.
        channel: Optional channel name for subscription-related messages.
        payload: Optional arbitrary data payload.
        correlation_id: Optional ID to correlate requests with responses,
            essential for streaming and async request/response patterns.
    """

    type: EventType = Field(..., description="Event type for message routing")
    channel: Optional[str] = Field(None, description="Channel name for subscriptions")
    payload: Optional[dict[str, Any]] = Field(None, description="Message payload data")
    correlation_id: Optional[str] = Field(
        None, description="Correlation ID for request/response matching"
    )

    model_config = {"use_enum_values": True}


# Broadcast Targets (modular approach)
# These dataclasses define the target for broadcast operations.
# Using dataclasses instead of Pydantic for simpler, lighter-weight target objects.


@dataclass
class OrgTarget:
    """Broadcast to all connections in an organization.

    Use this target when you need to send a message to all users
    within a specific organization.

    Example:
        await manager.broadcast(msg, OrgTarget(org_id="org-123"))
    """

    org_id: str


@dataclass
class UserTarget:
    """Broadcast to all connections for a specific user.

    Use this target when you need to send a message to all of a
    user's active connections (they may have multiple tabs/devices).

    Example:
        await manager.broadcast(msg, UserTarget(user_id="user-456"))
    """

    user_id: str


@dataclass
class ChannelTarget:
    """Broadcast to all subscribers of a channel.

    Use this target for pub/sub style messaging where clients
    subscribe to specific channels (e.g., "test_run:123").

    Example:
        await manager.broadcast(msg, ChannelTarget(channel="test_run:123"))
    """

    channel: str


@dataclass
class ConnectionTarget:
    """Send to a specific connection.

    Use this target for direct responses to a specific WebSocket
    connection, such as chat responses or acknowledgments.

    Example:
        await manager.broadcast(msg, ConnectionTarget(connection_id="conn-abc"))
    """

    connection_id: str


# Union type for type-safe target handling
Target = Union[OrgTarget, UserTarget, ChannelTarget, ConnectionTarget]


# Helper functions for target serialization/deserialization (used by Redis pub/sub)


def serialize_target(target: Target) -> dict[str, Any]:
    """Serialize a target for Redis transmission.

    Args:
        target: The broadcast target to serialize.

    Returns:
        Dictionary with target type and relevant ID.
    """
    if isinstance(target, OrgTarget):
        return {"type": "org", "org_id": target.org_id}
    elif isinstance(target, UserTarget):
        return {"type": "user", "user_id": target.user_id}
    elif isinstance(target, ChannelTarget):
        return {"type": "channel", "channel": target.channel}
    elif isinstance(target, ConnectionTarget):
        return {"type": "connection", "connection_id": target.connection_id}
    else:
        raise ValueError(f"Unknown target type: {type(target)}")


def deserialize_target(data: dict[str, Any]) -> Target:
    """Deserialize a target from Redis transmission.

    Args:
        data: Dictionary with target type and relevant ID.

    Returns:
        The reconstructed target object.

    Raises:
        ValueError: If the target type is unknown.
    """
    target_type = data.get("type")
    if target_type == "org":
        return OrgTarget(org_id=data["org_id"])
    elif target_type == "user":
        return UserTarget(user_id=data["user_id"])
    elif target_type == "channel":
        return ChannelTarget(channel=data["channel"])
    elif target_type == "connection":
        return ConnectionTarget(connection_id=data["connection_id"])
    else:
        raise ValueError(f"Unknown target type: {target_type}")
