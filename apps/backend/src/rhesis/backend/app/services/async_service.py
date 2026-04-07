"""Base service for async/sync task orchestration with Celery fallback.

This module provides a reusable base class for services that need to:
- Execute tasks asynchronously via Celery when workers are available
- Fallback to synchronous execution in development environments
- Batch process multiple tasks efficiently
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")  # For return types


class AsyncService(ABC, Generic[T]):
    """
    Abstract base service for orchestrating async/sync task execution.

    Provides common patterns for:
    - Checking Celery worker availability (shared TTL cache across subclasses)
    - Enqueuing async tasks with fallback to sync
    - Batch processing with a single worker check per batch (or caller-supplied flag)

    Subclasses must implement:
    - _execute_sync(): Synchronous fallback implementation
    - _enqueue_async(): Async task enqueuing logic
    """

    _worker_cache: dict = {"available": None, "checked_at": 0.0}
    _worker_cache_ttl: float = 300.0  # 5 minutes TTL

    def __init__(self):
        """Initialize the async service."""
        pass

    def _check_workers_available(self) -> bool:
        """
        Check if Celery workers are available, with shared TTL caching.

        Uses monotonic time (immune to clock adjustments) and a 1-second ping
        timeout (faster than the default 3s, avoids blocking request handling).

        Returns:
            True if workers are available, False otherwise
        """
        now = time.monotonic()
        cache = self.__class__._worker_cache

        if cache["available"] is not None and now - cache["checked_at"] < self._worker_cache_ttl:
            return cache["available"]

        is_available = False
        try:
            from rhesis.backend.worker import app as celery_app

            inspect = celery_app.control.inspect(timeout=1.0)
            ping_result = inspect.ping()

            if ping_result:
                logger.debug(
                    f"Found {len(ping_result)} available worker(s): {list(ping_result.keys())}"
                )
                is_available = True

        except Exception as e:
            logger.debug(f"Worker availability check failed: {e}")

        cache["available"] = is_available
        cache["checked_at"] = time.monotonic()

        return is_available

    @abstractmethod
    def _execute_sync(self, *args, **kwargs) -> T:
        """
        Execute task synchronously (development fallback).

        Must be implemented by subclasses.

        Returns:
            Result of synchronous execution
        """
        pass

    @abstractmethod
    def _enqueue_async(self, *args, **kwargs) -> Any:
        """
        Enqueue async Celery task.

        Must be implemented by subclasses.

        Returns:
            Celery AsyncResult or task ID
        """
        pass

    def execute_with_fallback(
        self,
        *args,
        workers_available: bool | None = None,
        swallow_exceptions: bool = False,
        **kwargs,
    ) -> tuple[bool, T | None]:
        """
        Execute task with async/sync fallback strategy.

        This implements a robust fallback:
        1. Check if workers are available (or use cached result)
        2. If yes, try async execution (optimal for production)
        3. If no workers or async fails, fall back to sync (development-friendly)

        Args:
            *args: Positional arguments for task
            workers_available: Optional cached worker availability.
                             If None, will check on this call.
            **kwargs: Keyword arguments for task
            swallow_exceptions: If True, will swallow exceptions and return None

        Returns:
            Tuple of (was_async, result)
            - was_async: True if async task was enqueued, False if sync fallback
            - result: Result from sync execution, or None if async
        """
        # Check worker availability (use cached if provided)
        if workers_available is None:
            workers_available = self._check_workers_available()

        # Try async execution
        if workers_available:
            try:
                task_result = self._enqueue_async(*args, **kwargs)
                logger.debug(f"Enqueued async task: {task_result}")
                return True, None
            except Exception as e:
                logger.warning(f"Async task failed, using sync fallback: {e}")
        else:
            logger.info("No Celery workers available, using sync execution")

        # Fall back to sync execution
        try:
            result = self._execute_sync(*args, **kwargs)
            logger.info("Completed sync execution")
            return False, result
        except Exception as sync_error:
            logger.error(f"Sync execution failed: {sync_error}", exc_info=True)
            if swallow_exceptions:
                return False, None
            raise

    def batch_execute(
        self,
        items: list[tuple[tuple, dict]],
        swallow_exceptions: bool = False,
        workers_available: bool | None = None,
    ) -> tuple[int, int]:
        """
        Execute multiple tasks using async/sync fallback strategy.

        Checks worker availability once before the loop (unless ``workers_available``
        is provided) to avoid N×ping cost when workers are unavailable.

        Args:
            items: List of (args_tuple, kwargs_dict) for each task
            swallow_exceptions: If True, sync failures return (False, None) per item
            workers_available: If set, skip an extra ping; use for callers that
                already resolved availability (e.g. telemetry ingest orchestration).

        Returns:
            Tuple of (async_count, sync_count)
        """
        async_count = 0
        sync_count = 0

        if workers_available is None:
            workers_available = self._check_workers_available()

        for args, kwargs in items:
            was_async, _ = self.execute_with_fallback(
                *args,
                workers_available=workers_available,
                swallow_exceptions=swallow_exceptions,
                **kwargs,
            )
            if was_async:
                async_count += 1
            else:
                sync_count += 1
                workers_available = False

        return async_count, sync_count
