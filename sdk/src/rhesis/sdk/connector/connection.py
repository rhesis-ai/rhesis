"""WebSocket connection management utilities."""

import asyncio
import json
import logging
from typing import Any, Callable, Dict, Optional

import websockets
from websockets.asyncio.client import ClientConnection

from rhesis.sdk.connector.types import ConnectionState

logger = logging.getLogger(__name__)


class WebSocketConnection:
    """Manages WebSocket connection with auto-reconnect."""

    def __init__(
        self,
        url: str,
        headers: Dict[str, str],
        on_message: Callable[[Dict[str, Any]], None],
        on_connect: Optional[Callable[[], None]] = None,
        ping_interval: int = 30,
        ping_timeout: int = 10,
    ):
        """
        Initialize WebSocket connection manager.

        Args:
            url: WebSocket URL to connect to
            headers: Headers to send with connection request
            on_message: Callback for handling incoming messages
            on_connect: Optional callback called when connection is established (or re-established)
            ping_interval: Interval between ping messages (seconds)
            ping_timeout: Timeout for pong response (seconds)
        """
        self.url = url
        self.headers = headers
        self.on_message = on_message
        self.on_connect = on_connect
        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout

        self.state = ConnectionState.DISCONNECTED
        self.websocket: Optional[ClientConnection] = None
        self._connection_task: Optional[asyncio.Task] = None
        self._should_reconnect = True

    async def connect(self) -> None:
        """Establish WebSocket connection."""
        if self.state in (ConnectionState.CONNECTED, ConnectionState.CONNECTING):
            logger.warning("Connection already active")
            return

        self.state = ConnectionState.CONNECTING
        self._should_reconnect = True

        # Start connection task
        self._connection_task = asyncio.create_task(self._maintain_connection())

    async def disconnect(self) -> None:
        """Close WebSocket connection gracefully."""
        self._should_reconnect = False
        self.state = ConnectionState.CLOSED

        if self.websocket:
            await self.websocket.close()
            self.websocket = None

        if self._connection_task:
            self._connection_task.cancel()
            try:
                await self._connection_task
            except asyncio.CancelledError:
                pass
            self._connection_task = None

    async def send(self, message: Dict[str, Any]) -> None:
        """
        Send a message through the WebSocket.

        Args:
            message: Message dictionary to send
        """
        if not self.websocket or self.state != ConnectionState.CONNECTED:
            logger.error("Cannot send message: not connected")
            raise RuntimeError("WebSocket not connected")

        try:
            await self.websocket.send(json.dumps(message))
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            raise

    async def _maintain_connection(self) -> None:
        """Maintain persistent connection with auto-reconnect."""
        retry_delay = 1  # Start with 1 second
        max_delay = 60  # Max 60 seconds between retries

        while self._should_reconnect:
            try:
                async with websockets.connect(
                    self.url,
                    additional_headers=self.headers,
                    ping_interval=self.ping_interval,
                    ping_timeout=self.ping_timeout,
                ) as websocket:
                    self.websocket = websocket
                    self.state = ConnectionState.CONNECTED
                    logger.info(f"WebSocket connected to {self.url}")

                    # Reset retry delay on successful connection
                    retry_delay = 1

                    # Trigger on_connect callback (for registration)
                    if self.on_connect:
                        asyncio.create_task(self.on_connect())

                    # Listen for messages
                    await self._listen_for_messages(websocket)

            except websockets.exceptions.WebSocketException as e:
                logger.error(f"WebSocket error: {e}")
                self.state = ConnectionState.RECONNECTING
                self.websocket = None

            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                self.state = ConnectionState.RECONNECTING
                self.websocket = None

            # Reconnect with exponential backoff
            if self._should_reconnect:
                logger.info(f"Reconnecting in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_delay)

        self.state = ConnectionState.DISCONNECTED
        logger.info("WebSocket connection closed")

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
