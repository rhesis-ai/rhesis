from datetime import datetime
from typing import Dict
from uuid import UUID

from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.app.models.test_configuration import TestConfiguration
from rhesis.backend.app.models.test_run import TestRun
from rhesis.backend.app.utils.crud_utils import get_or_create_status
from rhesis.backend.tasks.enums import RunStatus


class TestExecutionError(Exception):
    """Exception raised for errors during test execution."""

    pass


def create_test_run(session: Session, test_config: TestConfiguration, task_info: Dict) -> TestRun:
    """Create a new test run with initial status and metadata."""
    initial_status = get_or_create_status(session, RunStatus.PROGRESS.value, "TestRun")

    # Create the run with proper tenant context via the crud utility
    test_run_data = {
        "test_configuration_id": test_config.id,
        "user_id": test_config.user_id,
        "organization_id": test_config.organization_id,
        "status_id": initial_status.id,
        "attributes": {
            "started_at": datetime.utcnow().isoformat(),
            "configuration_id": str(test_config.id),
            "task_id": task_info.get("id"),
            "task_state": "PROGRESS",
        },
    }
    
    test_run = crud.create_test_run(session, crud.schemas.TestRunCreate(**test_run_data))
    return test_run


def update_test_run_status(
    session: Session, test_run: TestRun, status_name: str, error: str = None
) -> None:
    """Update the status of a test run."""
    new_status = get_or_create_status(session, status_name, "TestRun")
    
    # Build update data
    update_data = {"status_id": new_status.id}
    
    # Update attributes in memory before saving
    if error:
        test_run.attributes["error"] = error
        test_run.attributes["status"] = RunStatus.FAILED.value
    else:
        test_run.attributes["status"] = status_name
    
    test_run.attributes["updated_at"] = datetime.utcnow().isoformat()
    update_data["attributes"] = test_run.attributes
    
    # Use crud update operation
    crud.update_test_run(session, test_run.id, crud.schemas.TestRunUpdate(**update_data)) 