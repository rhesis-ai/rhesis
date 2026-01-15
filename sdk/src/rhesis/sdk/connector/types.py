"""Type definitions for the connector module."""

from enum import Enum


class ConnectionState(Enum):
    """WebSocket connection states."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    CLOSED = "closed"
    FAILED = "failed"  # Permanent failure, won't retry


class MessageType(str, Enum):
    """Message type constants for WebSocket communication."""

    # SDK -> Backend
    REGISTER = "register"
    TEST_RESULT = "test_result"
    PONG = "pong"

    # Backend -> SDK
    EXECUTE_TEST = "execute_test"
    PING = "ping"

    # Acknowledgements
    CONNECTED = "connected"
    REGISTERED = "registered"


class RetryConfig:
    """Configuration constants for connection retry behavior."""

    DEFAULT_MAX_RETRIES = 10
    DEFAULT_PING_INTERVAL = 30  # seconds
    DEFAULT_PING_TIMEOUT = 10  # seconds
    SLOW_RETRY_INTERVAL = 60  # seconds - wait between retry cycles
    REGISTRATION_DELAY = 0.5  # seconds - stabilization delay after connect

    # Exponential backoff params
    BACKOFF_MULTIPLIER = 1
    BACKOFF_MIN = 1  # seconds
    BACKOFF_MAX = 60  # seconds


class WebSocketCloseCode:
    """Standard WebSocket close codes."""

    NORMAL_CLOSURE = 1000
    GOING_AWAY = 1001
    PROTOCOL_ERROR = 1002
    UNSUPPORTED_DATA = 1003
    POLICY_VIOLATION = 1008
    MESSAGE_TOO_BIG = 1009

    # Permanent failure codes
    PERMANENT_CODES = {1000, 1001, 1002, 1003, 1007, 1008, 1009, 1010, 1011}


class ErrorClassification:
    """Error classification rules for retry logic."""

    # HTTP status code -> (is_retryable, error_template)
    HTTP_STATUS_RULES = {
        400: (
            False,
            (
                "Bad request: The connection request is malformed.\n"
                "Please check your SDK configuration."
            ),
        ),
        401: (
            False,
            (
                "Authentication failed: Your API key is invalid or expired.\n"
                "Please verify your RHESIS_API_KEY environment variable."
            ),
        ),
        403: (
            False,
            (
                "Authorization failed: Invalid API key or project ID.\n"
                "Please check:\n"
                "  - RHESIS_API_KEY is correct\n"
                "  - RHESIS_PROJECT_ID is valid and belongs to your organization"
            ),
        ),
        429: (True, "Rate limit exceeded. Retrying with backoff..."),
    }

    # WebSocket close codes -> (is_retryable, error_template)
    WS_CLOSE_CODE_RULES = {
        1002: (False, "Protocol error"),
        1003: (False, "Unsupported data format"),
        1008: (False, "Connection rejected by server due to policy violation"),
    }

    # Keywords in error messages that indicate transient failures
    TRANSIENT_KEYWORDS = [
        "connection refused",
        "timeout",
        "network",
        "unreachable",
        "connection reset",
    ]


class Environment:
    """Valid environment names."""

    PRODUCTION = "production"
    STAGING = "staging"
    DEVELOPMENT = "development"
    LOCAL = "local"

    ALL = [PRODUCTION, STAGING, DEVELOPMENT, LOCAL]
