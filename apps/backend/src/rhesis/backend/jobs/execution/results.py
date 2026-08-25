"""
Task for collecting and processing test execution results.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict
from uuid import UUID

from rhesis.backend.app.crud.test_run import get_test_run
from rhesis.backend.app.database import get_db_with_tenant_variables
from rhesis.backend.app.models.enums import NotificationEventType
from rhesis.backend.celery.core import app
from rhesis.backend.jobs.base import EmailEnabledJob, email_notification, in_app_notification
from rhesis.backend.jobs.execution.result_processor import TestRunProcessor
from rhesis.backend.notifications.email.template_service import EmailTemplate

logger = logging.getLogger(__name__)


def _emit_terminal_tick(task, test_run, org_id, user_id, project_id, total: int) -> None:
    """Publish one last grid tick after the run's terminal status is written.

    Every other tick comes from an in-flight phase transition, and the last
    of those fires before this task runs -- so without this the final
    coalesced publish still reports the run as in Progress, and a client
    that stops refetching on ``is_terminal`` never learns the run finished.
    """
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
                celery_task_id=getattr(task.request, "id", None),
                entity_type="test_run",
                entity_id=test_run.id,
                source="collect_results",
                completed=total,
                total=total,
            )
        )
    except Exception:
        logger.debug("Terminal TestRunProgressed emit failed", exc_info=True)


@in_app_notification(NotificationEventType.TestRun.EXECUTION_COMPLETED)
@email_notification(
    template=EmailTemplate.TEST_EXECUTION_SUMMARY,
    subject_template='Test Execution "{task_name}" {execution_status}',
)
@app.task(base=EmailEnabledJob, bind=True, display_name="Test Execution Summary")
def collect_results(self, *args, **kwargs) -> Dict[str, Any]:
    """
    Collect and process test execution results, then send summary email.

    This is a chord callback that receives results from parallel test execution tasks.
    The organization_id and user_id are passed via task headers and handled by the task base class.

    Args:
        results: List of results from parallel test execution tasks (auto-provided by chord)

    Note:
        test_run_id is retrieved from task headers (self.request.headers['test_run_id'])

    Returns:
        Dict containing test execution summary
    """

    # Extract results from args (should be first argument)
    if len(args) >= 1:
        results = args[0]
    else:
        results = []
        self.log_with_context("warning", "No results received in chord callback")

    # Get test_run_id from headers
    test_run_id = self.request.headers.get("test_run_id")
    if not test_run_id:
        raise ValueError("test_run_id not found in task headers")

    self.log_with_context(
        "info",
        f"Chord callback triggered - collecting results for test run {test_run_id}",
    )
    self.log_with_context("debug", f"Processing {len(results) if results else 0} test results")

    # Access context using the new utility method
    org_id, user_id, project_id = self.get_tenant_context()

    try:
        # Use tenant-aware database session with explicit organization_id and user_id
        with get_db_with_tenant_variables(org_id or "", user_id or "", project_id or "") as db:
            # Get test run with tenant context
            test_run = get_test_run(db, UUID(test_run_id), organization_id=org_id, user_id=user_id)
            if not test_run:
                raise ValueError(f"Test run not found: {test_run_id}")

            # Set completion time now for consistent use throughout
            completion_time = datetime.now(timezone.utc)

            self.emit(f"Processing results for {len(results) if results else 0} tests")

            # Process test run results using the dedicated processor
            processor = TestRunProcessor(self.log_with_context)
            summary_data = processor.process_test_run_results(
                db, test_run, test_run_id, completion_time
            )

            passed = summary_data.get("tests_passed", 0)
            failed = summary_data.get("tests_failed", 0)
            errors = summary_data.get("execution_errors", 0)
            total = summary_data.get("total_tests", 0)
            exec_time = summary_data.get("execution_time")

            parts = [f"{passed} passed", f"{failed} failed"]
            if errors:
                parts.append(f"{errors} errors")
            if total > 0:
                rate = round(passed / total * 100)
                parts.append(f"{rate}% pass rate")
            summary_line = f"Results: {', '.join(parts)}"
            if exec_time:
                summary_line += f" in {exec_time}"
            self.emit(summary_line)
            _emit_terminal_tick(self, test_run, org_id, user_id, project_id, total)
            self.log_with_context("info", f"Test run update completed for: {test_run_id}")

            return summary_data

    except Exception as e:
        self.log_with_context(
            "error", f"Failed to collect results for test run {test_run_id}", error=str(e)
        )
        raise
