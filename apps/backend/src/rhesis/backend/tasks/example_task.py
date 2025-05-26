from typing import Optional
from uuid import UUID

from rhesis.backend.app import crud
from rhesis.backend.worker import app
from rhesis.backend.tasks.base import BaseTask, with_tenant_context


@app.task(base=BaseTask, name="rhesis.backend.tasks.process_data")
def process_data(data: dict):
    """
    Example task that processes data.
    
    This task automatically receives organization_id and user_id in its context
    when launched with task_launcher.
    """
    # Access the task instance to get the request object with context
    task = process_data.request
    
    # Access context values from the request
    org_id = getattr(task, 'organization_id', 'unknown')
    user_id = getattr(task, 'user_id', 'unknown')
    
    print(f"Processing data: {data}")
    print(f"Organization from context: {org_id}")
    print(f"User from context: {user_id}")
    
    result = {"processed": data, "organization_id": org_id, "user_id": user_id}
    return result


@app.task(base=BaseTask, name="rhesis.backend.tasks.echo")
def echo(message: str):
    """
    Echo task for testing.
    
    This task doesn't use the database, but demonstrates how to access
    context information from the task request.
    """
    # Access context directly from the current task's request object
    task = echo.request
    org_id = getattr(task, 'organization_id', 'unknown') 
    user_id = getattr(task, 'user_id', 'unknown')
    
    print(f"Task executed for organization: {org_id}, by user: {user_id}")
    return f"Message: {message}, Organization: {org_id}, User: {user_id}"


@app.task(base=BaseTask, name="rhesis.backend.tasks.get_test_set_count")
@with_tenant_context
def get_test_set_count(db=None):
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
    
    # Access context from task request
    task = get_test_set_count.request
    org_id = getattr(task, 'organization_id', 'unknown')
    user_id = getattr(task, 'user_id', 'unknown')
    
    return {
        "organization_id": org_id,
        "user_id": user_id,
        "test_set_count": count
    }


@app.task(base=BaseTask, name="rhesis.backend.tasks.get_test_configuration")
@with_tenant_context
def get_test_configuration(test_configuration_id: str, db=None):
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
    
    # Access context from task request
    task = get_test_configuration.request
    org_id = getattr(task, 'organization_id', 'unknown')
    user_id = getattr(task, 'user_id', 'unknown')
    
    return {
        "organization_id": org_id,
        "user_id": user_id,
        "test_configuration": test_config.id if test_config else None,
        "found": test_config is not None
    }


@app.task(base=BaseTask, name="rhesis.backend.tasks.manual_db_example")
def manual_db_example():
    """
    Example of manually managing the database session in a task.
    
    This demonstrates using get_db_session for cases where you need more
    control over the session lifecycle.
    """
    # Access context from task request
    task = manual_db_example.request
    org_id = getattr(task, 'organization_id', 'unknown')
    user_id = getattr(task, 'user_id', 'unknown')
    
    results = {}
    
    # Use the context manager to get a properly configured session
    with manual_db_example.get_db_session() as db:
        # The session already has tenant context set
        test_sets = crud.get_test_sets(db)
        results["test_set_count"] = len(test_sets)
    
    return {
        "organization_id": org_id,
        "user_id": user_id,
        "results": results
    }
