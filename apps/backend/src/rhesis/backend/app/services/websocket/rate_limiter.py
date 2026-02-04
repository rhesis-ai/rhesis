"""Rate limiting for WebSocket message handling.

This module provides protection against denial of service attacks
by limiting the number of messages a connection can send within
a time window.
"""

import logging
import time
from collections import defaultdict
from threading import Lock
from typing import Optional

logger = logging.getLogger(__name__)


class SlidingWindowRateLimiter:
    """Per-connection rate limiter using sliding window algorithm.

    This limiter enforces a maximum number of requests per connection
    within a sliding time window. Each connection is tracked independently.

    Default: 100 messages per 60 seconds per connection.

    Example:
        limiter = SlidingWindowRateLimiter(max_requests=100, window_seconds=60)

        if limiter.is_allowed(conn_id):
            # Process message
        else:
            # Reject message - rate limit exceeded
    """

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        """Initialize the rate limiter.

        Args:
            max_requests: Maximum number of requests allowed per window.
            window_seconds: Size of the sliding window in seconds.
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def is_allowed(self, conn_id: str) -> bool:
        """Check if a request is allowed under the rate limit.

        This method is thread-safe and can be called from multiple
        async tasks concurrently.

        Args:
            conn_id: The connection ID making the request.

        Returns:
            True if the request is allowed, False if rate limit exceeded.
        """
        now = time.time()
        window_start = now - self.window_seconds

        with self._lock:
            # Remove timestamps outside the window
            self._requests[conn_id] = [ts for ts in self._requests[conn_id] if ts > window_start]

            # Check if limit exceeded
            if len(self._requests[conn_id]) >= self.max_requests:
                return False

            # Record this request
            self._requests[conn_id].append(now)
            return True

    def remove_connection(self, conn_id: str) -> None:
        """Clean up tracking data when a connection closes.

        Args:
            conn_id: The connection ID to remove.
        """
        with self._lock:
            self._requests.pop(conn_id, None)

    def get_remaining(self, conn_id: str) -> int:
        """Get the number of remaining requests in the current window.

        Args:
            conn_id: The connection ID to check.

        Returns:
            Number of remaining requests allowed.
        """
        now = time.time()
        window_start = now - self.window_seconds

        with self._lock:
            current_count = len([ts for ts in self._requests.get(conn_id, []) if ts > window_start])
            return max(0, self.max_requests - current_count)

    def get_stats(self) -> dict:
        """Get rate limiter statistics.

        Returns:
            Dictionary with current tracking information.
        """
        with self._lock:
            return {
                "tracked_connections": len(self._requests),
                "max_requests": self.max_requests,
                "window_seconds": self.window_seconds,
            }


# Singleton instance
_rate_limiter: Optional[SlidingWindowRateLimiter] = None


def get_rate_limiter() -> SlidingWindowRateLimiter:
    """Get or create the rate limiter singleton."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = SlidingWindowRateLimiter()
    return _rate_limiter
