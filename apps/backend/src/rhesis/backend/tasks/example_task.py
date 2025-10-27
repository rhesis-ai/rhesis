"""
Example task execution with various features and patterns.

This module demonstrates how to use the task system, including:
- Basic task execution
- Tenant context handling
- Email notifications
- Error handling and retries
- NEW: Sequential vs Parallel execution modes
"""

from datetime import datetime
from typing import Any, Dict
from uuid import UUID

from rhesis.backend.app import crud
from rhesis.backend.app.database import get_db, get_db_with_tenant_variables
from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.notifications.email.template_service import EmailTemplate
from rhesis.backend.tasks.base import (
    BaseTask,
    email_notification,
)
from rhesis.backend.tasks.enums import ExecutionMode
from rhesis.backend.tasks.execution.modes import (
    get_execution_mode,
    get_mode_description,
    set_execution_mode,
)
from rhesis.backend.worker import app


@app.task(
    base=BaseTask,
    name="rhesis.backend.tasks.process_data",
    bind=True,
    display_name="Data Processing",
)
def process_data(self, data: dict):
    """
    Example task that processes data.

    This task automatically receives organization_id and user_id in its context
    when launched with task_launcher.
    """
    # Access context using the new utility method
    org_id, user_id = self.get_tenant_context()

    self.log_with_context("info", "Processing data", data_keys=list(data.keys()) if data else [])

    result = {"processed": data, "organization_id": org_id, "user_id": user_id}
    return result


@app.task(base=BaseTask, name="rhesis.backend.tasks.echo", bind=True, display_name="Echo Test")
def echo(self, message: str):
    """
    Echo task for testing.

    This task doesn't use the database, but demonstrates how to access
    context information from the task request.
    """
    # Access context using the new utility method
    org_id, user_id = self.get_tenant_context()

    self.log_with_context("info", "Echo task executed", message_length=len(message))
    return f"Message: {message}, Organization: {org_id}, User: {user_id}"


@app.task(
    base=BaseTask,
    name="rhesis.backend.tasks.get_test_set_count",
    bind=True,
    display_name="Test Set Count",
)
# with_tenant_context decorator removed - tenant context now passed directly
def get_test_set_count(self):
    """
    Count test sets for the current organization.

    Demonstrates using the tenant context system for database operations.
    Uses get_db_with_tenant_variables for explicit tenant context.
    """
    # Access context using the new utility method
    org_id, user_id = self.get_tenant_context()

    # Use tenant-aware database session with explicit organization_id and user_id
    with get_db_with_tenant_variables(org_id or "", user_id or "") as db:
        # Use the crud utility which will respect the tenant context
        test_sets = crud.get_test_sets(db, organization_id=org_id, user_id=user_id)
        count = len(test_sets)

    self.log_with_context("info", "Test set count retrieved", test_set_count=count)

    return {"organization_id": org_id, "user_id": user_id, "test_set_count": count}


@app.task(
    base=BaseTask,
    name="rhesis.backend.tasks.get_test_configuration",
    bind=True,
    display_name="Test Configuration Retrieval",
)
# with_tenant_context decorator removed - tenant context now passed directly
def get_test_configuration(self, test_configuration_id: str):
    """
    Get details of a specific test configuration.

    Demonstrates using the tenant context system with parameters.
    Uses get_db_with_tenant_variables for explicit tenant context.
    """
    # Access context using the new utility method
    org_id, user_id = self.get_tenant_context()

    # Convert string ID to UUID
    config_id = UUID(test_configuration_id)

    # Use tenant-aware database session with explicit organization_id and user_id
    with get_db_with_tenant_variables(org_id or "", user_id or "") as db:
        # The crud function will use the properly configured session
        # which has the tenant context already set
        test_config = crud.get_test_configuration(
            db, test_configuration_id=config_id, organization_id=org_id, user_id=user_id
        )

    self.log_with_context(
        "info",
        "Test configuration retrieved",
        test_configuration_id=test_configuration_id,
        found=test_config is not None,
    )

    return {
        "organization_id": org_id,
        "user_id": user_id,
        "test_configuration": test_config.id if test_config else None,
        "found": test_config is not None,
    }


@app.task(
    base=BaseTask,
    name="rhesis.backend.tasks.manual_db_example",
    bind=True,
    display_name="Database Example",
)
def manual_db_example(self):
    """
    Example of manually managing the database session in a task.

    This demonstrates using get_db_session for cases where you need more
    control over the session lifecycle.
    """
    # Access context using the new utility method
    org_id, user_id = self.get_tenant_context()

    results = {}

    # Use tenant-aware database session with explicit organization_id and user_id
    with get_db_with_tenant_variables(org_id or "", user_id or "") as db:
        # The session already has tenant context set
        test_sets = crud.get_test_sets(db, organization_id=org_id, user_id=user_id)
        results["test_set_count"] = len(test_sets)

    self.log_with_context(
        "info", "Manual DB example completed", test_set_count=results.get("test_set_count", 0)
    )

    return {"organization_id": org_id, "user_id": user_id, "results": results}


@email_notification(
    template=EmailTemplate.TASK_COMPLETION,
    subject_template="Test Task Complete: {task_name} - {status}",
)
@app.task(
    base=BaseTask,
    name="rhesis.backend.tasks.email_notification_test",
    bind=True,
    display_name="Email Notification Test",
)
# with_tenant_context decorator removed - tenant context now passed directly
def email_notification_test(self, test_message: str = "Test message", message: str = None):
    """
    Test task to verify email notifications are working.
    This task will always succeed to test success notifications.

    Accepts both 'test_message' (preferred) and 'message' parameters for compatibility.
    """
    # Use message if test_message is default and message is provided
    if test_message == "Test message" and message is not None:
        test_message = message

    self.log_with_context("info", "Starting email notification test", test_message=test_message)

    # Simulate some work
    import time

    time.sleep(2)

    self.log_with_context("info", "Email notification test completed successfully")

    return {"message": test_message, "timestamp": "2024-01-01T00:00:00Z", "status": "success"}


