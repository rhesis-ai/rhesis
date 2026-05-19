"""
Tests for the AsyncService base class.
"""

from unittest.mock import patch

import kombu.exceptions
import pytest
import redis.exceptions

from rhesis.backend.app.services.async_service import AsyncService


class ConcreteAsyncService(AsyncService[str]):
    """Concrete implementation of AsyncService for testing."""

    def _execute_sync(self, *args, **kwargs) -> str:
        if kwargs.get("fail_sync"):
            raise ValueError("Sync failed")
        return "sync_result"

    def _enqueue_async(self, *args, **kwargs) -> str:
        if kwargs.get("fail_async"):
            raise ValueError("Async failed")
        if kwargs.get("fail_broker"):
            raise redis.exceptions.ConnectionError("Redis unavailable")
        return "async_task_id"


@pytest.fixture
def service():
    """Create a service instance."""
    return ConcreteAsyncService()


@pytest.mark.unit
@pytest.mark.services
class TestAsyncServiceExecuteWithFallback:
    """Tests for the execute_with_fallback method."""

    def test_execute_with_fallback_async_success(self, service):
        """Test successful async execution."""
        was_async, result = service.execute_with_fallback()

        assert was_async is True
        assert result is None

    def test_execute_with_fallback_broker_error_sync_fallback(self, service):
        """Test sync fallback when broker is unreachable."""
        was_async, result = service.execute_with_fallback(fail_broker=True)

        assert was_async is False
        assert result == "sync_result"

    def test_execute_with_fallback_async_fails_sync_success(self, service):
        """Test sync fallback when async execution fails with non-broker error."""
        was_async, result = service.execute_with_fallback(fail_async=True)

        assert was_async is False
        assert result == "sync_result"

    def test_execute_with_fallback_sync_fails_raises(self, service):
        """Test that sync failure raises an exception by default."""
        with pytest.raises(ValueError, match="Sync failed"):
            service.execute_with_fallback(fail_broker=True, fail_sync=True)

    def test_execute_with_fallback_sync_fails_swallow(self, service):
        """Test that sync failure is swallowed when requested."""
        was_async, result = service.execute_with_fallback(
            fail_broker=True, fail_sync=True, swallow_exceptions=True
        )

        assert was_async is False
        assert result is None

    def test_execute_with_fallback_kombu_error(self, service):
        """Test sync fallback on kombu OperationalError."""
        with patch.object(
            service,
            "_enqueue_async",
            side_effect=kombu.exceptions.OperationalError("Broker down"),
        ):
            was_async, result = service.execute_with_fallback()

        assert was_async is False
        assert result == "sync_result"

    def test_execute_with_fallback_timeout_error(self, service):
        """Test sync fallback on TimeoutError."""
        with patch.object(
            service,
            "_enqueue_async",
            side_effect=TimeoutError("Connection timed out"),
        ):
            was_async, result = service.execute_with_fallback()

        assert was_async is False
        assert result == "sync_result"


@pytest.mark.unit
@pytest.mark.services
class TestAsyncServiceBatchExecute:
    """Tests for the batch_execute method."""

    def test_batch_execute_all_async(self, service):
        """Test batch execution where all tasks are async."""
        items = [((), {}), ((), {})]
        async_count, sync_count = service.batch_execute(items)

        assert async_count == 2
        assert sync_count == 0

    def test_batch_execute_all_sync(self, service):
        """Test batch execution where all tasks fall back to sync."""
        items = [((), {"fail_broker": True}), ((), {"fail_broker": True})]
        async_count, sync_count = service.batch_execute(items)

        assert async_count == 0
        assert sync_count == 2

    def test_batch_execute_mixed(self, service):
        """Test batch execution with mixed async and sync fallback."""
        items = [((), {}), ((), {"fail_async": True})]
        async_count, sync_count = service.batch_execute(items)

        assert async_count == 1
        assert sync_count == 1


@pytest.mark.integration
@pytest.mark.services
class TestAsyncServiceIntegration:
    """Integration tests for the AsyncService base class."""

    def test_execute_with_fallback_attempts_async_first(self):
        """Test that execute_with_fallback always attempts async first."""
        service = ConcreteAsyncService()
        was_async, result = service.execute_with_fallback()

        assert was_async is True
        assert result is None
