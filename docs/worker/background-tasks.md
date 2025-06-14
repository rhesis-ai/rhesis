# Worker Tasks and Background Processing

## Overview

The Rhesis backend uses Celery to handle asynchronous background tasks. This allows the API to offload time-consuming operations and improve responsiveness. The task processing system is designed to be scalable, fault-tolerant, and context-aware.

## Celery Configuration

The Celery application is configured in `worker.py`:

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

The application uses Redis as both the broker and result backend with TLS support:

```bash
# Development (local Redis)
BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# Production (Redis with TLS)
BROKER_URL=rediss://:password@redis-host:6378/0?ssl_cert_reqs=CERT_NONE
CELERY_RESULT_BACKEND=rediss://:password@redis-host:6378/1?ssl_cert_reqs=CERT_NONE

# Model API Keys (required for evaluation tasks)
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL_NAME=gemini-1.5-pro
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_API_KEY=your_azure_openai_key
AZURE_OPENAI_DEPLOYMENT_NAME=your-deployment-name
AZURE_OPENAI_API_VERSION=2024-02-01
```

**Note:** The `rediss://` protocol indicates Redis with TLS/SSL encryption. The `ssl_cert_reqs=CERT_NONE` parameter is used when connecting to managed Redis services that use self-signed certificates.

## Base Task Class

All tasks inherit from a `BaseTask` class that provides retry logic, error handling, and most importantly, context awareness for multi-tenant operations:

```python
from celery import Task
from contextlib import contextmanager

from rhesis.backend.app.database import SessionLocal, set_tenant

class BaseTask(Task):
    """Base task class with retry settings and tenant context management."""

    # Retry settings
    autoretry_for = (Exception,)
    max_retries = 3
    retry_backoff = True
    retry_backoff_max = 600  # 10 minutes max delay
    track_started = True
    
    @contextmanager
    def get_db_session(self):
        """Get a database session with the proper tenant context."""
        db = SessionLocal()
        try:
            # Start with a clean session
            db.expire_all()
            
            # Get task context
            request = getattr(self, 'request', None)
            org_id = getattr(request, 'organization_id', None)
            user_id = getattr(request, 'user_id', None)
            
            # Set tenant context if available
            if org_id or user_id:
                set_tenant(db, org_id, user_id)
                
            yield db
        finally:
            db.close()

    def apply_async(self, args=None, kwargs=None, **options):
        """Store org_id and user_id in task context when task is queued."""
        args = args or ()
        kwargs = kwargs or {}
        
        # Extract context from kwargs and store in headers
        if kwargs and ('organization_id' in kwargs or 'user_id' in kwargs):
            headers = options.get('headers', {})
            
            if 'organization_id' in kwargs:
                headers['organization_id'] = kwargs.pop('organization_id')
                
            if 'user_id' in kwargs:  
                headers['user_id'] = kwargs.pop('user_id')
                
            options['headers'] = headers
            
        return super().apply_async(args, kwargs, **options)
        
    def before_start(self, task_id, args, kwargs):
        """Add organization_id and user_id to task request context."""
        # Try to get from kwargs first, then headers (which take precedence)
        if 'organization_id' in kwargs:
            self.request.organization_id = kwargs.pop('organization_id')
        if 'user_id' in kwargs:  
            self.request.user_id = kwargs.pop('user_id')
            
        headers = getattr(self.request, 'headers', {}) or {}
        if headers:
            if 'organization_id' in headers:
                self.request.organization_id = headers['organization_id']
            if 'user_id' in headers:
                self.request.user_id = headers['user_id']
```

This enhanced `BaseTask` ensures that:
- Tasks have access to organization_id and user_id for proper multi-tenant operations
- Context is automatically propagated through the task execution
- Error handling and retry logic are standardized
- Logging and monitoring include context information

## Tenant Context Decorator

A task decorator is provided to automatically handle database sessions with proper tenant context:

