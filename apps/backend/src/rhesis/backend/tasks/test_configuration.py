"""
This module contains the main entry point for test configuration execution,
with detailed implementation in the execution/ directory modules.
"""

from datetime import datetime
from uuid import UUID

from rhesis.backend.app import crud
from rhesis.backend.app.database import get_db_with_tenant_variables
from rhesis.backend.tasks.base import SilentTask
from rhesis.backend.tasks.enums import RunStatus
from rhesis.backend.tasks.execution.config import get_test_configuration
from rhesis.backend.tasks.execution.orchestration import execute_test_cases
from rhesis.backend.tasks.execution.run import (
    TestExecutionError,
    create_test_run,
    update_test_run_status,
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
def execute_test_configuration(self, test_configuration_id: str, test_run_id: str = None):
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
    is_valid, error_msg = validate_task_parameters(test_configuration_id=test_configuration_id)
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
    org_id, user_id = self.get_tenant_context()
    retries = getattr(self.request, "retries", 0)

    self.log_with_context("debug", "Task context retrieved", retries=retries)

    try:
        # Use tenant-aware database session with explicit organization_id and user_id
        with get_db_with_tenant_variables(org_id or "", user_id or "") as db:
            # Get test configuration with tenant context
            test_config = get_test_configuration(db, test_configuration_id, org_id)

            if test_run_id:
                # Test run was pre-created by the API with Queued status
                test_run = crud.get_test_run(db, UUID(test_run_id), organization_id=org_id)
                if test_run is None:
                    raise ValueError(f"Test run {test_run_id} not found")

                # Transition Queued -> Progress and record task_id
                test_run.attributes = test_run.attributes or {}
                test_run.attributes["task_id"] = self.request.id
                test_run.attributes["started_at"] = datetime.utcnow().isoformat()
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

            # Extract re-scoring params from configuration attributes
            config_attrs = test_config.attributes or {}
            reference_test_run_id = config_attrs.get("reference_test_run_id")

            # Execute test cases (parallel or sequential)
            result = execute_test_cases(
                db,
                test_config,
                test_run,
                reference_test_run_id=reference_test_run_id,
            )

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
        with get_db_with_tenant_variables(org_id or "", user_id or "") as db:
            if test_run_id:
                test_run = crud.get_test_run(db, UUID(test_run_id), organization_id=org_id)
            else:
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
