"""Base service for async/sync task orchestration with Celery fallback.

This module provides a reusable base class for services that need to:
- Execute tasks asynchronously via Celery when workers are available
- Fallback to synchronous execution in development environments
- Batch process multiple tasks efficiently
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")  # For return types


class AsyncService(ABC, Generic[T]):
    """
    Abstract base service for orchestrating async/sync task execution.

    Provides common patterns for:
    - Checking Celery worker availability
    - Enqueuing async tasks with fallback to sync
    - Batch processing with single worker check

    Subclasses must implement:
    - _execute_sync(): Synchronous fallback implementation
    - _enqueue_async(): Async task enqueuing logic
    """

    def __init__(self):
        """Initialize the async service."""
        pass

    def _check_workers_available(self) -> bool:
        """
        Check if Celery workers are available.

        Uses ping with 3 second timeout - more reliable for solo pool workers.
        Solo pool workers process tasks sequentially, so stats() may timeout
        while ping() is faster and gets prioritized.

        Returns:
            True if workers are available, False otherwise
        """
        try:
            from rhesis.backend.worker import app as celery_app

            inspect = celery_app.control.inspect(timeout=3.0)
            ping_result = inspect.ping()

            if not ping_result:
                return False

            logger.debug(
                f"Found {len(ping_result)} available worker(s): {list(ping_result.keys())}"
            )
            return True

        except Exception as e:
            logger.debug(f"Worker availability check failed: {e}")
            return False

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
        self, *args, workers_available: bool | None = None, **kwargs
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
            raise

    def batch_execute(self, items: list[tuple[tuple, dict]]) -> tuple[int, int]:
        """
        Execute multiple tasks using async/sync fallback strategy.

        Checks worker availability once before the loop to avoid N×3 second
        timeout when workers are unavailable (prevents batch delays).

        Args:
            items: List of (args_tuple, kwargs_dict) for each task

        Returns:
            Tuple of (async_count, sync_count)
        """
        async_count = 0
        sync_count = 0

        # Single worker check for entire batch
        workers_available = self._check_workers_available()

        for args, kwargs in items:
            was_async, _ = self.execute_with_fallback(
                *args, workers_available=workers_available, **kwargs
            )
            if was_async:
                async_count += 1
            else:
                sync_count += 1

        return async_count, sync_count