```python
from functools import wraps

def with_tenant_context(func):
    """
    Decorator to automatically maintain tenant context in task functions.
    This ensures all database operations use the proper tenant context.
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        # Get task request for context
        request = getattr(self, 'request', None)
        organization_id = getattr(request, 'organization_id', None)
        user_id = getattr(request, 'user_id', None)
        
        # Get a database session
        with self.get_db_session() as db:
            # Set tenant for this session
            if organization_id or user_id:
                set_tenant(db, organization_id, user_id)
            
            # Add db to kwargs and execute the task function
            kwargs['db'] = db
            return func(self, *args, **kwargs)
    
    return wrapper
```

Using this decorator simplifies working with database operations in tasks:

```python
@app.task(base=BaseTask, name="rhesis.backend.tasks.count_test_sets")
@with_tenant_context
def count_test_sets(self, db=None):
    """
    Task that counts total test sets.
    The db parameter is automatically provided with tenant context.
    """
    # Access context from task request
    org_id = getattr(self.request, 'organization_id', 'unknown')
    user_id = getattr(self.request, 'user_id', 'unknown')
    
    # The db session already has tenant context set
    test_sets = crud.get_test_sets(db)
    count = len(test_sets)
    
    return {
        "count": count,
        "organization_id": org_id,
        "user_id": user_id
    }
```

## Task Launcher Utility

A `task_launcher` utility method is provided to easily launch tasks with proper context from FastAPI routes:

```python
def task_launcher(task: Callable, *args: Any, current_user=None, **kwargs: Any):
    """
    Launch a task with proper context from a FastAPI route.
    
    This helper automatically adds organization_id and user_id from current_user
    to the task context, removing the need to pass them explicitly.
    """
    # Add user context if available and not already specified
    if current_user is not None:
        if hasattr(current_user, 'id') and current_user.id is not None:
            kwargs.setdefault('user_id', str(current_user.id))
        
        if hasattr(current_user, 'organization_id') and current_user.organization_id is not None:
            kwargs.setdefault('organization_id', str(current_user.organization_id))
    
    # Launch the task
    return task.delay(*args, **kwargs)
```

## Task Organization

Tasks are organized in the `tasks/` directory:

```
tasks/
├── __init__.py
├── base.py
├── example_task.py
├── test_configuration.py
└── test_set.py
```

## Creating Tasks

When creating a task, you no longer need to explicitly require organization_id and user_id as parameters. The context system handles this automatically:

### Simple Task without Database Access

```python
@app.task(base=BaseTask, name="rhesis.backend.tasks.echo")
def echo(message: str):
    """Echo task for testing context."""
    task = echo.request
    org_id = getattr(task, 'organization_id', 'unknown') 
    user_id = getattr(task, 'user_id', 'unknown')
    
    print(f"Task executed for organization: {org_id}, by user: {user_id}")
    return f"Message: {message}, Organization: {org_id}, User: {user_id}"
```

### Task with Automatic Database Context

```python
@app.task(base=BaseTask, name="rhesis.backend.tasks.get_test_configuration")
@with_tenant_context
def get_test_configuration(test_configuration_id: str, db=None):
    """
    Get a test configuration with proper tenant context.
    
    The @with_tenant_context decorator automatically:
    1. Creates a database session
    2. Sets the tenant context from task headers
    3. Passes the session to the function
    4. Closes the session when done
    """
    # Convert string ID to UUID
    config_id = UUID(test_configuration_id)
    
    # Use existing crud functions with proper tenant context
    test_config = crud.get_test_configuration(db, test_configuration_id=config_id)
    
    return {
        "found": test_config is not None,
        "id": str(test_config.id) if test_config else None
    }
```

### Task with Manual Database Session Control

```python
@app.task(base=BaseTask, name="rhesis.backend.tasks.manual_db_example")
def manual_db_example():
    """Example of manually managing database sessions."""
    results = {}
    
    # Use the context manager to get a properly configured session
    with manual_db_example.get_db_session() as db:
        # The session already has tenant context set
        test_sets = crud.get_test_sets(db)
        results["test_set_count"] = len(test_sets)
    
    return results
```

