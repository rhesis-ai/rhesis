"""Type definitions for the connector module."""

import os
from enum import Enum
from typing import TYPE_CHECKING, Optional

from pydantic import BaseModel

if TYPE_CHECKING:
    import aiohttp


class FileReference(BaseModel):
    """A reference to a file stored in object storage.

    Passed through the execution pipeline instead of raw bytes so that
    the full file content never resides in Python memory except at the
    moment an endpoint actually needs it (on-demand materialisation).
    """

    id: str
    filename: str
    content_type: str
    size_bytes: int
    content_hash: str
    storage_path: Optional[str] = None
    signed_url: Optional[str] = None
    extracted_text: Optional[str] = None

    def read_bytes(self) -> bytes:
        """Fetch the file bytes via the signed URL (blocking I/O).

        .. warning::

           This call blocks on the network using stdlib ``urllib``. Do
           **not** call from an asyncio event loop or a Celery task that
           interleaves with other I/O — use :meth:`aread_bytes` instead.
           This sync variant is intended for synchronous SDK user code
           (scripts, notebooks, sync metric implementations).

        Raises:
            RuntimeError: when ``signed_url`` is not populated. The
                backend must set it before passing ``FileReference``
                instances to SDK user functions that need raw bytes.
        """
        if not self.signed_url:
            raise RuntimeError(
                f"No signed_url available for FileReference id={self.id}. "
                "The backend must populate signed_url before passing FileReferences "
                "to SDK user functions that need raw bytes."
            )
        import urllib.request

        with urllib.request.urlopen(self.signed_url) as resp:
            return resp.read()

    async def aread_bytes(self, session: Optional["aiohttp.ClientSession"] = None) -> bytes:
        """Async sibling of :meth:`read_bytes` — fetches bytes without blocking.

        Uses ``aiohttp`` (already an SDK runtime dependency).  Pass an
        existing ``aiohttp.ClientSession`` for connection reuse when
        invoking from a long-lived async context; otherwise a one-shot
        session is created and closed for this call.

        Raises:
            RuntimeError: when ``signed_url`` is not populated.
        """
        if not self.signed_url:
            raise RuntimeError(
                f"No signed_url available for FileReference id={self.id}. "
                "The backend must populate signed_url before passing FileReferences "
                "to SDK user functions that need raw bytes."
            )
        import aiohttp

        async def _fetch(s: aiohttp.ClientSession) -> bytes:
            async with s.get(self.signed_url) as resp:
                resp.raise_for_status()
                return await resp.read()

        if session is not None:
            return await _fetch(session)
        async with aiohttp.ClientSession() as owned_session:
            return await _fetch(owned_session)


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
    METRIC_RESULT = "metric_result"
    PONG = "pong"

    # Backend -> SDK
    EXECUTE_TEST = "execute_test"
    EXECUTE_METRIC = "execute_metric"
    PING = "ping"

    # Acknowledgements
    CONNECTED = "connected"
    REGISTERED = "registered"


class RetryConfig:
    """Configuration constants for connection retry behavior."""

    DEFAULT_MAX_RETRIES = 10
    # Ping interval and timeout are configurable for long-running LLM operations
    # Defaults increased to accommodate typical LLM response times
    DEFAULT_PING_INTERVAL = int(os.environ.get("RHESIS_PING_INTERVAL", "60"))  # seconds
    DEFAULT_PING_TIMEOUT = int(os.environ.get("RHESIS_PING_TIMEOUT", "30"))  # seconds
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
