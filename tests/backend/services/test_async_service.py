"""
Tests for the AsyncService base class.
"""

import time
from unittest.mock import patch

import pytest

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
        return "async_task_id"


@pytest.fixture
def service():
    """Create a service instance and reset the worker cache."""
    AsyncService._worker_cache = {"available": None, "checked_at": 0.0}
    return ConcreteAsyncService()


@pytest.mark.unit
@pytest.mark.services
class TestAsyncServiceWorkerCheck:
    """Tests for the _check_workers_available method."""

    @patch("rhesis.backend.worker.app.control.inspect")
    def test_check_workers_available_success(self, mock_inspect, service):
        """Test successful worker availability check."""
        mock_inspect_instance = mock_inspect.return_value
        mock_inspect_instance.ping.return_value = {"worker1@host": {"ok": "pong"}}

        assert service._check_workers_available() is True
        assert AsyncService._worker_cache["available"] is True
        mock_inspect_instance.ping.assert_called_once()

    @patch("rhesis.backend.worker.app.control.inspect")
    def test_check_workers_available_none(self, mock_inspect, service):
        """Test worker availability check when no workers are found."""
        mock_inspect_instance = mock_inspect.return_value
        mock_inspect_instance.ping.return_value = None

        assert service._check_workers_available() is False
        assert AsyncService._worker_cache["available"] is False

    @patch("rhesis.backend.worker.app.control.inspect")
    def test_check_workers_available_empty(self, mock_inspect, service):
        """Test worker availability check when workers list is empty."""
        mock_inspect_instance = mock_inspect.return_value
        mock_inspect_instance.ping.return_value = {}

        assert service._check_workers_available() is False
        assert AsyncService._worker_cache["available"] is False

    @patch("rhesis.backend.worker.app.control.inspect")
    def test_check_workers_available_exception(self, mock_inspect, service):
        """Test worker availability check when an exception occurs."""
        mock_inspect_instance = mock_inspect.return_value
        mock_inspect_instance.ping.side_effect = Exception("Connection error")

        assert service._check_workers_available() is False
        assert AsyncService._worker_cache["available"] is False

    @patch("rhesis.backend.worker.app.control.inspect")
    def test_check_workers_available_cache_hit(self, mock_inspect, service):
        """Test worker availability check uses cache within TTL."""
        AsyncService._worker_cache = {"available": True, "checked_at": time.monotonic()}

        assert service._check_workers_available() is True
        mock_inspect.assert_not_called()

    @patch("rhesis.backend.worker.app.control.inspect")
    def test_check_workers_available_cache_miss_ttl(self, mock_inspect, service):
        """Test worker availability check ignores cache after TTL."""
        mock_inspect_instance = mock_inspect.return_value
        mock_inspect_instance.ping.return_value = {"worker1": "pong"}

        AsyncService._worker_cache = {
            "available": False,
            "checked_at": time.monotonic() - AsyncService._worker_cache_ttl - 1,
        }

        assert service._check_workers_available() is True
        mock_inspect_instance.ping.assert_called_once()


@pytest.mark.unit
@pytest.mark.services
class TestAsyncServiceExecuteWithFallback:
    """Tests for the execute_with_fallback method."""

    def test_execute_with_fallback_async_success(self, service):
        """Test successful async execution."""
        with patch.object(service, "_check_workers_available", return_value=True):
            was_async, result = service.execute_with_fallback()

        assert was_async is True
        assert result is None

    def test_execute_with_fallback_no_workers_sync_success(self, service):
        """Test sync fallback when no workers are available."""
        with patch.object(service, "_check_workers_available", return_value=False):
            was_async, result = service.execute_with_fallback()

        assert was_async is False
        assert result == "sync_result"

    def test_execute_with_fallback_async_fails_sync_success(self, service):
        """Test sync fallback when async execution fails."""
        with patch.object(service, "_check_workers_available", return_value=True):
            was_async, result = service.execute_with_fallback(fail_async=True)

        assert was_async is False
        assert result == "sync_result"

    def test_execute_with_fallback_sync_fails_raises(self, service):
        """Test that sync failure raises an exception by default."""
        with patch.object(service, "_check_workers_available", return_value=False):
            with pytest.raises(ValueError, match="Sync failed"):
                service.execute_with_fallback(fail_sync=True)

    def test_execute_with_fallback_sync_fails_swallow(self, service):
        """Test that sync failure is swallowed when requested."""
        with patch.object(service, "_check_workers_available", return_value=False):
            was_async, result = service.execute_with_fallback(
                fail_sync=True, swallow_exceptions=True
            )

        assert was_async is False
        assert result is None

    def test_execute_with_fallback_provided_workers_available(self, service):
        """Test using provided workers_available flag."""
        with patch.object(service, "_check_workers_available") as mock_check:
            was_async, result = service.execute_with_fallback(workers_available=True)

            assert was_async is True
            mock_check.assert_not_called()


