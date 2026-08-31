"""
This module contains the main entry point for test configuration execution,
with detailed implementation in the execution/ directory modules.
"""

import logging
from uuid import UUID

from rhesis.backend.app.crud.test_run import get_test_run
from rhesis.backend.app.database import get_db_with_tenant_variables
from rhesis.backend.app.quota import QuotaResource
from rhesis.backend.app.services.usage import dispatch_accrual
from rhesis.backend.celery.core import app
from rhesis.backend.jobs.base import SilentJob
from rhesis.backend.jobs.enums import RunStatus
from rhesis.backend.jobs.execution.config import get_test_configuration
from rhesis.backend.jobs.execution.orchestration import execute_test_cases
from rhesis.backend.jobs.execution.run import (
    TestExecutionError,
    create_test_run,
    update_test_run_status,
)
from rhesis.backend.jobs.utils import (
    create_task_result,
    get_test_run_by_task_id,
    update_test_run_with_error,
    validate_task_parameters,
)

logger = logging.getLogger(__name__)


def _make_on_test_phase(self, test_run, org_id, user_id, project_id, total_tests):
    """Build the in-flight phase callback for the verdict grid's live columns.

    Tracks generating/evaluating test ids locally (there is no shared
    ExecutionContext between the batch and sequential paths) and emits a
    TestRunProgressed tick on every transition -- cheap to call at this
    frequency because TestRunSink coalesces publishes per test run at 500ms;
    this call site is not where the volume reduction happens.

    Also stamps each transition's moment into the timing cache, which is what
    lets the Summary grid animate from real execution timing instead of a
    scripted sweep. That write is dispatched off-thread (record_phase_async)
    rather than issued inline: batch execution runs many tests concurrently
    as coroutines on one shared event loop, and a synchronous Redis
    round-trip here would block every other in-flight test for its duration.
    See services/test_run_timing.py.
    """
    from datetime import datetime, timezone

    from rhesis.backend.app.services.test_run_timing import TestPhase, record_phase_async

    generating_ids: set = set()
    evaluating_ids: set = set()
    # A set, not a counter: a recovery pass re-runs a test through the whole
    # generating -> evaluating -> done cycle, and counting each "done" would
    # push completed past total.
    completed_ids: set = set()

    # Read once here rather than inside the callback: after the run's first
    # commit the ORM object is expired, and touching it from a worker thread
    # would refresh it off-session.
    test_run_id = str(test_run.id)

    def _on_test_phase(test_id: str, phase: TestPhase) -> None:
        if phase == TestPhase.GENERATING:
            generating_ids.add(test_id)
            evaluating_ids.discard(test_id)
        elif phase == TestPhase.EVALUATING:
            generating_ids.discard(test_id)
            evaluating_ids.add(test_id)
        elif phase == TestPhase.DONE:
            completed_ids.add(test_id)
            generating_ids.discard(test_id)
            evaluating_ids.discard(test_id)

        record_phase_async(test_run_id, test_id, phase)

        try:
            from rhesis.backend.events import emit
            from rhesis.backend.events.correlation import resolve_ids
            from rhesis.backend.events.types import TestRunProgressed

            trace_id, span_id = resolve_ids()
            emit(
                TestRunProgressed(
                    occurred_at=datetime.now(timezone.utc),
                    organization_id=UUID(org_id),
                    project_id=UUID(project_id) if project_id else None,
                    user_id=UUID(user_id) if user_id else None,
                    trace_id=trace_id,
                    span_id=span_id,
                    celery_task_id=getattr(self.request, "id", None),
                    entity_type="test_run",
                    entity_id=test_run.id,
                    source="execute_test_configuration",
                    completed=len(completed_ids),
                    total=total_tests,
                    generating_test_ids=[UUID(tid) for tid in generating_ids],
                    evaluating_test_ids=[UUID(tid) for tid in evaluating_ids],
                )
            )
        except Exception:
            logger.debug("TestRunProgressed emit failed", exc_info=True)

    return _on_test_phase