## Using Tasks in FastAPI Routes

The most common way to launch tasks is from FastAPI route handlers:

```python
from rhesis.backend.tasks import task_launcher, execute_test_configuration

@router.post("/{test_configuration_id}/execute")
def execute_test_configuration_endpoint(
    test_configuration_id: UUID,
    current_user: schemas.User = Depends(require_current_user_or_token)
):
    # Schedule the task with automatic context handling
    result = task_launcher(
        execute_test_configuration, 
        str(test_configuration_id),
        current_user=current_user
    )
    
    # Return the task ID for checking status later
    return {"task_id": result.id}
```

## Worker Configuration

Celery workers are configured with Redis-optimized performance settings:

```dockerfile
# Default Celery configuration optimized for Redis
ENV CELERY_WORKER_CONCURRENCY=8 \
    CELERY_WORKER_PREFETCH_MULTIPLIER=4 \
    CELERY_WORKER_MAX_TASKS_PER_CHILD=1000 \
    CELERY_WORKER_LOGLEVEL=INFO \
    CELERY_WORKER_OPTS=""
```

### Redis-Specific Configuration

The Celery app includes Redis-optimized settings:

```python
app.conf.update(
    # Redis configuration with TLS support
    broker_url=os.getenv("BROKER_URL", "redis://localhost:6379/0"),
    result_backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1"),
    
    # Redis-optimized settings
    result_expires=3600,  # 1 hour - shorter for Redis efficiency
    result_compression="gzip",
    
    # Connection settings for Redis reliability
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    
    # Redis transport options for TLS connections
    broker_transport_options={
        'retry_on_timeout': True,
        'connection_pool_kwargs': {
            'retry_on_timeout': True,
            'socket_connect_timeout': 30,
            'socket_timeout': 30,
        }
    },
    
    result_backend_transport_options={
        'retry_on_timeout': True,
        'connection_pool_kwargs': {
            'retry_on_timeout': True,
            'socket_connect_timeout': 30,
            'socket_timeout': 30,
        }
    },
)
```

The worker startup script applies these configurations:

```bash
# Start Celery worker with Redis-optimized settings
celery -A rhesis.backend.worker.app worker \
    --queues=celery,execution \
    --loglevel=${CELERY_WORKER_LOGLEVEL:-INFO} \
    --concurrency=${CELERY_WORKER_CONCURRENCY:-8} \
    --prefetch-multiplier=${CELERY_WORKER_PREFETCH_MULTIPLIER:-4} \
    --max-tasks-per-child=${CELERY_WORKER_MAX_TASKS_PER_CHILD:-1000} \
    ${CELERY_WORKER_OPTS}
```

Optional monitoring is available through Flower:

```bash
# Enable Flower monitoring
docker run -e ENABLE_FLOWER=yes -p 5555:5555 your-worker-image
```

## Task Monitoring

Task status can be monitored through several interfaces:

### API Endpoint

```python
@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Get the status of a task."""
    result = AsyncResult(task_id, app=celery_app)
    return {
        "task_id": task_id,
        "status": result.status,
        "result": result.result if result.ready() else None,
        "error": str(result.error) if result.failed() else None,
    }
```

### Flower Dashboard

Access the Flower web UI at `http://localhost:5555` when enabled.

## Error Handling

The enhanced BaseTask provides improved error handling:

1. Exceptions are logged with tenant context information
2. Failed tasks are automatically retried with exponential backoff
3. After maximum retries, the error is recorded in the result backend
4. Both success and failure callbacks include context information
5. Task execution time and other metrics are tracked automatically 

## Troubleshooting

For detailed information about troubleshooting common worker issues, including:

- Dealing with stuck tasks and chord_unlock zombies
- Fixing tenant context errors
- Connection problems with the broker
- Task execution failures

Please refer to the [Worker Troubleshooting Guide](troubleshooting.md).

## Task Monitoring

Task status can be monitored through several interfaces: 