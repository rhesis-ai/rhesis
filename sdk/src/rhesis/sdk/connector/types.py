"""Type definitions for the connector module."""

from enum import Enum


class ConnectionState(Enum):
    """WebSocket connection states."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    CLOSED = "closed"


class MessageType:
    """Message type constants."""

    # SDK -> Backend
    REGISTER = "register"
    TEST_RESULT = "test_result"
    PONG = "pong"

    # Backend -> SDK
    EXECUTE_TEST = "execute_test"
    PING = "ping"
