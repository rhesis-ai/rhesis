"""Security tests for WebSocket rate limiting.

These tests verify that the rate limiter correctly enforces
request limits to prevent denial of service attacks.
"""

import time
from unittest.mock import patch

import pytest

from rhesis.backend.app.services.websocket.rate_limiter import (
    SlidingWindowRateLimiter,
    get_rate_limiter,
)


@pytest.fixture
def rate_limiter():
    """Create a fresh rate limiter with test-friendly settings."""
    return SlidingWindowRateLimiter(max_requests=5, window_seconds=1)


class TestRateLimiterSecurity:
    """Security tests for rate limiter enforcement."""

    def test_messages_within_limit_are_processed(self, rate_limiter):
        """Messages within the rate limit are allowed."""
        conn_id = "test_conn_1"

        # All 5 requests within the limit should be allowed
        for i in range(5):
            assert rate_limiter.is_allowed(conn_id) is True

    def test_messages_exceeding_limit_are_rejected(self, rate_limiter):
        """Messages exceeding the rate limit are rejected."""
        conn_id = "test_conn_2"

        # Use up the limit
        for _ in range(5):
            rate_limiter.is_allowed(conn_id)

        # 6th request should be rejected
        assert rate_limiter.is_allowed(conn_id) is False
        # Additional requests should also be rejected
        assert rate_limiter.is_allowed(conn_id) is False

    def test_rate_limit_resets_after_window_expires(self, rate_limiter):
        """Rate limit resets after the time window expires."""
        conn_id = "test_conn_3"

        # Use up the limit
        for _ in range(5):
            rate_limiter.is_allowed(conn_id)

        # Should be at limit
        assert rate_limiter.is_allowed(conn_id) is False

        # Wait for window to expire
        time.sleep(1.1)

        # Should be allowed again
        assert rate_limiter.is_allowed(conn_id) is True

    def test_each_connection_has_independent_limit(self, rate_limiter):
        """Each connection has its own independent rate limit."""
        conn_a = "conn_a"
        conn_b = "conn_b"

        # Exhaust conn_a's limit
        for _ in range(5):
            rate_limiter.is_allowed(conn_a)

        assert rate_limiter.is_allowed(conn_a) is False

        # conn_b should still have its full limit
        for i in range(5):
            assert rate_limiter.is_allowed(conn_b) is True

        # Now conn_b should be at limit
        assert rate_limiter.is_allowed(conn_b) is False


class TestRateLimiterCleanup:
    """Tests for rate limiter cleanup functionality."""

    def test_remove_connection_clears_tracking(self, rate_limiter):
        """Removing a connection clears its tracking data."""
        conn_id = "test_conn_cleanup"

        # Make some requests
        for _ in range(3):
            rate_limiter.is_allowed(conn_id)

        # Remove the connection
        rate_limiter.remove_connection(conn_id)

        # Should have full limit again
        for i in range(5):
            assert rate_limiter.is_allowed(conn_id) is True

    def test_get_remaining_shows_correct_count(self, rate_limiter):
        """get_remaining returns correct remaining request count."""
        conn_id = "test_conn_remaining"

        assert rate_limiter.get_remaining(conn_id) == 5

        rate_limiter.is_allowed(conn_id)
        assert rate_limiter.get_remaining(conn_id) == 4

        rate_limiter.is_allowed(conn_id)
        rate_limiter.is_allowed(conn_id)
        assert rate_limiter.get_remaining(conn_id) == 2


class TestRateLimiterStats:
    """Tests for rate limiter statistics."""

    def test_get_stats_returns_configuration(self, rate_limiter):
        """get_stats returns limiter configuration."""
        stats = rate_limiter.get_stats()

        assert stats["max_requests"] == 5
        assert stats["window_seconds"] == 1
        assert "tracked_connections" in stats

    def test_tracked_connections_count_increases(self, rate_limiter):
        """Tracked connections count increases as new connections make requests."""
        assert rate_limiter.get_stats()["tracked_connections"] == 0

        rate_limiter.is_allowed("conn_1")
        assert rate_limiter.get_stats()["tracked_connections"] == 1

        rate_limiter.is_allowed("conn_2")
        assert rate_limiter.get_stats()["tracked_connections"] == 2


class TestRateLimiterSingleton:
    """Tests for the rate limiter singleton."""

    def test_get_rate_limiter_returns_singleton(self):
        """get_rate_limiter returns the same instance."""
        limiter1 = get_rate_limiter()
        limiter2 = get_rate_limiter()

        assert limiter1 is limiter2

    def test_singleton_is_rate_limiter_instance(self):
        """Singleton is a SlidingWindowRateLimiter instance."""
        limiter = get_rate_limiter()

        assert isinstance(limiter, SlidingWindowRateLimiter)


class TestRateLimiterThreadSafety:
    """Tests for thread safety of rate limiter."""

    def test_concurrent_access_is_safe(self, rate_limiter):
        """Rate limiter is thread-safe under concurrent access."""
        import threading

        conn_id = "concurrent_test"
        results = []
        errors = []

        def make_requests():
            try:
                for _ in range(10):
                    result = rate_limiter.is_allowed(conn_id)
                    results.append(result)
            except Exception as e:
                errors.append(e)

        # Start multiple threads making requests
        threads = [threading.Thread(target=make_requests) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have no errors
        assert len(errors) == 0
        # Should have some allowed and some rejected
        assert True in results
        assert False in results
