"""
Async batch runner — semaphore-gated concurrent test execution.

Contains the ``asyncio.gather``-based runner and the per-test coroutine.
Delegates to `invocation.py` and `evaluation.py`.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List

from rhesis.backend.tasks.execution.batch.context import ExecutionContext
from rhesis.backend.tasks.execution.batch.evaluation import evaluate_metrics
from rhesis.backend.tasks.execution.batch.invocation import is_multi_turn_test, run_test

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cooperative cancellation helper
# ---------------------------------------------------------------------------


def _is_task_revoked(task_id: str | None) -> bool:
    """Return True if the Celery task has been revoked.

    Checks the worker-process in-memory revoke set — a pure dict lookup with
    no I/O.  Safe to call from any thread or coroutine running inside the
    worker.  Returns False if called outside a worker (e.g. in tests).
    """
    if not task_id:
        return False
    try:
        from celery.worker.state import revoked as _revoked  # noqa: PLC0415

        return task_id in _revoked
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Cancellation watchdog
# ---------------------------------------------------------------------------


async def _cancellation_watchdog(
    task_id: str | None,
    tasks: List[asyncio.Task],
    poll_interval: float = 1.0,
) -> None:
    """Poll the Celery revoke set and cancel all batch tasks when triggered.

    Runs as a sibling asyncio Task alongside the test fan-out.  When the
    Celery task is revoked, each test Task receives a CancelledError at its
    next await point (i.e. mid HTTP call, mid metric evaluation, etc.).
    The watchdog exits as soon as it fires or is itself cancelled by run_batch
    after the tests finish naturally.
    """
    while True:
        await asyncio.sleep(poll_interval)
        if _is_task_revoked(task_id):
            pending = [t for t in tasks if not t.done()]
            logger.info(f"[BATCH] Revoke detected — cancelling {len(pending)} in-flight tasks")
            for t in pending:
                t.cancel()
            return


# ---------------------------------------------------------------------------
# Top-level batch runner
# ---------------------------------------------------------------------------


async def run_batch(
    ctx: ExecutionContext,
    test_ids: List[str],
) -> List[Dict[str, Any]]:
    """Async entry point: run all tests with semaphore-gated concurrency."""
    semaphore = asyncio.Semaphore(ctx.batch_concurrency)

    # Create a single PenelopeAgent for the batch (model + metrics are shared;
    # per-test state is created fresh inside a_execute_test).
    penelope_agent = None
    has_multi_turn = any(
        is_multi_turn_test(ctx.test_data.get(tid, {}).get("test")) for tid in test_ids
    )
    if has_multi_turn:
        from rhesis.penelope import PenelopeAgent

        penelope_agent = PenelopeAgent(model=ctx.model) if ctx.model else PenelopeAgent()

        # Fetch credentials / tokens once before the concurrent fan-out so
        # all coroutines hit a warm cache rather than racing to fetch in parallel.
        await penelope_agent.model.warmup()

    # Create a single MetricEvaluator for the batch (stateless, safe to share).
    evaluator = None
    if ctx.metric_configs:
        from rhesis.backend.metrics.evaluator import MetricEvaluator

        evaluator = MetricEvaluator(
            model=ctx.model,
            connector_metric_sender=ctx.connector_metric_sender,
        )

    tasks = [
        asyncio.create_task(
            _execute_single_test(ctx, test_id, semaphore, penelope_agent, evaluator)
        )
        for test_id in test_ids
    ]

    watchdog = asyncio.create_task(_cancellation_watchdog(ctx.celery_task_id, tasks))

    try:
        results = await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        watchdog.cancel()
        await asyncio.gather(watchdog, return_exceptions=True)

    final_results: List[Dict[str, Any]] = []
    for test_id, result in zip(test_ids, results):
        if isinstance(result, asyncio.CancelledError):
            logger.info(f"[BATCH] Test {test_id} cancelled mid-flight")
            final_results.append({"test_id": test_id, "status": "cancelled", "execution_time": 0})
        elif isinstance(result, Exception):
            logger.error(f"[BATCH] Test {test_id} raised exception: {result}")
            final_results.append(
                {
                    "test_id": test_id,
                    "status": "failed",
                    "error": str(result),
                    "execution_time": 0,
                    "exception_type": type(result).__name__,
                }
            )
        else:
            final_results.append(result)

    return final_results


# ---------------------------------------------------------------------------
# Per-test coroutine
# ---------------------------------------------------------------------------


async def _execute_single_test(
    ctx: ExecutionContext,
    test_id: str,
    semaphore: asyncio.Semaphore,
    penelope_agent: Any = None,
    evaluator: Any = None,
) -> Dict[str, Any]:
    """Unified coroutine for both single-turn and multi-turn tests."""
    async with semaphore:
        if test_id in ctx.existing_result_ids:
            logger.info(f"[BATCH] Skipping test {test_id}: result already exists")
            return {"test_id": test_id, "status": "skipped", "execution_time": 0}

        td = ctx.test_data.get(test_id)
        if not td:
            return {
                "test_id": test_id,
                "status": "failed",
                "error": "Test data not pre-fetched",
                "execution_time": 0,
            }

        test = td["test"]
        prompt_content = td["prompt_content"]
        expected_response = td["expected_response"]

        is_multi_turn = is_multi_turn_test(test)

        test_execution_context = {
            "test_run_id": str(ctx.test_run.id),
            "test_id": test_id,
            "test_configuration_id": str(ctx.test_config.id),
        }

        start_time = time.monotonic()
        deferred_traces: list = []
        output: Dict[str, Any] = {}
        penelope_metrics: Dict[str, Any] = {}
        metrics_results: Dict[str, Any] = {}

        try:
            # --- Run the test ---
            try:
                coro = run_test(
                    ctx,
                    test,
                    test_id,
                    prompt_content,
                    test_execution_context,
                    is_multi_turn,
                    deferred_traces,
                    penelope_agent,
                )
                result = await asyncio.wait_for(coro, timeout=ctx.per_test_timeout)
                output = result.get("output", {})
                penelope_metrics = result.get("penelope_metrics", {})
                deferred_traces = result.get("deferred_traces", deferred_traces)
            except asyncio.TimeoutError:
                logger.error(f"[BATCH] Test {test_id} timed out after {ctx.per_test_timeout}s")
                return {
                    "test_id": test_id,
                    "status": "failed",
                    "error": f"Timeout after {ctx.per_test_timeout}s",
                    "execution_time": (time.monotonic() - start_time) * 1000,
                }
            except Exception as e:
                logger.error(f"[BATCH] Test {test_id} failed: {e}", exc_info=True)
                return {
                    "test_id": test_id,
                    "status": "failed",
                    "error": str(e),
                    "execution_time": (time.monotonic() - start_time) * 1000,
                    "exception_type": type(e).__name__,
                }

            # --- Async metric evaluation ---
            metrics_results = dict(penelope_metrics)
            if evaluator and ctx.metric_configs:
                metrics_results = await evaluate_metrics(
                    ctx,
                    evaluator,
                    test,
                    test_id,
                    output,
                    prompt_content,
                    expected_response,
                    is_multi_turn,
                    penelope_metrics,
                )

            execution_time = (time.monotonic() - start_time) * 1000

            # --- Persist result and deferred traces in a thread ---
            try:
                from rhesis.backend.tasks.execution.batch.persist import persist_result

                await asyncio.to_thread(
                    persist_result,
                    ctx,
                    test_id,
                    test,
                    output,
                    metrics_results,
                    deferred_traces,
                    execution_time,
                    is_multi_turn,
                )
            except Exception as e:
                logger.error(f"[BATCH] Persist failed for {test_id}: {e}", exc_info=True)
                return {
                    "test_id": test_id,
                    "status": "failed",
                    "error": f"Persist failed: {e}",
                    "execution_time": execution_time,
                }

            return {
                "test_id": test_id,
                "status": "succeeded",
                "execution_time": execution_time,
                "metrics": metrics_results,
            }
        finally:
            ctx.test_data.pop(test_id, None)
            ctx.input_files.pop(test_id, None)
            deferred_traces.clear()
            output.clear()
            penelope_metrics.clear()
