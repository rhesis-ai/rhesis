"""WebSocket connection management utilities."""

import asyncio
import json
import logging
import re
from typing import Any, Callable, Dict, Optional

import websockets
from tenacity import (
    AsyncRetrying,
    RetryError,
    stop_after_attempt,
    wait_exponential,
)
from websockets.asyncio.client import ClientConnection

from rhesis.sdk.connector.types import ConnectionState

logger = logging.getLogger(__name__)


class PermanentConnectionError(Exception):
    """Exception for permanent connection failures that should not be retried."""

    pass


class TransientConnectionError(Exception):
    """Exception for transient connection failures that should be retried."""

    pass


def classify_websocket_error(exception: Exception) -> tuple[bool, str]:
    """
    Classify WebSocket errors as retryable or permanent.

    Args:
        exception: The exception to classify

    Returns:
        Tuple of (is_retryable, error_message)
    """
    error_str = str(exception)

    # Check for WebSocket close code and reason (e.g., code 1008 = Policy Violation)
    # websockets library provides ConnectionClosed with code and reason attributes
    if hasattr(exception, "rcvd") and exception.rcvd:
        close_code = exception.rcvd.code
        close_reason = exception.rcvd.reason

        # Code 1008: Policy Violation (used for validation errors like invalid project_id)
        if close_code == 1008:
            message = (
                f"Connection rejected: {close_reason}"
                if close_reason
                else "Connection rejected by server due to policy violation"
            )
            return False, message

        # Code 1002: Protocol Error
        if close_code == 1002:
            message = (
                f"Protocol error: {close_reason}" if close_reason else "WebSocket protocol error"
            )
            return False, message

        # Code 1003: Unsupported Data
        if close_code == 1003:
            message = (
                f"Unsupported data: {close_reason}" if close_reason else "Unsupported data format"
            )
            return False, message

        # Use close reason if available for other codes
        if close_reason:
            # Codes 1000-1003, 1007-1011 are permanent failures
            if close_code in [1000, 1001, 1002, 1003, 1007, 1008, 1009, 1010, 1011]:
                return False, f"Connection closed (code {close_code}): {close_reason}"

    # Extract HTTP status code if present
    http_status_match = re.search(r"HTTP (\d{3})", error_str)
    if http_status_match:
        status_code = int(http_status_match.group(1))

        # Authentication/Authorization errors (permanent)
        if status_code in [401, 403]:
            if status_code == 401:
                message = (
                    "Authentication failed: Your API key is invalid or expired.\n"
                    "Please verify your RHESIS_API_KEY environment variable."
                )
            else:  # 403
                message = (
                    "Authorization failed: Invalid API key, project ID, "
                    "or user not associated with organization.\n"
                    "Please check:\n"
                    "  - RHESIS_API_KEY is correct\n"
                    "  - RHESIS_PROJECT_ID is set\n"
                    "  - Your user account is linked to an organization"
                )
            return False, message

        # Bad request (permanent)
        if status_code == 400:
            message = (
                "Bad request: The connection request is malformed.\n"
                "Please check your SDK configuration."
            )
            return False, message

        # Rate limiting (transient)
        if status_code == 429:
            message = "Rate limit exceeded. Retrying with backoff..."
            return True, message

        # Server errors (transient)
        if status_code >= 500:
            message = f"Server error (HTTP {status_code}). Retrying..."
            return True, message

    # Connection refused, timeouts, network errors (transient)
    if any(
        keyword in error_str.lower()
        for keyword in [
            "connection refused",
            "timeout",
            "network",
            "unreachable",
            "connection reset",
        ]
    ):
        message = f"Network error: {error_str}. Retrying..."
        return True, message

    # Default: treat as transient
    message = f"Connection error: {error_str}. Retrying..."
    return True, message