@app.task(base=BaseTask, bind=True, display_name="Example Task")
# with_tenant_context decorator removed - tenant context now passed directly
def example_task(self, name: str, delay_seconds: int = 5):
    """
    Example task that demonstrates basic functionality.

    Args:
        name: Name for the task execution
        delay_seconds: How long to simulate work
        db: Database session (injected by decorator)
    """
    self.log_with_context("info", "Starting example task", task_name=name)

    # Simulate some work
    import time

    time.sleep(delay_seconds)

    self.log_with_context("info", "Example task completed", task_name=name, duration=delay_seconds)

    return {
        "name": name,
        "duration": delay_seconds,
        "completed_at": datetime.utcnow().isoformat(),
        "message": f"Task '{name}' completed successfully",
    }


@app.task(base=BaseTask, bind=True, display_name="Test Configuration Mode Example")
# with_tenant_context decorator removed - tenant context now passed directly
def example_execution_mode_task(self, test_config_id: str) -> Dict[str, Any]:
    """
    Example task that demonstrates execution mode handling.

    This shows how to:
    1. Check the execution mode of a test configuration
    2. Get a description of the execution mode
    3. Potentially modify execution mode (for admin tasks)

    Args:
        test_config_id: Test configuration UUID
        db: Database session (injected by decorator)
    """
    self.log_with_context(
        "info", "Checking execution mode for test config", test_config_id=test_config_id
    )

    # Access context using the new utility method
    org_id, user_id = self.get_tenant_context()

    try:
        # Get test configuration
        from rhesis.backend.tasks.utils import safe_uuid_convert

        test_config_uuid = safe_uuid_convert(test_config_id)
        if not test_config_uuid:
            raise ValueError(f"Invalid test configuration ID: {test_config_id}")

        # Use tenant-aware database session with explicit organization_id and user_id
        with get_db_with_tenant_variables(org_id or "", user_id or "") as db:
            test_config = crud.get_test_configuration(
                db, test_config_uuid, organization_id=org_id, user_id=user_id
            )
            if not test_config:
                raise ValueError(f"Test configuration not found: {test_config_id}")

        # Get current execution mode
        execution_mode = get_execution_mode(test_config)
        description = get_mode_description(execution_mode)

        self.log_with_context(
            "info",
            "Test configuration execution mode",
            execution_mode=execution_mode.value,
            test_config_id=test_config_id,
        )

        # Example: Log some statistics about the test configuration
        test_set_id = str(test_config.test_set_id) if test_config.test_set_id else None
        endpoint_id = str(test_config.endpoint_id) if test_config.endpoint_id else None

        result = {
            "test_config_id": test_config_id,
            "execution_mode": execution_mode.value,
            "execution_mode_description": description,
            "test_set_id": test_set_id,
            "endpoint_id": endpoint_id,
            "attributes": test_config.attributes or {},
            "checked_at": datetime.utcnow().isoformat(),
        }

        self.log_with_context(
            "info",
            "Execution mode check completed successfully",
            test_config_id=test_config_id,
            execution_mode=execution_mode.value,
        )

        return result

    except Exception as e:
        self.log_with_context(
            "error", "Error checking execution mode", test_config_id=test_config_id, error=str(e)
        )
        raise


def example_set_execution_mode(test_config_id: str, execution_mode: str) -> bool:
    """
    Example function showing how to programmatically set execution mode.

    NOTE: This is not a Celery task - it's a utility function that could be
    called from an admin interface or management command.

    Args:
        test_config_id: Test configuration UUID
        execution_mode: "Sequential" or "Parallel"

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Validate execution mode
        ExecutionMode(execution_mode)

        with get_db() as db:
            # Set the execution mode
            success = set_execution_mode(
                db,
                test_config_id,
                ExecutionMode(execution_mode),
                organization_id=None,
                user_id=None,
            )

            if success:
                logger.info(
                    f"Successfully set execution mode to {execution_mode} for test config {test_config_id}"
                )
                return True
            else:
                logger.error(f"Failed to set execution mode for test config {test_config_id}")
                return False

    except ValueError as e:
        logger.error(f"Invalid execution mode '{execution_mode}': {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Error setting execution mode: {str(e)}")
        return False


# Example usage documentation
"""
EXECUTION MODE USAGE EXAMPLES:

1. Setting execution mode in test configuration attributes:
   {
     "execution_mode": "Sequential"  # or "Parallel"
   }

2. Checking execution mode programmatically:
   from rhesis.backend.tasks.execution.modes import get_execution_mode
   mode = get_execution_mode(test_config)

3. Setting execution mode programmatically:
   from rhesis.backend.tasks.execution.modes import set_execution_mode
   from rhesis.backend.tasks.enums import ExecutionMode
   success = set_execution_mode(db, test_config_id, ExecutionMode.SEQUENTIAL)

4. Getting mode description:
   from rhesis.backend.tasks.execution.modes import get_mode_description
   desc = get_mode_description(ExecutionMode.SEQUENTIAL)

WHEN TO USE EACH MODE:

Sequential Mode:
- When testing endpoints that can't handle high concurrent load
- When tests have dependencies or need to run in a specific order
- When debugging test execution issues
- For endpoints with rate limiting

Parallel Mode (Default):
- When endpoints can handle concurrent requests
- When tests are independent of each other
- When you need faster test execution
- For scalable endpoints without rate limits

The system defaults to Parallel mode if no execution_mode is specified.
"""
