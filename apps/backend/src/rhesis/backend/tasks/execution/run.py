from datetime import datetime
from typing import Dict

from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.app.models.test_configuration import TestConfiguration
from rhesis.backend.app.models.test_run import TestRun
from rhesis.backend.app.utils.crud_utils import get_or_create_status
from rhesis.backend.tasks.enums import RunStatus


class TestExecutionError(Exception):
    """Exception raised for errors during test execution."""

    pass


def create_test_run(
    session: Session, test_config: TestConfiguration, task_info: Dict, current_user_id: str = None
) -> TestRun:
    """Create a new test run with initial status and metadata."""
    initial_status = get_or_create_status(
        session,
        RunStatus.PROGRESS.value,
        "TestRun",
        organization_id=str(test_config.organization_id),
    )

    # Create the run with proper tenant context via the crud utility
    # Use current_user_id if provided (for re-runs), otherwise fall back to test_config.user_id
    executor_user_id = current_user_id if current_user_id else test_config.user_id

    test_run_data = {
        "test_configuration_id": test_config.id,
        "user_id": executor_user_id,
        "organization_id": test_config.organization_id,
        "status_id": initial_status.id,
        "attributes": {
            "started_at": datetime.utcnow().isoformat(),
            "configuration_id": str(test_config.id),
            "task_id": task_info.get("id"),
            "task_state": RunStatus.PROGRESS.value,
        },
    }

    test_run = crud.create_test_run(
        session,
        crud.schemas.TestRunCreate(**test_run_data),
        organization_id=str(test_config.organization_id) if test_config.organization_id else None,
        user_id=str(executor_user_id) if executor_user_id else None,
    )
    return test_run


def update_test_run_status(
    session: Session, test_run: TestRun, status_name: str, error: str = None
) -> None:
    """
    Update the status of a test run.

    Args:
        session: Database session
        test_run: TestRun instance to update
        status_name: New status name (should match RunStatus enum values)
        error: Optional error message if the run failed
    """
    # Get the appropriate status record
    new_status = get_or_create_status(
        session, status_name, "TestRun", organization_id=str(test_run.organization_id)
    )

    # Build update data
    update_data = {"status_id": new_status.id}

    # Update attributes in memory before saving
    if error:
        test_run.attributes["error"] = error
        test_run.attributes["status"] = RunStatus.FAILED.value
        test_run.attributes["task_state"] = RunStatus.FAILED.value
    else:
        # Map the status name to the corresponding RunStatus enum value
        if status_name == RunStatus.COMPLETED.value:
            test_run.attributes["task_state"] = RunStatus.COMPLETED.value
        elif status_name == RunStatus.FAILED.value:
            test_run.attributes["task_state"] = RunStatus.FAILED.value
        elif status_name == RunStatus.PARTIAL.value:
            test_run.attributes["task_state"] = RunStatus.PARTIAL.value
        elif status_name == RunStatus.PROGRESS.value:
            test_run.attributes["task_state"] = RunStatus.PROGRESS.value

        # Update the status attribute consistently
        test_run.attributes["status"] = status_name

    # Always update the timestamp
    test_run.attributes["updated_at"] = datetime.utcnow().isoformat()

    # If this is a final status (not Progress), add completed_at if not already present
    # This preserves the completed_at set by collect_results while ensuring it gets set
    # if update_test_run_status is called directly
    if status_name != RunStatus.PROGRESS.value and "completed_at" not in test_run.attributes:
        test_run.attributes["completed_at"] = datetime.utcnow().isoformat()

    update_data["attributes"] = test_run.attributes

    # Use crud update operation
    crud.update_test_run(
        session,
        test_run.id,
        crud.schemas.TestRunUpdate(**update_data),
        organization_id=str(test_run.organization_id) if test_run.organization_id else None,
        user_id=str(test_run.user_id) if test_run.user_id else None,
    )