@app.task(
    base=SilentJob,
    name="rhesis.backend.jobs.execute_test_configuration",
    bind=True,
    display_name="Test Set Execution",
)
# with_tenant_context decorator removed - tenant context now passed directly
def execute_test_configuration(self, test_configuration_id: str, test_run_id: str | None = None):
    """
    Execute a test configuration by running all associated test cases.

    This task gets tenant context passed directly and should
    handle database sessions with the proper tenant context.

    Args:
        test_configuration_id: ID of the test configuration to execute.
        test_run_id: ID of a pre-created test run (created by the API with
            Queued status). If not provided, a test run is created here
            for backward compatibility.
    """
    # Validate parameters
    params_to_validate = {"test_configuration_id": test_configuration_id}
    if test_run_id:
        params_to_validate["test_run_id"] = test_run_id
    is_valid, error_msg = validate_task_parameters(**params_to_validate)
    if not is_valid:
        self.log_with_context("error", "Parameter validation failed", error=error_msg)
        raise ValueError(error_msg)

    self.log_with_context(
        "info",
        "Starting test configuration execution",
        test_configuration_id=test_configuration_id,
        test_run_id=test_run_id,
    )

    # Access context using the new utility method
    org_id, user_id, project_id = self.get_tenant_context()
    retries = getattr(self.request, "retries", 0)

    self.log_with_context("debug", "Task context retrieved", retries=retries)

    try:
        # Use tenant-aware database session with explicit organization_id and user_id
        with get_db_with_tenant_variables(org_id or "", user_id or "", project_id or "") as db:
            # Get test configuration with tenant context
            test_config = get_test_configuration(db, test_configuration_id, org_id)

            if test_run_id:
                # Test run was pre-created by the API with Queued status
                test_run = get_test_run(db, UUID(test_run_id), organization_id=org_id)
                if test_run is None:
                    # Run was deleted before the worker picked it up — treat as
                    # a terminal no-op so Celery does not retry the task.
                    from celery.exceptions import Ignore

                    self.log_with_context(
                        "info",
                        f"Test run {test_run_id} no longer exists (deleted), ignoring task",
                    )
                    raise Ignore()

                # The run may have been cancelled while sitting in the queue.
                # Bail out immediately so we don't overwrite the Cancelled status.
                current_status = test_run.status.name if test_run.status else None
                if current_status == RunStatus.CANCELLED.value:
                    self.log_with_context(
                        "info",
                        f"Test run {test_run_id} was cancelled before execution started, skipping",
                    )
                    return create_task_result(
                        self.request.id,
                        test_configuration_id,
                        test_run_id=test_run_id,
                        status="cancelled",
                    )

                # Transition Queued -> Progress.
                # task_id was already embedded at dispatch time by the router;
                # confirm it here as a no-op safety net.
                test_run.attributes = dict(test_run.attributes or {})
                test_run.attributes["task_id"] = self.request.id
                update_test_run_status(db, test_run, RunStatus.PROGRESS.value)
                db.commit()
                self.log_with_context(
                    "info",
                    f"Test run {test_run_id} transitioned to Progress",
                )
            else:
                # Backward compatibility: no pre-created test run
                existing_test_run = get_test_run_by_task_id(db, self.request.id, org_id)
                if existing_test_run:
                    self.log_with_context(
                        "info",
                        f"Found existing test run for task {self.request.id}",
                        existing_test_run_id=str(existing_test_run.id),
                        task_retry=True,
                    )
                    test_run = existing_test_run
                else:
                    self.log_with_context(
                        "info",
                        f"Creating new test run for task {self.request.id}",
                        test_configuration_id=test_configuration_id,
                    )
                    test_run = create_test_run(
                        db,
                        test_config,
                        {"id": self.request.id},
                        current_user_id=user_id,
                        initial_status=RunStatus.PROGRESS,
                    )
                    db.commit()
                    self.log_with_context(
                        "debug",
                        f"Test run {test_run.id} committed to database",
                    )

            self.set_entity("TestRun", str(test_run.id))

            # Extract re-scoring params from configuration attributes
            config_attrs = test_config.attributes or {}
            reference_test_run_id = config_attrs.get("reference_test_run_id")

            # total_tests is already on the run (create_test_run counts the
            # test set up front), so this is known before execution starts.
            total_tests = (test_run.attributes or {}).get("total_tests", 0)
            self.set_progress(0, total_tests)

            test_set_name = getattr(test_config.test_set, "name", None)
            endpoint_name = getattr(test_config.endpoint, "name", None)
            context_parts = [f"{total_tests} tests"]
            if test_set_name:
                context_parts.append(f"from '{test_set_name}'")
            if endpoint_name:
                context_parts.append(f"against '{endpoint_name}'")
            self.emit(f"Executing {' '.join(context_parts)}")

            # Execute test cases (parallel or sequential)
            on_test_phase = _make_on_test_phase(
                self, test_run, org_id, user_id, project_id, total_tests
            )
            result = execute_test_cases(
                db,
                test_config,
                test_run,
                reference_test_run_id=reference_test_run_id,
                on_progress=self.set_progress,
                on_emit=self.emit,
                on_test_phase=on_test_phase,
            )
            self.emit("Execution complete")

            # Accrue TEST_EXECUTIONS for the count actually processed by this
            # run -- result["total_tests"] is computed once at the start of
            # execute_test_cases from the same tests list it iterates, so it
            # reflects what was billed for, not what the test set currently
            # contains. Re-querying the test set's live count here instead
            # would open a window between execution and accrual: tests
            # added or removed from the set mid-run would shift what gets
            # billed away from what was actually executed.
            dispatch_accrual(org_id, QuotaResource.TEST_EXECUTIONS, result.get("total_tests", 0))

        # Use utility to create standardized result
        # Remove test_run_id from result if present to avoid duplicate parameter
        result_copy = result.copy()
        result_copy.pop("test_run_id", None)

        final_result = create_task_result(
            task_id=self.request.id,
            test_config_id=test_configuration_id,
            test_run_id=str(test_run.id),
            **result_copy,
        )

        self.log_with_context(
            "info",
            "Test configuration execution completed successfully",
            test_configuration_id=test_configuration_id,
            test_run_id=str(test_run.id),
            total_tests=result.get("total_tests", 0),
        )

        return final_result

    except Exception as e:
        self.log_with_context(
            "error",
            "Error executing test configuration",
            test_configuration_id=test_configuration_id,
            error=str(e),
            exception_type=type(e).__name__,
        )

        # Attempt to update test run status to failed
        with get_db_with_tenant_variables(org_id or "", user_id or "", project_id or "") as db:
            if test_run_id:
                test_run = get_test_run(db, UUID(test_run_id), organization_id=org_id)
            else:
                test_run = get_test_run_by_task_id(db, self.request.id, org_id)
            if test_run:
                success = update_test_run_with_error(db, test_run, str(e))
                if not success:
                    self.log_with_context("error", "Failed to update test run status")

        # Check if we've exceeded max_retries (from BaseJob)
        if retries >= self.max_retries:
            self.log_with_context(
                "warning", "Maximum retries reached, giving up", max_retries=self.max_retries
            )
            # Raise a specific error that should not trigger retry
            raise TestExecutionError(f"Failed after {self.max_retries} retries: {str(e)}")

        # Re-raise the original error to trigger retry behavior from BaseJob
        raise
