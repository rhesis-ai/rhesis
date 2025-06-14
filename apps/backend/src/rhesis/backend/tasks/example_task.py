from typing import Optional
from uuid import UUID

from rhesis.backend.app import crud
from rhesis.backend.worker import app
from rhesis.backend.tasks.base import BaseTask, with_tenant_context, EmailEnabledTask


@app.task(base=BaseTask, name="rhesis.backend.tasks.process_data", bind=True)
def process_data(self, data: dict):
    """
    Example task that processes data.
    
    This task automatically receives organization_id and user_id in its context
    when launched with task_launcher.
    """
    # Access context using the new utility method
    org_id, user_id = self.get_tenant_context()
    
    self.log_with_context('info', f"Processing data", data_keys=list(data.keys()) if data else [])
    
    result = {"processed": data, "organization_id": org_id, "user_id": user_id}
    return result


@app.task(base=BaseTask, name="rhesis.backend.tasks.echo", bind=True)
def echo(self, message: str):
    """
    Echo task for testing.
    
    This task doesn't use the database, but demonstrates how to access
    context information from the task request.
    """
    # Access context using the new utility method
    org_id, user_id = self.get_tenant_context()
    
    self.log_with_context('info', f"Echo task executed", message_length=len(message))
    return f"Message: {message}, Organization: {org_id}, User: {user_id}"


@app.task(base=BaseTask, name="rhesis.backend.tasks.get_test_set_count", bind=True)
@with_tenant_context
def get_test_set_count(self, db=None):
    """
    Count test sets for the current organization.
    
    This task demonstrates using the tenant context system for database operations.
    The @with_tenant_context decorator automatically:
    1. Creates a database session
    2. Sets the tenant context from the task
    3. Passes the session to the task function
    4. Closes the session when done
    
    All database operations will have the correct tenant context automatically.
    """
    # The db session is automatically injected by the with_tenant_context decorator
    # and already has the correct tenant context set
    
    # Use the crud utility which will respect the tenant context
    test_sets = crud.get_test_sets(db)
    count = len(test_sets)
    
    # Access context using the new utility method
    org_id, user_id = self.get_tenant_context()
    
    self.log_with_context('info', f"Test set count retrieved", test_set_count=count)
    
    return {
        "organization_id": org_id,
        "user_id": user_id,
        "test_set_count": count
    }


@app.task(base=BaseTask, name="rhesis.backend.tasks.get_test_configuration", bind=True)
@with_tenant_context
def get_test_configuration(self, test_configuration_id: str, db=None):
    """
    Get details of a specific test configuration.
    
    This task demonstrates using the tenant context system with parameters.
    The database session is automatically configured with the correct tenant.
    """
    # Convert string ID to UUID
    config_id = UUID(test_configuration_id)
    
    # The crud function will use the properly configured session
    # which has the tenant context already set
    test_config = crud.get_test_configuration(db, test_configuration_id=config_id)
    
    # Access context using the new utility method
    org_id, user_id = self.get_tenant_context()
    
    self.log_with_context('info', f"Test configuration retrieved", 
                         test_configuration_id=test_configuration_id,
                         found=test_config is not None)
    
    return {
        "organization_id": org_id,
        "user_id": user_id,
        "test_configuration": test_config.id if test_config else None,
        "found": test_config is not None
    }


@app.task(base=BaseTask, name="rhesis.backend.tasks.manual_db_example", bind=True)
def manual_db_example(self):
    """
    Example of manually managing the database session in a task.
    
    This demonstrates using get_db_session for cases where you need more
    control over the session lifecycle.
    """
    # Access context using the new utility method
    org_id, user_id = self.get_tenant_context()
    
    results = {}
    
    # Use the context manager to get a properly configured session
    with self.get_db_session() as db:
        # The session already has tenant context set
        test_sets = crud.get_test_sets(db)
        results["test_set_count"] = len(test_sets)
    
    self.log_with_context('info', f"Manual DB example completed", 
                         test_set_count=results.get("test_set_count", 0))
    
    return {
        "organization_id": org_id,
        "user_id": user_id,
        "results": results
    }


@app.task(base=EmailEnabledTask, name="rhesis.backend.tasks.email_notification_test", bind=True)
@with_tenant_context
def email_notification_test(self, test_message: str = "Test message", message: str = None, db=None):
    """
    Test task to verify email notifications are working.
    This task will always succeed to test success notifications.
    
    Accepts both 'test_message' (preferred) and 'message' parameters for compatibility.
    """
    # Use message if test_message is default and message is provided
    if test_message == "Test message" and message is not None:
        test_message = message
    
    self.log_with_context('info', f"Starting email notification test", test_message=test_message)
    
    # Simulate some work
    import time
    time.sleep(2)
    
    self.log_with_context('info', f"Email notification test completed successfully")
    
    return {
        "message": test_message,
        "timestamp": "2024-01-01T00:00:00Z",
        "status": "success"
    }