@pytest.mark.unit
@pytest.mark.services
class TestAsyncServiceBatchExecute:
    """Tests for the batch_execute method."""

    def test_batch_execute_all_async(self, service):
        """Test batch execution where all tasks are async."""
        items = [((), {}), ((), {})]
        with patch.object(service, "_check_workers_available", return_value=True):
            async_count, sync_count = service.batch_execute(items)

        assert async_count == 2
        assert sync_count == 0

    def test_batch_execute_all_sync(self, service):
        """Test batch execution where all tasks are sync."""
        items = [((), {}), ((), {})]
        with patch.object(service, "_check_workers_available", return_value=False):
            async_count, sync_count = service.batch_execute(items)

        assert async_count == 0
        assert sync_count == 2

    def test_batch_execute_mixed_async_fallback(self, service):
        """Test batch execution with mixed results due to async failure."""
        # First task succeeds async, second fails async and falls back to sync
        items = [((), {"fail_async": False}), ((), {"fail_async": True})]

        with patch.object(service, "_check_workers_available", return_value=True):
            async_count, sync_count = service.batch_execute(items)

        assert async_count == 1
        assert sync_count == 1

    def test_batch_execute_stops_async_after_first_fallback(self, service):
        """Test that once a sync fallback occurs, subsequent tasks in batch also use sync."""
        # First task fails async -> falls back to sync.
        # This should set workers_available to False for subsequent tasks.
        items = [((), {"fail_async": True}), ((), {"fail_async": False})]

        with patch.object(service, "_check_workers_available", return_value=True):
            # We patch execute_with_fallback to see what workers_available it gets
            with patch.object(
                service, "execute_with_fallback", wraps=service.execute_with_fallback
            ) as mock_execute:
                async_count, sync_count = service.batch_execute(items)

        assert async_count == 0
        assert sync_count == 2

        # Check workers_available argument in both calls
        assert mock_execute.call_args_list[0].kwargs["workers_available"] is True
        assert mock_execute.call_args_list[1].kwargs["workers_available"] is False


@pytest.mark.integration
@pytest.mark.services
class TestAsyncServiceIntegration:
    """Integration tests for the AsyncService base class."""

    def test_check_workers_available_real_broker(self):
        """Test worker availability check against the real configured broker."""
        # Reset cache to force a real check
        AsyncService._worker_cache = {"available": None, "checked_at": 0.0}

        service = ConcreteAsyncService()

        # Since no Celery workers are running in the backend test environment,
        # this should successfully connect to Redis but return False
        is_available = service._check_workers_available()

        assert is_available is False
        assert AsyncService._worker_cache["available"] is False

    def test_execute_with_fallback_real_broker(self):
        """Test execute_with_fallback using the real broker connection."""
        # Reset cache
        AsyncService._worker_cache = {"available": None, "checked_at": 0.0}

        service = ConcreteAsyncService()

        # Will check real broker, find no workers, and fallback to sync
        was_async, result = service.execute_with_fallback()

        assert was_async is False
        assert result == "sync_result"

    def test_batch_execute_real_broker(self):
        """Test batch_execute using the real broker connection."""
        # Reset cache
        AsyncService._worker_cache = {"available": None, "checked_at": 0.0}

        service = ConcreteAsyncService()

        items = [((), {}), ((), {})]

        # Will check real broker once, find no workers, and execute all sync
        async_count, sync_count = service.batch_execute(items)

        assert async_count == 0
        assert sync_count == 2
