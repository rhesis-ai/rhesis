"""Debounce cache for conversation-level trace metrics evaluation.

When a multi-turn conversation is active, each turn triggers a turn-level
evaluation immediately. For conversation-level metrics, we schedule a
delayed Celery task that fires after an inactivity timeout. Each new turn
resets the timer by revoking the previous scheduled task and scheduling
a new one.

This module manages the pending task IDs in Redis (or in-memory fallback)
so that any worker can look up and revoke a previously scheduled task.
"""

import logging
from typing import Optional

from rhesis.backend.app.constants import DEFAULT_CONVERSATION_DEBOUNCE_SECONDS
from rhesis.backend.app.services.cache import RedisBackedCache
from rhesis.backend.app.services.redis_constants import RedisDatabase

logger = logging.getLogger(__name__)

_PREFIX = "tracemetrics:pending:"
_COMPLETE_PREFIX = "tracemetrics:complete:"


class TraceMetricsDebounceCache(RedisBackedCache):
    """Tracks pending conversation-level evaluation task IDs per trace."""

    def __init__(self) -> None:
        super().__init__(
            redis_db=RedisDatabase.TRACE_METRICS_DEBOUNCE,
            cache_name="trace-metrics-debounce",
            ttl=600,
        )

    def register_pending_eval(self, trace_id: str, task_id: str) -> Optional[str]:
        """Store the Celery task ID for a scheduled conversation eval.

        Returns the previous task ID if one existed (caller should revoke it).
        """
        key = f"{_PREFIX}{trace_id}"
        previous = self._getdel(key)
        self._set(key, task_id)
        return previous

    def pop_pending_eval(self, trace_id: str) -> Optional[str]:
        """Retrieve and delete the pending task ID for a trace."""
        return self._getdel(f"{_PREFIX}{trace_id}")

    def mark_complete(self, trace_id: str) -> None:
        """Mark a conversation as complete to prevent further debounce scheduling."""
        self._set(f"{_COMPLETE_PREFIX}{trace_id}", "1")

    def is_complete(self, trace_id: str) -> bool:
        """Check if a conversation has been marked complete."""
        return self._get(f"{_COMPLETE_PREFIX}{trace_id}") == "1"


# ---------------------------------------------------------------
# Module-level singleton and public API
# ---------------------------------------------------------------

_cache = TraceMetricsDebounceCache()


def initialize_cache() -> None:
    """Initialize the trace metrics debounce cache (call at app startup)."""
    _cache.initialize()


def schedule_conversation_eval(
    trace_id: str,
    project_id: str,
    organization_id: str,
    debounce_seconds: int = DEFAULT_CONVERSATION_DEBOUNCE_SECONDS,
) -> None:
    """Schedule or reset a debounced conversation-level evaluation.

    If a previous evaluation was already scheduled for this trace_id,
    it is revoked before scheduling a new one.
    """
    from rhesis.backend.celery.core import app as celery_app
    from rhesis.backend.tasks.telemetry.evaluate import (
        evaluate_conversation_trace_metrics,
    )

    # Schedule new delayed task first to get the task ID
    result = evaluate_conversation_trace_metrics.apply_async(
        args=[trace_id, project_id, organization_id],
        countdown=debounce_seconds,
    )

    # Register and get previous task ID (if any)
    previous_task_id = _cache.register_pending_eval(trace_id, result.id)
    if previous_task_id:
        celery_app.control.revoke(previous_task_id)
        logger.debug(
            f"[TRACE_METRICS] Revoked previous conversation eval "
            f"task {previous_task_id} for trace {trace_id}"
        )

    logger.debug(
        f"[TRACE_METRICS] Scheduled conversation eval "
        f"task {result.id} for trace {trace_id} "
        f"(countdown={debounce_seconds}s)"
    )


def signal_conversation_complete(
    trace_id: str,
    project_id: str,
    organization_id: str,
) -> None:
    """Bypass debounce and evaluate conversation metrics immediately.

    Called when Penelope finishes a multi-turn test execution. The
    conversation is definitively over so there is no need to wait for
    the inactivity timeout.

    Steps:
      1. Dispatch immediate conversation evaluation (if this fails,
         the pending debounce remains as a safety net).
      2. Mark the trace as complete so future turns (still in the
         enrichment pipeline) skip debounce scheduling.
      3. Revoke any pending debounced task.
    """
    from rhesis.backend.celery.core import app as celery_app
    from rhesis.backend.tasks.telemetry.evaluate import (
        evaluate_conversation_trace_metrics,
    )

    # Dispatch first: if this fails the debounce stays as a safety net.
    evaluate_conversation_trace_metrics.delay(trace_id, project_id, organization_id)
    logger.debug(
        f"[TRACE_METRICS] Dispatched immediate conversation eval "
        f"for trace {trace_id} (conversation complete)"
    )

    # Mark complete so in-flight turns skip debounce scheduling.
    _cache.mark_complete(trace_id)

    # Revoke the pending debounced task (no longer needed).
    previous_task_id = _cache.pop_pending_eval(trace_id)
    if previous_task_id:
        celery_app.control.revoke(previous_task_id)
        logger.debug(
            f"[TRACE_METRICS] Revoked debounced conversation eval "
            f"task {previous_task_id} for trace {trace_id} "
            f"(conversation marked complete)"
        )


def is_conversation_complete(trace_id: str) -> bool:
    """Check whether a conversation has been marked complete."""
    return _cache.is_complete(trace_id)
