"""Result storage for WebSocket test and metric responses."""

import asyncio
import json
import logging
from collections import OrderedDict
from typing import Any, Callable, Dict, Optional

from rhesis.backend.app.services.connector.redis_client import redis_manager

logger = logging.getLogger(__name__)


class ResultStore:
    """Stores test/metric results and manages cancellation tracking.

    Owns the in-memory result dicts, asyncio events for waiters, and
    the cancelled-run OrderedDicts that prevent late results from being
    stored after a timeout.

    Args:
        track_background_task: Callback to schedule a fire-and-forget
            coroutine as a tracked ``asyncio.Task``.
    """

    def __init__(self, track_background_task: Callable) -> None:
        self._track_background_task = track_background_task

        self._test_results: Dict[str, Dict[str, Any]] = {}
        self._metric_results: Dict[str, Dict[str, Any]] = {}
        self._result_events: Dict[str, asyncio.Event] = {}

        self._cancelled_tests: OrderedDict = OrderedDict()
        self._cancelled_metrics: OrderedDict = OrderedDict()

    # ------------------------------------------------------------------
    # Test results
    # ------------------------------------------------------------------

    def resolve_test_result(self, test_run_id: str, result: Dict[str, Any]) -> None:
        """Store a test result and wake up any waiting coroutine."""
        if test_run_id in self._cancelled_tests:
            logger.warning(f"Ignoring late result for cancelled test run: {test_run_id}")
            return

        logger.info(
            f"Received test result from SDK: {test_run_id} "
            f"(status: {result.get('status', 'unknown')})"
        )

        self._test_results[test_run_id] = result

        event = self._result_events.get(test_run_id)
        if event:
            event.set()

        if redis_manager.is_available:
            try:
                self._track_background_task(self._publish_rpc_response(test_run_id, result))
            except Exception as e:
                logger.error(
                    f"Failed to schedule RPC response publish: {e}",
                    exc_info=True,
                )

    def get_test_result(self, test_run_id: str) -> Optional[Dict[str, Any]]:
        """Get test result if available (non-destructive)."""
        return self._test_results.get(test_run_id)

    def cleanup_test_result(self, test_run_id: str) -> None:
        """Remove a test result and mark as cancelled to reject late arrivals."""
        self._cancelled_tests[test_run_id] = True

        if test_run_id in self._test_results:
            del self._test_results[test_run_id]
            logger.debug(f"Cleaned up test result: {test_run_id}")
        else:
            logger.debug(f"Marked test run as cancelled: {test_run_id}")

        if len(self._cancelled_tests) > 10000:
            self._cancelled_tests = self._trim_cancelled(
                self._cancelled_tests, keep=5000, label="tests"
            )

    # ------------------------------------------------------------------
    # Metric results
    # ------------------------------------------------------------------

    def resolve_metric_result(self, metric_run_id: str, result: Dict[str, Any]) -> None:
        """Store a metric result and wake up any waiting coroutine."""
        if metric_run_id in self._cancelled_metrics:
            logger.warning(f"Ignoring late result for cancelled metric run: {metric_run_id}")
            return

        logger.info(
            f"Received metric result from SDK: {metric_run_id} "
            f"(status: {result.get('status', 'unknown')})"
        )
        self._metric_results[metric_run_id] = result

        event = self._result_events.get(metric_run_id)
        if event:
            event.set()

        if redis_manager.is_available:
            try:
                self._track_background_task(self._publish_rpc_response(metric_run_id, result))
            except Exception as e:
                logger.error(
                    f"Failed to publish metric RPC response: {e}",
                    exc_info=True,
                )

    def get_metric_result(self, metric_run_id: str) -> Optional[Dict[str, Any]]:
        """Get metric result if available (non-destructive)."""
        return self._metric_results.get(metric_run_id)

    def cleanup_metric_result(self, metric_run_id: str) -> None:
        """Remove a metric result and mark as cancelled to reject late arrivals."""
        self._cancelled_metrics[metric_run_id] = True

        if metric_run_id in self._metric_results:
            del self._metric_results[metric_run_id]
            logger.debug(f"Cleaned up metric result: {metric_run_id}")
        else:
            logger.debug(f"Marked metric run as cancelled: {metric_run_id}")

        if len(self._cancelled_metrics) > 10000:
            self._cancelled_metrics = self._trim_cancelled(
                self._cancelled_metrics, keep=5000, label="metrics"
            )

    # ------------------------------------------------------------------
    # Event management (used by Dispatcher for send-and-await)
    # ------------------------------------------------------------------

    def create_event(self, run_id: str) -> asyncio.Event:
        """Create and register a waiter event for a run ID."""
        event = asyncio.Event()
        self._result_events[run_id] = event
        return event

    def remove_event(self, run_id: str) -> None:
        """Remove a waiter event."""
        self._result_events.pop(run_id, None)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _publish_rpc_response(self, run_id: str, result: Dict[str, Any]) -> None:
        """Publish RPC response to Redis for cross-instance waiters."""
        try:
            channel = f"ws:rpc:response:{run_id}"
            await redis_manager.client.publish(channel, json.dumps(result))
            logger.debug(f"Published RPC response: {run_id}")
        except Exception as e:
            logger.error(
                f"Failed to publish RPC response for {run_id}: {e}",
                exc_info=True,
            )

    @staticmethod
    def _trim_cancelled(cancelled: OrderedDict, keep: int, label: str) -> OrderedDict:
        """Trim cancelled run entries, keeping only the newest items."""
        cancelled_items = list(cancelled.items())
        trimmed = OrderedDict(cancelled_items[-keep:])
        removed_count = len(cancelled_items) - len(trimmed)
        logger.info(
            f"Cleaned up old cancelled {label}. Removed {removed_count} entries, kept {keep}"
        )
        return trimmed
