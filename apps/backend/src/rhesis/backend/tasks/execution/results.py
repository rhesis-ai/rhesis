"""
Task for collecting and processing test execution results.
"""

from datetime import datetime
from typing import Any, Dict
from uuid import UUID

from rhesis.backend.app import crud
from rhesis.backend.app.database import get_db_with_tenant_variables
from rhesis.backend.notifications.email.template_service import EmailTemplate
from rhesis.backend.tasks.base import BaseTask, email_notification
from rhesis.backend.tasks.execution.result_processor import TestRunProcessor
from rhesis.backend.worker import app


@email_notification(
    template=EmailTemplate.TEST_EXECUTION_SUMMARY,
    subject_template='Test Execution "{task_name}" {execution_status}',
)
@app.task(base=BaseTask, bind=True, display_name="Test Execution Summary")
def collect_results(self, *args, **kwargs) -> Dict[str, Any]:
    """
    Collect and process test execution results, then send summary email.

    This is a chord callback that receives results from parallel test execution tasks.
    The organization_id and user_id are passed via task headers and handled by BaseTask.

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
    org_id, user_id = self.get_tenant_context()

    try:
        # Use tenant-aware database session with explicit organization_id and user_id
        with get_db_with_tenant_variables(org_id or "", user_id or "") as db:
            # Get test run with tenant context
            test_run = crud.get_test_run(
                db, UUID(test_run_id), organization_id=org_id, user_id=user_id
            )
            if not test_run:
                raise ValueError(f"Test run not found: {test_run_id}")

            # Set completion time now for consistent use throughout
            completion_time = datetime.utcnow()

            # Process test run results using the dedicated processor
            processor = TestRunProcessor(self.log_with_context)
            summary_data = processor.process_test_run_results(
                db, test_run, test_run_id, completion_time
            )

            self.log_with_context("info", f"Test run update completed for: {test_run_id}")

            return summary_data

    except Exception as e:
        self.log_with_context(
            "error", f"Failed to collect results for test run {test_run_id}", error=str(e)
        )
        raise
