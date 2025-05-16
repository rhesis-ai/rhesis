# Background Tasks

## Overview

The Rhesis backend uses Celery to handle asynchronous background tasks. This allows the API to offload time-consuming operations and improve responsiveness. The task processing system is designed to be scalable and fault-tolerant.

## Celery Configuration

The Celery application is configured in `celery_app.py`:

```python
import os
from celery import Celery
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Create the Celery app
app = Celery("rhesis")

# Configure Celery
app.conf.update(
    broker_url=os.getenv("BROKER_URL"),
    result_backend=os.getenv("CELERY_RESULT_BACKEND"),
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)

# Auto-discover tasks without loading config files
app.autodiscover_tasks(["rhesis.backend.tasks"], force=True)
```

The application uses PostgreSQL as both the broker and result backend:

```
BROKER_URL=sqla+postgresql://celery-user:password@/celery?host=/cloudsql/project-id:region:instance
CELERY_RESULT_BACKEND=db+postgresql://celery-user:password@/celery?host=/cloudsql/project-id:region:instance
```

## Base Task Class

All tasks inherit from a common `BaseTask` class that provides retry logic and error handling:

```python
class BaseTask(Task):
    """Base task class with retry settings."""

    autoretry_for = (Exception,)
    max_retries = 3
    retry_backoff = True
    retry_backoff_max = 600
    retry_jitter = True
```

This configuration ensures that tasks:
- Automatically retry on exceptions
- Use exponential backoff for retries
- Add jitter to retry intervals to prevent thundering herd problems

## Task Organization

Tasks are organized in the `tasks/` directory:

```
tasks/
├── __init__.py
├── api.py
├── base.py
├── example_task.py
├── test_configuration.py
└── test_set.py
```

## Key Tasks

### Test Configuration Execution

The `execute_test_configuration` task runs tests against AI models:

```python
@app.task(base=BaseTask, bind=True)
def execute_test_configuration(self, test_configuration_id: str, organization_id: str = None):
    """Execute a test configuration asynchronously."""
    # Set up database session
    db = SessionLocal()
    try:
        # Set tenant context
        set_tenant(db, organization_id)
        
        # Get the test configuration
        test_configuration = db.query(TestConfiguration).filter(
            TestConfiguration.id == test_configuration_id
        ).first()
        
        if not test_configuration:
            raise ValueError(f"Test configuration {test_configuration_id} not found")
            
        # Execute the test configuration
        # ...implementation details...
        
        return {"status": "completed", "test_configuration_id": test_configuration_id}
    except Exception as e:
        # Log the error
        logger.error(f"Error executing test configuration {test_configuration_id}: {e}")
        raise
    finally:
        # Clean up
        db.close()
```

### Test Set Processing

The `count_test_sets` task processes and analyzes test sets:

```python
@app.task(base=BaseTask, bind=True)
def count_test_sets(self):
    """Count the number of test sets in the database."""
    db = SessionLocal()
    try:
        count = db.query(TestSet).count()
        return count
    finally:
        db.close()
```

## Task Scheduling

Tasks can be scheduled in several ways:

### Direct Invocation

```python
from rhesis.backend.tasks import execute_test_configuration

# Schedule a task to be executed asynchronously
task = execute_test_configuration.delay(test_configuration_id)

# Get the task ID for later reference
task_id = task.id
```

### Scheduled Execution

```python
from rhesis.backend.tasks import execute_test_configuration

# Schedule a task to run after 10 seconds
task = execute_test_configuration.apply_async(
    args=[test_configuration_id],
    countdown=10
)
```

### API Endpoints

Tasks can be triggered through API endpoints:

```python
@router.post("/test-configurations/{test_configuration_id}/execute")
def execute_test_configuration_endpoint(
    test_configuration_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_current_user),
):
    # Get the organization ID from the current user
    organization_id = current_user.get("organization_id")
    
    # Schedule the task
    task = execute_test_configuration.delay(test_configuration_id, organization_id)
    
    # Return the task ID
    return {"task_id": task.id}
```

## Task Monitoring

Task status can be monitored through the Celery result backend:

```python
from rhesis.backend.celery_app import app

def get_task_status(task_id):
    """Get the status of a task."""
    task_result = app.AsyncResult(task_id)
    return {
        "task_id": task_id,
        "status": task_result.status,
        "result": task_result.result if task_result.ready() else None,
    }
```

## Worker Configuration

Celery workers are configured to run in separate processes:

```
celery -A rhesis.backend.celery_app worker --loglevel=info
```

For production, multiple workers can be deployed across different machines for scalability and fault tolerance.

## Error Handling

Tasks include comprehensive error handling:

1. Exceptions are logged with context information
2. Failed tasks are automatically retried with exponential backoff
3. After maximum retries, the error is recorded in the result backend
4. Critical errors can trigger notifications through the logging system 