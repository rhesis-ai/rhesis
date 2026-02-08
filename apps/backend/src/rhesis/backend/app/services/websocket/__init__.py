"""WebSocket service package.

This package provides the WebSocket infrastructure for real-time communication
between the backend and frontend.

Components:
- ChannelAuthorizer: Validates user authorization for channel subscriptions
- ConnectionRegistry: Tracks WebSocket connections with multi-index lookups
- WebSocketManager: Manages connections, subscriptions, and broadcasting
- EventPublisher: Publishes events via Redis for cross-instance broadcasting
- RedisSubscriber: Listens for Redis events and forwards to WebSocketManager
"""

from rhesis.backend.app.services.websocket.authorization import (
    ChannelAuthorizer,
    get_channel_authorizer,
)
from rhesis.backend.app.services.websocket.manager import WebSocketManager, ws_manager
from rhesis.backend.app.services.websocket.publisher import (
    EventPublisher,
    get_publisher,
    publish_event,
    publish_event_async,
)
from rhesis.backend.app.services.websocket.rate_limiter import (
    SlidingWindowRateLimiter,
    get_rate_limiter,
)
from rhesis.backend.app.services.websocket.redis_pubsub import (
    RedisSubscriber,
    get_subscriber,
    start_redis_subscriber,
    stop_redis_subscriber,
)
from rhesis.backend.app.services.websocket.registry import ConnectionRegistry
from rhesis.backend.app.services.websocket.token_service import (
    WebSocketTokenService,
    get_ws_token_service,
)

__all__ = [
    "ChannelAuthorizer",
    "ConnectionRegistry",
    "EventPublisher",
    "RedisSubscriber",
    "SlidingWindowRateLimiter",
    "WebSocketManager",
    "WebSocketTokenService",
    "get_channel_authorizer",
    "get_publisher",
    "get_rate_limiter",
    "get_subscriber",
    "get_ws_token_service",
    "publish_event",
    "publish_event_async",
    "start_redis_subscriber",
    "stop_redis_subscriber",
    "ws_manager",
]