class WebSocketConnection:
    """Manages WebSocket connection with auto-reconnect."""

    def __init__(
        self,
        url: str,
        headers: Dict[str, str],
        on_message: Callable[[Dict[str, Any]], None],
        on_connect: Optional[Callable[[], None]] = None,
        on_connection_failed: Optional[Callable[[str], None]] = None,
        ping_interval: int = 30,
        ping_timeout: int = 10,
        max_retries: int = 10,
    ):
        """
        Initialize WebSocket connection manager.

        Args:
            url: WebSocket URL to connect to
            headers: Headers to send with connection request
            on_message: Callback for handling incoming messages
            on_connect: Optional callback called when connection is established (or re-established)
            on_connection_failed: Optional callback called when connection permanently fails
            ping_interval: Interval between ping messages (seconds)
            ping_timeout: Timeout for pong response (seconds)
            max_retries: Maximum number of connection retry attempts (default: 10)
        """
        self.url = url
        self.headers = headers
        self.on_message = on_message
        self.on_connect = on_connect
        self.on_connection_failed = on_connection_failed
        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout
        self.max_retries = max_retries

        self.state = ConnectionState.DISCONNECTED
        self.websocket: Optional[ClientConnection] = None
        self._connection_task: Optional[asyncio.Task] = None
        self._should_reconnect = True
        self._failure_reason: Optional[str] = None

    def _log_state_change(self, new_state: ConnectionState, context: str = "") -> None:
        """
        Log connection state changes with context.

        Args:
            new_state: The new connection state
            context: Additional context about the state change
        """
        old_state = self.state
        if old_state != new_state:
            context_msg = f" ({context})" if context else ""
            logger.info(
                f"Connection state: {old_state.value} -> {new_state.value}{context_msg} "
                f"[url={self.url}, ping_interval={self.ping_interval}s, "
                f"ping_timeout={self.ping_timeout}s]"
            )
        self.state = new_state

    async def connect(self) -> None:
        """Establish WebSocket connection."""
        if self.state in (ConnectionState.CONNECTED, ConnectionState.CONNECTING):
            logger.warning("Connection already active")
            return

        self._log_state_change(ConnectionState.CONNECTING, "initiating connection")
        self._should_reconnect = True

        # Start connection task
        self._connection_task = asyncio.create_task(self._maintain_connection())

    async def disconnect(self) -> None:
        """Close WebSocket connection gracefully."""
        self._should_reconnect = False
        self._log_state_change(ConnectionState.CLOSED, "user requested disconnect")

        if self.websocket:
            try:
                await self.websocket.close()
            except Exception:
                pass  # Ignore errors during close
            self.websocket = None

        if self._connection_task:
            self._connection_task.cancel()
            try:
                await self._connection_task
            except (asyncio.CancelledError, Exception):
                # Ignore all exceptions from connection task
                pass
            self._connection_task = None

    async def send(self, message: Dict[str, Any]) -> None:
        """
        Send a message through the WebSocket.

        Args:
            message: Message dictionary to send
        """
        if not self.websocket or self.state != ConnectionState.CONNECTED:
            logger.error(f"Cannot send message: not connected (state={self.state.value})")
            raise RuntimeError("WebSocket not connected")

        try:
            message_type = message.get("type", "unknown")
            await self.websocket.send(json.dumps(message))
            logger.debug(f"Message sent successfully: type={message_type}")
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            raise

    async def _maintain_connection(self) -> None:
        """Maintain persistent connection with auto-reconnect using tenacity."""
        attempt_number = 0
        logger.info("Starting connection maintenance loop")

        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self.max_retries),
                wait=wait_exponential(multiplier=1, min=1, max=60),
                reraise=False,  # Don't reraise - we want to catch RetryError
            ):
                with attempt:
                    attempt_number = attempt.retry_state.attempt_number
                    if attempt_number > 1:
                        self._log_state_change(
                            ConnectionState.RECONNECTING,
                            f"attempt {attempt_number}/{self.max_retries}",
                        )

                    try:
                        await self._attempt_single_connection()
                        # If we get here, connection was successful and closed gracefully
                        if attempt_number > 1:
                            logger.info(
                                f"Successfully reconnected after {attempt_number} attempt(s)"
                            )
                        logger.info("Connection closed gracefully")
                        break
                    except Exception as e:
                        # Classify the error
                        is_retryable, error_message = classify_websocket_error(e)

                        if not is_retryable:
                            # Permanent error - don't retry
                            logger.error(f"Permanent connection failure:\n{error_message}")
                            logger.error("Not retrying authentication/authorization failures.")
                            self._log_state_change(ConnectionState.FAILED, "permanent error")
                            self._failure_reason = error_message

                            # Call failure callback if provided
                            if self.on_connection_failed:
                                try:
                                    self.on_connection_failed(error_message)
                                except Exception as callback_error:
                                    logger.error(f"Error in failure callback: {callback_error}")

                            # Break out without retrying
                            return

                        # Transient error - will retry
                        if attempt_number == 1:
                            # First failure - log the full message
                            logger.error(error_message)
                        else:
                            # Subsequent failures - shorter message
                            logger.warning(
                                f"Attempt {attempt_number}/{self.max_retries} failed. Retrying..."
                            )

                        # Re-raise to trigger retry
                        raise TransientConnectionError(error_message) from e

        except RetryError as e:
            # Max retries exceeded
            self._log_state_change(
                ConnectionState.FAILED, f"max retries ({self.max_retries}) exceeded"
            )
            last_error = (
                e.last_attempt.exception()
                if e.last_attempt and e.last_attempt.exception()
                else None
            )

            if last_error:
                _, error_message = classify_websocket_error(last_error)
            else:
                error_message = "Connection failed after maximum retries"

            self._failure_reason = error_message
            logger.error(
                f"Connection failed after {self.max_retries} attempts.\nLast error: {error_message}"
            )

            # Call failure callback if provided
            if self.on_connection_failed:
                try:
                    self.on_connection_failed(error_message)
                except Exception as callback_error:
                    logger.error(f"Error in failure callback: {callback_error}")

        finally:
            if self.state not in (ConnectionState.FAILED, ConnectionState.CLOSED):
                self._log_state_change(
                    ConnectionState.DISCONNECTED, "connection closed unexpectedly"
                )
            logger.info("Connection maintenance loop ended")

    async def _attempt_single_connection(self) -> None:
        """Attempt a single WebSocket connection."""
        logger.debug(f"Attempting WebSocket connection to {self.url}")
        async with websockets.connect(
            self.url,
            additional_headers=self.headers,
            ping_interval=self.ping_interval,
            ping_timeout=self.ping_timeout,
        ) as websocket:
            self.websocket = websocket
            self._log_state_change(ConnectionState.CONNECTED, "websocket established")

            # Trigger on_connect callback (for registration)
            if self.on_connect:
                asyncio.create_task(self.on_connect())

            # Listen for messages (blocks until connection closes)
            logger.debug("Starting message listener loop")
            await self._listen_for_messages(websocket)
            logger.debug("Message listener loop ended")

    async def _listen_for_messages(self, websocket: ClientConnection) -> None:
        """Listen for incoming messages."""
        async for message in websocket:
            try:
                data = json.loads(message)
                await self.on_message(data)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode message: {e}")
            except Exception as e:
                logger.error(f"Error handling message: {e}")
