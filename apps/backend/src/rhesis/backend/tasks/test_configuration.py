"""
This module contains the main entry point for test configuration execution,
with detailed implementation in the execution/ directory modules.
"""

from rhesis.backend.app.database import get_db_with_tenant_variables
from rhesis.backend.tasks.base import SilentTask
from rhesis.backend.tasks.execution.config import get_test_configuration
from rhesis.backend.tasks.execution.orchestration import execute_test_cases
from rhesis.backend.tasks.execution.run import (
    TestExecutionError,
    create_test_run,
)
from rhesis.backend.tasks.utils import (
    create_task_result,
    get_test_run_by_task_id,
    update_test_run_with_error,
    validate_task_parameters,
)
from rhesis.backend.worker import app


@app.task(
    base=SilentTask,
    name="rhesis.backend.tasks.execute_test_configuration",
    bind=True,
    display_name="Test Configuration Execution",
)
# with_tenant_context decorator removed - tenant context now passed directly
def execute_test_configuration(self, test_configuration_id: str):
    """
    Execute a test configuration by running all associated test cases.

    This task gets tenant context passed directly and should
    handle database sessions with the proper tenant context.
    """
    # Validate parameters
    is_valid, error_msg = validate_task_parameters(test_configuration_id=test_configuration_id)
    if not is_valid:
        self.log_with_context("error", "Parameter validation failed", error=error_msg)
        raise ValueError(error_msg)

    self.log_with_context(
        "info",
        "Starting test configuration execution",
        test_configuration_id=test_configuration_id,
    )

    # Access context using the new utility method
    org_id, user_id = self.get_tenant_context()
    retries = getattr(self.request, "retries", 0)

    self.log_with_context("debug", "Task context retrieved", retries=retries)

    try:
        # Use tenant-aware database session with explicit organization_id and user_id
        with get_db_with_tenant_variables(org_id or "", user_id or "") as db:
            # Get test configuration with tenant context
            test_config = get_test_configuration(db, test_configuration_id, org_id)

            # CRITICAL: Check for existing test run by TASK ID (not config ID)
            # This allows multiple test runs per configuration but prevents task retries
            # from creating multiple test runs for the same task
            existing_test_run = get_test_run_by_task_id(db, self.request.id, org_id)
            if existing_test_run:
                self.log_with_context(
                    "info",
                    f"Found existing test run for task {self.request.id}",
                    existing_test_run_id=str(existing_test_run.id),
                    task_retry=True,
                )

                # Use the existing test run (this handles task retries)
                test_run = existing_test_run
            else:
                # Create a new test run for this task execution
                self.log_with_context(
                    "info",
                    f"Creating new test run for task {self.request.id}",
                    test_configuration_id=test_configuration_id,
                )
                test_run = create_test_run(
                    db, test_config, {"id": self.request.id}, current_user_id=user_id
                )

                # CRITICAL: Explicitly commit the test run creation before launching parallel tasks
                # This ensures the test run exists in the database before async tasks try to reference it
                db.commit()
                self.log_with_context("debug", f"Test run {test_run.id} committed to database")

            # Execute test cases in parallel
            result = execute_test_cases(db, test_config, test_run)

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

        # Attempt to update test run status to failed using utility
        # Use task ID to find the specific test run created by this task
        with get_db_with_tenant_variables(org_id or "", user_id or "") as db:
            test_run = get_test_run_by_task_id(db, self.request.id, org_id)
            if test_run:
                success = update_test_run_with_error(db, test_run, str(e))
                if not success:
                    self.log_with_context("error", "Failed to update test run status")

        # Check if we've exceeded max_retries (from BaseTask)
        if retries >= self.max_retries:
            self.log_with_context(
                "warning", "Maximum retries reached, giving up", max_retries=self.max_retries
            )
            # Raise a specific error that should not trigger retry
            raise TestExecutionError(f"Failed after {self.max_retries} retries: {str(e)}")

        # Re-raise the original error to trigger retry behavior from BaseTask
        raise
