"""A long-lived connector that drops reconnects at once, not after the accumulated backoff."""

import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest
from websockets.exceptions import ConnectionClosedError

from rhesis.sdk.connector.connection import WebSocketConnection
from rhesis.sdk.connector.types import ConnectionState, RetryConfig


def _connection():
    return WebSocketConnection(
        url="ws://localhost/connector/ws", headers={}, on_message=AsyncMock()
    )


async def _run_until(connection, attempts, calls, seconds):
    async def attempt():
        calls.append(time.monotonic())
        if len(calls) >= attempts:
            connection._should_reconnect = False
            return
        await asyncio.sleep(0)
        raise ConnectionError("connection reset")

    with patch.object(connection, "_attempt_single_connection", side_effect=attempt):
        try:
            await asyncio.wait_for(connection._maintain_connection(), timeout=seconds)
        except asyncio.TimeoutError:
            pass


@pytest.mark.asyncio
async def test_drop_after_a_stable_connection_reconnects_at_once():
    """Item 9: each drop used to add to the backoff (1, 2, 4 ... 32s, then 60s)."""
    connection = _connection()
    calls = []
    original = connection._dropped_after_stable_connection

    def stable():
        connection._connected_at = time.monotonic() - RetryConfig.STABLE_CONNECTION_SECONDS
        return original()

    with patch.object(connection, "_dropped_after_stable_connection", side_effect=stable):
        await _run_until(connection, attempts=5, calls=calls, seconds=1.0)

    assert len(calls) == 5


@pytest.mark.asyncio
async def test_connect_then_immediate_drop_still_backs_off():
    """A server that accepts and drops at once must not get a hot reconnect loop."""
    connection = _connection()
    calls = []

    def just_connected():
        connection._connected_at = time.monotonic()
        return False

    with patch.object(connection, "_dropped_after_stable_connection", side_effect=just_connected):
        await _run_until(connection, attempts=5, calls=calls, seconds=0.5)

    assert len(calls) == 1  # the first retry waits BACKOFF_MIN (1s)


def test_only_a_connection_that_stayed_up_counts_as_stable():
    connection = _connection()
    assert not connection._dropped_after_stable_connection()
    connection._connected_at = time.monotonic()
    assert not connection._dropped_after_stable_connection()
    connection._connected_at = time.monotonic() - RetryConfig.STABLE_CONNECTION_SECONDS
    assert connection._dropped_after_stable_connection()
    assert connection._connected_at is None


class _DyingSocket:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise ConnectionClosedError(None, None)


@pytest.mark.asyncio
async def test_dead_socket_is_not_left_marked_connected():
    """Sends during the backoff go straight to the outbox instead of a dead socket."""
    connection = _connection()
    with patch("rhesis.sdk.connector.connection.websockets.connect", return_value=_DyingSocket()):
        with pytest.raises(ConnectionClosedError):
            await connection._attempt_single_connection()

    assert connection.websocket is None
    assert connection.state == ConnectionState.RECONNECTING
    with pytest.raises(RuntimeError, match="not connected"):
        await connection.send({"type": "test_result", "test_run_id": "run-1"})
