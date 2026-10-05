"""
Sequential execution implementation for test cases.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from rhesis.backend.app.models.test_configuration import TestConfiguration
from rhesis.backend.app.models.test_run import TestRun
from rhesis.backend.app.services.run_models import resolve_run_models
from rhesis.backend.app.services.test_run_timing import TestPhase
from rhesis.backend.jobs.enums import ExecutionMode, RunStatus
from rhesis.backend.jobs.execution.executors.data import get_live_metric_backends
from rhesis.backend.jobs.execution.modes import is_multi_turn_test
from rhesis.backend.jobs.execution.run import update_test_run_status
from rhesis.backend.jobs.execution.shared import (
    create_execution_result,
    create_failure_result,
    is_task_revoked,
    run_on_thread_loop,
    trigger_results_collection,
    update_test_run_start,
)
from rhesis.backend.jobs.execution.test_execution import execute_test

logger = logging.getLogger(__name__)


def _narrate_completion(
    result: Any,
    index: int,
    total: int,
    on_progress=None,
    on_emit=None,
) -> None:
    """Report one finished test to the progress and activity-log callbacks.

    A test whose endpoint rejected the call still returns normally here (the Error row is
    already persisted), so a bare "completed" line told a reader nothing about a run the
    target refused wholesale. Reports the status code and the target's own reason instead.
    """
    endpoint_error = result.get("endpoint_error") if isinstance(result, dict) else None

    if endpoint_error:
        logger.info(f"Test {index}/{total} reported as Error: {endpoint_error['summary']}")
    else:
        logger.info(f"Test {index}/{total} completed successfully")

    if on_progress:
        on_progress(index, total)
    if on_emit:
        if endpoint_error:
            on_emit(f"Test {index}/{total} endpoint error: {endpoint_error['message']}")
        else:
            on_emit(f"Test {index}/{total} completed")


def _rollback_after_failure(session: Session) -> None:
    """Put the session back in a usable state after a test failed.

    ``execute_test`` writes its results on this same session, so a database error
    leaves the transaction needing a rollback. Without one, the next iteration's
    commit raises ``PendingRollbackError`` from outside any handler and the whole
    run dies with it -- remaining tests, terminal status and results collection
    included. A rollback that itself fails (dead connection) is logged and left:
    the next test will fail the same way, one row at a time, which is the
    containment this loop is meant to have.
    """
    try:
        session.rollback()
    except Exception:
        logger.warning("Rollback after a failed test did not succeed", exc_info=True)


def execute_tests_sequentially(
    session: Session,
    test_config: TestConfiguration,
    test_run: TestRun,
    tests: List,
    reference_test_run_id: str | None = None,
    trace_id: str | None = None,
    on_progress=None,
    on_emit=None,
    on_test_phase=None,
) -> Dict[str, Any]:
    """Execute test cases sequentially, one after another.

    Args:
        session: Database session
        test_config: Test configuration model
        test_run: Test run model
        tests: List of test models to execute
        reference_test_run_id: Optional previous test run ID for re-scoring
        trace_id: Optional trace ID for trace-based evaluation
        on_progress: Optional callback(current, total) to update job progress
        on_emit: Optional callback(message) to write activity log entries
        on_test_phase: Optional callback(test_id, phase). Reports
            "generating" right before the test runs and "done" when it
            finishes, same as the batch path. "evaluating" is also reported,
            but from inside execute_test's call chain (SingleTurnRunner.run /
            MultiTurnRunner.run, not this loop) -- that's the real seam
            between invocation and metric evaluation, just three call frames
            deeper here than in batch.
    """
    logger.info(f"Starting sequential execution for test run {test_run.id} with {len(tests)} tests")

    start_time = datetime.now(timezone.utc)
    results = []

    # Update test run with start information using shared utility
    update_test_run_start(session, test_run, ExecutionMode.SEQUENTIAL, len(tests), start_time)

    # Builds only the models this run uses (app/services/run_models.py). Tests and metrics
    # are read again here, so one edited since dispatch still gets its model.
    run_models = resolve_run_models(
        session,
        test_config,
        test_run,
        replay=bool(reference_test_run_id or trace_id),
        live_backends=get_live_metric_backends(
            session,
            tests,
            test_config,
            str(test_config.organization_id) if test_config.organization_id else None,
            str(test_config.user_id) if test_config.user_id else None,
        ),
        live_multi_turn=any(is_multi_turn_test(test) for test in tests),
    )

    # Cooperative cancellation: checked once per test, the only safe point in
    # a loop that otherwise blocks on a synchronous run_on_thread_loop() per test.
    # Same revoke set the batch runner polls, populated by revoke() from
    # either the test-run cancel endpoint or the job cancel endpoint.
    celery_task_id = (test_run.attributes or {}).get("task_id")
    was_cancelled = False

    # Execute tests one by one
    for i, test in enumerate(tests, 1):
        if is_task_revoked(celery_task_id):
            logger.info(
                f"Revoke detected before test {i}/{len(tests)} — "
                f"stopping sequential execution for test run {test_run.id}"
            )
            was_cancelled = True
            break

        logger.info(f"Executing test {i}/{len(tests)}: {test.id}")

        if on_test_phase:
            try:
                on_test_phase(str(test.id), TestPhase.GENERATING)
            except Exception:
                logger.debug("on_test_phase(generating) failed", exc_info=True)

        try:
            # End the transaction the previous test left open: otherwise the connection
            # sits "idle in transaction" across the whole LLM call, blocking vacuum and
            # holding a pool slot. expire_on_commit=False keeps test_config / test_run
            # usable after. Inside the try: a commit that fails has to be contained to
            # this test like any other failure.
            session.commit()

            result = run_on_thread_loop(
                execute_test(
                    db=session,
                    test_config_id=str(test_config.id),
                    test_run_id=str(test_run.id),
                    test_id=str(test.id),
                    endpoint_id=str(test_config.endpoint_id),
                    organization_id=str(test_config.organization_id)
                    if test_config.organization_id
                    else None,
                    user_id=str(test_config.user_id) if test_config.user_id else None,
                    execution_model=run_models.execution,
                    evaluation_model=run_models.evaluation,
                    reference_test_run_id=reference_test_run_id,
                    trace_id=trace_id,
                    on_test_phase=on_test_phase,
                )
            )
            results.append(result)

            _narrate_completion(result, i, len(tests), on_progress, on_emit)

        except Exception as e:
            _rollback_after_failure(session)
            logger.error(f"Test {i}/{len(tests)} failed: {str(e)}")
            # Create failure result using shared utility
            failure_result = create_failure_result(str(test.id), e)
            results.append(failure_result)
            if on_progress:
                on_progress(i, len(tests))
            if on_emit:
                # The reason is the whole point of reading the activity log; the batch
                # path has always included it and this one silently dropped it.
                on_emit(f"Test {i}/{len(tests)} failed: {e}")
        finally:
            if on_test_phase:
                try:
                    on_test_phase(str(test.id), TestPhase.DONE)
                except Exception:
                    logger.debug("on_test_phase(done) failed", exc_info=True)

    end_time = datetime.now(timezone.utc)
    execution_time = (end_time - start_time).total_seconds()

    if was_cancelled:
        logger.info(
            f"Sequential execution cancelled for test run {test_run.id} "
            f"after {len(results)}/{len(tests)} tests"
        )
        # No collect_results dispatch: the run stopped partway, so there is
        # nothing to aggregate and the session is still open here, unlike the
        # batch path, so the status update needs no new session.
        update_test_run_status(session, test_run, RunStatus.CANCELLED.value)
        session.commit()

        return create_execution_result(
            test_run,
            test_config,
            len(tests),
            ExecutionMode.SEQUENTIAL,
            execution_time=execution_time,
            completed_at=end_time.isoformat(),
            status="cancelled",
        )

    logger.info(
        f"Sequential execution completed for test run {test_run.id} in {execution_time:.2f} seconds"
    )

    # Trigger results collection as a proper Celery task to get the same
    # processing as parallel execution
    try:
        collection_task = trigger_results_collection(test_config, str(test_run.id), results)
        logger.info(f"Results collection task started: {collection_task.id}")
    except Exception as e:
        logger.error(f"Error triggering results collection: {str(e)}")

    # Return standardized result using shared utility
    return create_execution_result(
        test_run,
        test_config,
        len(tests),
        ExecutionMode.SEQUENTIAL,
        execution_time=execution_time,
        completed_at=end_time.isoformat(),
    )
