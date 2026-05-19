"""Base service for async/sync task orchestration with Celery fallback.

This module provides a reusable base class for services that need to:
- Execute tasks asynchronously via Celery when workers are available
- Fallback to synchronous execution when the broker is unreachable
- Batch process multiple tasks efficiently
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

import kombu.exceptions
import redis.exceptions

logger = logging.getLogger(__name__)

BROKER_ERRORS = (
    redis.exceptions.RedisError,
    kombu.exceptions.OperationalError,
    ConnectionError,
    TimeoutError,
    OSError,
)

T = TypeVar("T")  # For return types


class AsyncService(ABC, Generic[T]):
    """
    Abstract base service for orchestrating async/sync task execution.

    Always attempts async dispatch first. Falls back to sync only when
    the broker is unreachable (BROKER_ERRORS). No pre-flight worker
    availability checks — those add latency on the hot path and trigger
    autoscaler cascades when Redis is slow.

    Subclasses must implement:
    - _execute_sync(): Synchronous fallback implementation
    - _enqueue_async(): Async task enqueuing logic
    """

    def __init__(self):
        """Initialize the async service."""
        pass

    @abstractmethod
    def _execute_sync(self, *args, **kwargs) -> T:
        """Execute task synchronously (fallback when broker is unreachable)."""
        pass

    @abstractmethod
    def _enqueue_async(self, *args, **kwargs) -> Any:
        """Enqueue async Celery task."""
        pass

    def execute_with_fallback(
        self,
        *args,
        swallow_exceptions: bool = False,
        **kwargs,
    ) -> tuple[bool, T | None]:
        """
        Execute task: try async first, fall back to sync on broker errors.

        Returns:
            Tuple of (was_async, result)
            - was_async: True if async task was enqueued, False if sync fallback
            - result: Result from sync execution, or None if async
        """
        try:
            task_result = self._enqueue_async(*args, **kwargs)
            logger.debug(f"Enqueued async task: {task_result}")
            return True, None
        except BROKER_ERRORS as e:
            logger.warning(f"Broker unavailable ({type(e).__name__}), falling back to sync: {e}")
        except Exception as e:
            logger.warning(f"Async task failed, using sync fallback: {e}")

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
    ) -> tuple[int, int]:
        """
        Execute multiple tasks: try async first, fall back to sync per-item.

        Returns:
            Tuple of (async_count, sync_count)
        """
        async_count = 0
        sync_count = 0

        for args, kwargs in items:
            was_async, _ = self.execute_with_fallback(
                *args,
                swallow_exceptions=swallow_exceptions,
                **kwargs,
            )
            if was_async:
                async_count += 1
            else:
                sync_count += 1

        return async_count, sync_count
