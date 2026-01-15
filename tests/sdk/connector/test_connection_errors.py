"""Tests for WebSocket connection error handling and retry logic."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import websockets

from rhesis.sdk.connector.connection import (
    WebSocketConnection,
    classify_websocket_error,
)
from rhesis.sdk.connector.types import ConnectionState


async def wait_for_state(
    connection: WebSocketConnection, expected_state: ConnectionState, timeout: float = 5.0
) -> bool:
    """
    Wait for connection to reach expected state.

    Args:
        connection: WebSocket connection instance
        expected_state: Expected connection state
        timeout: Maximum time to wait in seconds

    Returns:
        True if state reached, False if timeout
    """
    start_time = asyncio.get_event_loop().time()
    while (asyncio.get_event_loop().time() - start_time) < timeout:
        if connection.state == expected_state:
            return True
        await asyncio.sleep(0.05)  # Poll every 50ms
    return False


async def wait_for_task_completion(task: asyncio.Task, timeout: float = 10.0) -> None:
    """
    Wait for async task to complete, handling all exceptions.

    Args:
        task: Async task to wait for
        timeout: Maximum time to wait in seconds
    """
    try:
        await asyncio.wait_for(task, timeout=timeout)
    except (asyncio.TimeoutError, asyncio.CancelledError, Exception):
        # Expected - task may fail or be cancelled
        pass


class TestErrorClassification:
    """Test error classification logic."""

    def test_classify_http_401_error(self):
        """Test that HTTP 401 is classified as permanent."""
        error = Exception("server rejected WebSocket connection: HTTP 401")
        is_retryable, message = classify_websocket_error(error)

        assert not is_retryable
        assert "Authentication failed" in message
        assert "RHESIS_API_KEY" in message

    def test_classify_http_403_error(self):
        """Test that HTTP 403 is classified as permanent."""
        error = Exception("server rejected WebSocket connection: HTTP 403")
        is_retryable, message = classify_websocket_error(error)

        assert not is_retryable
        assert "Authorization failed" in message
        assert "RHESIS_API_KEY" in message
        assert "RHESIS_PROJECT_ID" in message
        assert "organization" in message

    def test_classify_http_400_error(self):
        """Test that HTTP 400 is classified as permanent."""
        error = Exception("Bad request: HTTP 400")
        is_retryable, message = classify_websocket_error(error)

        assert not is_retryable
        assert "Bad request" in message

    def test_classify_http_429_error(self):
        """Test that HTTP 429 is classified as retryable."""
        error = Exception("Rate limited: HTTP 429")
        is_retryable, message = classify_websocket_error(error)

        assert is_retryable
        assert "Rate limit" in message

    def test_classify_http_500_error(self):
        """Test that HTTP 500 is classified as retryable."""
        error = Exception("Internal server error: HTTP 500")
        is_retryable, message = classify_websocket_error(error)

        assert is_retryable
        assert "Server error" in message

    def test_classify_http_503_error(self):
        """Test that HTTP 503 is classified as retryable."""
        error = Exception("Service unavailable: HTTP 503")
        is_retryable, message = classify_websocket_error(error)

        assert is_retryable
        assert "Server error" in message

    def test_classify_connection_refused_error(self):
        """Test that connection refused is classified as retryable."""
        error = Exception("Connection refused")
        is_retryable, message = classify_websocket_error(error)

        assert is_retryable
        assert "Network error" in message

    def test_classify_timeout_error(self):
        """Test that timeout is classified as retryable."""
        error = Exception("Connection timeout")
        is_retryable, message = classify_websocket_error(error)

        assert is_retryable
        assert "Network error" in message

    def test_classify_network_unreachable_error(self):
        """Test that network unreachable is classified as retryable."""
        error = Exception("Network is unreachable")
        is_retryable, message = classify_websocket_error(error)

        assert is_retryable
        assert "Network error" in message

    def test_classify_generic_error(self):
        """Test that generic errors are classified as retryable by default."""
        error = Exception("Something went wrong")
        is_retryable, message = classify_websocket_error(error)

        assert is_retryable
        assert "Connection error" in message


class TestWebSocketConnectionRetry:
    """Test WebSocket connection retry logic."""

    @pytest.fixture
    def mock_on_message(self):
        """Create mock on_message callback."""
        return AsyncMock()

    @pytest.fixture
    def mock_on_connect(self):
        """Create mock on_connect callback."""
        return AsyncMock()

    @pytest.fixture
    def mock_on_connection_failed(self):
        """Create mock on_connection_failed callback."""
        return MagicMock()

    @pytest.fixture
    def connection(self, mock_on_message, mock_on_connect, mock_on_connection_failed):
        """Create WebSocket connection instance."""
        return WebSocketConnection(
            url="ws://test.example.com/ws",
            headers={"Authorization": "Bearer test-token"},
            on_message=mock_on_message,
            on_connect=mock_on_connect,
            on_connection_failed=mock_on_connection_failed,
            max_retries=3,  # Lower for faster tests
        )

    @pytest.mark.asyncio
    async def test_permanent_error_no_retry(self, connection, mock_on_connection_failed):
        """Test that permanent errors (401/403) don't trigger retries."""
        # Mock websockets.connect to raise HTTP 403
        with patch("rhesis.sdk.connector.connection.websockets.connect") as mock_connect:
            mock_connect.side_effect = websockets.exceptions.InvalidStatusCode(
                403, {"status": "403"}
            )

            # Start connection
            await connection.connect()

            # Give it a moment to process
            await asyncio.sleep(0.2)

            # Should only try once (no retries for permanent errors)
            assert mock_connect.call_count == 1

            # Should be in FAILED state
            assert connection.state == ConnectionState.FAILED

            # Should have called failure callback
            assert mock_on_connection_failed.called
            call_args = mock_on_connection_failed.call_args[0][0]
            assert "Authorization failed" in call_args

            # Cleanup
            await connection.disconnect()

    @pytest.mark.asyncio
    async def test_transient_error_retries(self):
        """Test that transient errors (500) trigger retries and enter slow retry mode."""
        callback_called = False

        def on_failed(message):
            nonlocal callback_called
            callback_called = True

        connection = WebSocketConnection(
            url="ws://test.example.com/ws",
            headers={"Authorization": "Bearer test-token"},
            on_message=AsyncMock(),
            on_connection_failed=on_failed,
            max_retries=3,
        )

        # Mock websockets.connect to raise HTTP 500 multiple times
        with patch("rhesis.sdk.connector.connection.websockets.connect") as mock_connect:
            mock_connect.side_effect = websockets.exceptions.InvalidStatusCode(
                500, {"status": "500"}
            )

            # Start connection (runs in background task)
            await connection.connect()

            # Wait for initial fast retries to complete
            # With exponential backoff (1s, 2s, 4s), we need to wait ~7 seconds for 3 retries
            # But we can check incrementally
            max_wait = 10.0
            start_time = asyncio.get_event_loop().time()

            while mock_connect.call_count < 3:
                if (asyncio.get_event_loop().time() - start_time) > max_wait:
                    break
                await asyncio.sleep(0.1)

            # Should have retried max_retries times (3 in this case)
            assert mock_connect.call_count == 3, (
                f"Expected 3 retries, got {mock_connect.call_count}"
            )

            # Connection should still be active (in RECONNECTING state for slow retry mode)
            # Not in FAILED state because transient errors don't cause permanent failure
            assert connection.state == ConnectionState.RECONNECTING, (
                f"Expected RECONNECTING state for slow retry, got {connection.state}"
            )

            # Failure callback should NOT be called for transient errors
            # (only called for permanent failures like 401/403)
            assert not callback_called, "Failure callback should not be called for transient errors"

            # Cleanup - stop the retry loop
            await connection.disconnect()

    @pytest.mark.asyncio
    async def test_successful_connection_after_retry(
        self, connection, mock_on_connect, mock_on_connection_failed
    ):
        """Test successful connection after transient failures."""
        call_count = 0
        close_event = asyncio.Event()

        class MockWebSocket:
            """Mock WebSocket that behaves like an async context manager."""

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None

            def __aiter__(self):
                return self

            async def __anext__(self):
                # Wait for close signal then stop iteration
                await close_event.wait()
                raise StopAsyncIteration

            async def close(self):
                """Mock close method."""
                pass

        def mock_connect_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            if call_count < 3:
                # First 2 attempts fail with transient error
                raise websockets.exceptions.InvalidStatusCode(500, {"status": "500"})
            elif call_count == 3:
                # Third attempt succeeds
                return MockWebSocket()
            else:
                # After first successful connection closes, prevent infinite reconnection
                # by raising an error that will be handled by the retry loop
                raise websockets.exceptions.InvalidStatusCode(500, {"status": "500"})

        with patch(
            "rhesis.sdk.connector.connection.websockets.connect",
            side_effect=mock_connect_side_effect,
        ):
            # Start connection
            await connection.connect()

            # Wait for connection to reach CONNECTED state
            state_reached = await wait_for_state(connection, ConnectionState.CONNECTED, timeout=5.0)
            assert state_reached, f"Expected CONNECTED state, got {connection.state}"

            # Should have tried 3 times to reach first successful connection
            assert call_count == 3

            # Should NOT have called failure callback (succeeded eventually)
            assert not mock_on_connection_failed.called

            # Should have called on_connect callback
            assert mock_on_connect.called

            # Disconnect before closing websocket to prevent reconnection loop
            await connection.disconnect()

            # Now signal close to clean up the websocket
            close_event.set()
            await asyncio.sleep(0.05)  # Brief wait for iterator to complete

    @pytest.mark.asyncio
    async def test_max_retries_configuration(self, mock_on_message):
        """Test that max_retries configuration is respected for fast retries."""
        max_retries = 5
        connection = WebSocketConnection(
            url="ws://test.example.com/ws",
            headers={"Authorization": "Bearer test-token"},
            on_message=mock_on_message,
            max_retries=max_retries,
        )

        with patch("rhesis.sdk.connector.connection.websockets.connect") as mock_connect:
            mock_connect.side_effect = websockets.exceptions.InvalidStatusCode(
                500, {"status": "500"}
            )

            # Start connection
            await connection.connect()

            # Wait for fast retries to complete
            # With exponential backoff (1s, 2s, 4s, 8s, 16s), need to wait ~31 seconds for 5 retries
            # But we can check incrementally
            max_wait = 35.0
            start_time = asyncio.get_event_loop().time()

            while mock_connect.call_count < max_retries:
                if (asyncio.get_event_loop().time() - start_time) > max_wait:
                    break
                await asyncio.sleep(0.1)

            # Should retry exactly max_retries times in the fast retry phase
            assert mock_connect.call_count == max_retries, (
                f"Expected {max_retries} fast retries, got {mock_connect.call_count}"
            )

            # Should be in RECONNECTING state (entering slow retry mode)
            assert connection.state == ConnectionState.RECONNECTING, (
                f"Expected RECONNECTING for slow retry, got {connection.state}"
            )

            # Cleanup
            await connection.disconnect()

    @pytest.mark.asyncio
    async def test_state_transitions_on_retry(self, connection):
        """Test that connection state transitions correctly during retries."""
        with patch("rhesis.sdk.connector.connection.websockets.connect") as mock_connect:
            # Make it fail with transient error
            mock_connect.side_effect = websockets.exceptions.InvalidStatusCode(
                500, {"status": "500"}
            )

            # Initial state
            assert connection.state == ConnectionState.DISCONNECTED

            # Start connection (runs in background)
            await connection.connect()

            # Wait for first failure - should transition from CONNECTING
            # Poll until we're no longer in CONNECTING state
            start_time = asyncio.get_event_loop().time()
            while connection.state == ConnectionState.CONNECTING:
                if (asyncio.get_event_loop().time() - start_time) > 2.0:
                    break
                await asyncio.sleep(0.05)

            # Should have transitioned to RECONNECTING or FAILED
            assert connection.state in [
                ConnectionState.RECONNECTING,
                ConnectionState.FAILED,
            ], f"Expected RECONNECTING or FAILED, got {connection.state}"

            # Cleanup
            await connection.disconnect()

    @pytest.mark.asyncio
    async def test_failure_reason_stored(self, connection):
        """Test that failure reason is stored on permanent failure."""
        with patch("rhesis.sdk.connector.connection.websockets.connect") as mock_connect:
            mock_connect.side_effect = websockets.exceptions.InvalidStatusCode(
                403, {"status": "403"}
            )

            # Start connection
            await connection.connect()
            await asyncio.sleep(0.2)

            # Should have stored failure reason
            assert connection._failure_reason is not None
            assert "Authorization failed" in connection._failure_reason

            # Cleanup
            await connection.disconnect()
