"""
Batch async execution engine for test sets.

Replaces the Celery chord fan-out with a single Celery task that runs all
tests concurrently using asyncio.gather() with a configurable semaphore.
One Celery task = one worker slot per test set.

Public API:
    execute_tests_as_batch  — called from orchestration.py
    ExecutionContext         — re-exported for type hints
"""

import asyncio
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app.models.test import Test
from rhesis.backend.app.models.test_configuration import TestConfiguration
from rhesis.backend.app.models.test_run import TestRun
from rhesis.backend.tasks.enums import ExecutionMode
from rhesis.backend.tasks.execution.batch.context import (
    ExecutionContext,
    prefetch_execution_context,
)
from rhesis.backend.tasks.execution.batch.profiling import (
    ResourceSnapshot,
    log_batch_report,
)
from rhesis.backend.tasks.execution.batch.runner import run_batch

__all__ = ["execute_tests_as_batch", "ExecutionContext"]

logger = logging.getLogger(__name__)

# Per-thread event loop, reused across tasks in the same Celery worker thread.
# asyncio.run() creates and destroys a loop each invocation; LiteLLM's internal
# LoggingWorker spawns background tasks on the loop that are destroyed mid-flight
# when the loop closes, producing "Task was destroyed but it is pending!" warnings
# and potentially dropping logging callbacks.  Reusing a loop per thread keeps
# those background tasks alive for the thread's lifetime.
# Thread-local (not process-global) so it is safe under --pool threads.
_thread_local = threading.local()


def _run_async(coro):
    """Run a coroutine on the calling thread's persistent event loop."""
    loop = getattr(_thread_local, "loop", None)
    if loop is None or loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        _thread_local.loop = loop
    return loop.run_until_complete(coro)


def _persist_failed_results(ctx: "ExecutionContext", results: List[Dict[str, Any]]) -> None:
    """Write error TestResult rows for tests that failed without ever being persisted.

    Called after all recovery rounds complete.  We query the DB first so that
    tests which failed on the invocation path but were later retried and
    persisted by a recovery round don't get a duplicate row.
    """
    from uuid import UUID

    from rhesis.backend.app.database import get_db_with_tenant_variables
    from rhesis.backend.app.models.test_result import TestResult
    from rhesis.backend.tasks.execution.batch.persist import persist_result

    failed = [r for r in results if r.get("status") == "failed"]
    if not failed:
        return

    failed_ids = [r["test_id"] for r in failed]

    try:
        with get_db_with_tenant_variables(ctx.organization_id, ctx.user_id or "") as db:
            existing = {
                str(row.test_id)
                for row in db.query(TestResult.test_id)
                .filter(
                    TestResult.test_run_id == UUID(str(ctx.test_run.id)),
                    TestResult.test_id.in_([UUID(tid) for tid in failed_ids]),
                    TestResult.deleted_at.is_(None),
                )
                .all()
            }
    except Exception as e:
        logger.warning(f"[BATCH] Could not check existing error records: {e}")
        return

    for result in failed:
        tid = result["test_id"]
        if tid in existing:
            continue

        snapshot = ctx.test_data_snapshot.get(tid)
        if not snapshot:
            logger.warning(f"[BATCH] Cannot persist error record for {tid}: no snapshot data")
            continue

        try:
            persist_result(
                ctx,
                tid,
                snapshot["test"],
                {"error": result.get("error", "Execution failed")},
                {},
                [],
                result.get("execution_time", 0),
                False,
            )
            logger.info(
                f"[BATCH] Persisted error record for failed test {tid}: "
                f"{result.get('error', '')}"
            )
        except Exception as e:
            logger.warning(f"[BATCH] Failed to persist error record for {tid}: {e}")


def execute_tests_as_batch(
    session: Session,
    test_config: TestConfiguration,
    test_run: TestRun,
    tests: List[Test],
    reference_test_run_id: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Three-phase batch execution: pre-fetch, asyncio.gather, trigger results."""
    from rhesis.backend.tasks.execution.shared import (
        create_execution_result,
        trigger_results_collection,
        update_test_run_start,
    )

    start_time = datetime.now(timezone.utc)
    total_tests = len(tests)

    update_test_run_start(
        session,
        test_run,
        ExecutionMode.PARALLEL,
        total_tests,
        start_time,
        batch_mode=True,
    )

    # Phase 1: Pre-fetch all shared data while we still have a DB session.
    ctx = prefetch_execution_context(
        session,
        test_config,
        test_run,
        tests,
        reference_test_run_id=reference_test_run_id,
        trace_id=trace_id,
    )
    # Capture the Celery task ID for cooperative cancellation in the async loop.
    ctx.celery_task_id = (test_run.attributes or {}).get("task_id")

    # Flush any pending writes (e.g. auth token refresh) and release the DB
    # connection back to the pool.  All needed data lives in ctx (models are
    # expunged).  Without this, the connection sits idle for the entire async
    # phase — potentially 30+ minutes — starving persist_result threads.
    session.commit()
    session.close()

    snap_before = ResourceSnapshot.take()
    logger.info(
        f"[BATCH] Starting: {total_tests} tests, "
        f"concurrency={ctx.batch_concurrency}, timeout={ctx.per_test_timeout}s, "
        f"rss={snap_before.peak_rss_mb:.0f}MB"
    )

    # Phase 2: Async execution (DB-free, uses deferred tracing).
    test_ids = [str(t.id) for t in tests if str(t.id) in ctx.test_data]
    results = _run_async(run_batch(ctx, test_ids))

    # Write error TestResult rows for tests that failed without being persisted
    # (e.g. invocation exceptions, timeouts).  Must run before trigger_results_collection
    # so the DB count includes those rows.
    _persist_failed_results(ctx, results)

    # Phase 3: Trigger results collection.
    wall_time_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
    snap_after = ResourceSnapshot.take()

    log_batch_report(
        before=snap_before,
        after=snap_after,
        wall_time_ms=wall_time_ms,
        total_tests=total_tests,
        results=results,
        concurrency=ctx.batch_concurrency,
        test_run_id=str(test_run.id),
    )

    # Skip results collection if the entire run was cancelled or the batch was
    # empty — there are no persisted test results to aggregate and calling
    # collect_results would erroneously overwrite the Cancelled status
    # (total_tests == 0 -> FAILED).
    skip_collection = not results or all(r.get("status") == "cancelled" for r in results)
    if not skip_collection:
        trigger_results_collection(test_config, str(test_run.id), results)

    return create_execution_result(
        test_run,
        test_config,
        total_tests,
        ExecutionMode.PARALLEL,
        execution_time_total=wall_time_ms,
        batch_mode=True,
    )
