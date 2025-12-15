import { CodeBlock } from '@/components/CodeBlock'

# Worker Architecture and Dependencies

This document explains the relationships and dependencies between the Rhesis worker system, the backend API, and the SDK components.

## Component Relationships

The Rhesis platform consists of several interrelated components:

```
┌───────────┐     ┌───────────┐     ┌───────────┐
│           │     │           │     │           │
│  Backend  │────▶│   Broker  │────▶│   Worker  │
│    API    │     │           │     │           │
│           │     │           │     │           │
└───────────┘     └───────────┘     └───────────┘
      │                                   │
      │                                   │
      │                                   │
      ▼                                   ▼
┌───────────┐                       ┌───────────┐
│           │                       │           │
│  Database │◀─────────────────────▶│    SDK    │
│           │                       │           │
└───────────┘                       └───────────┘
```

## Backend-Worker Interdependencies

### How Tasks Flow Through the System

1. **Backend API**: Endpoints receive client requests and enqueue asynchronous tasks
2. **Broker**: Redis-based queue stores pending tasks (with TLS support)
3. **Worker**: Processes tasks from the queue and executes business logic
4. **Database**: Shared between backend and worker for storing and retrieving application data
5. **SDK**: Provides shared utilities and models used by both components

### Code Dependencies

The worker depends on the backend code in several ways:

1. **Shared Models**: The worker needs access to the same data models defined in the backend
2. **Database Access**: Worker tasks use the same database connection/ORM layer as the backend
3. **Business Logic**: Tasks often execute backend business logic in an asynchronous context
4. **Context Management**: The worker needs to maintain the same multi-tenant context system

Example import hierarchy:

```python
# In a worker task
from rhesis.backend.app import models, crud    # Backend models and database operations
from rhesis.backend.app.database import SessionLocal, set_tenant  # Backend database utilities
from rhesis.backend.tasks.base import BaseTask # Worker-specific task base class
from rhesis.sdk import client                  # Shared SDK components
```

### SDK Dependencies

Both the worker and backend depend on the Rhesis SDK for:

1. **Client Libraries**: API clients for external services (e.g., LLM providers)
2. **Shared Utilities**: Common functions used by both backend and worker
3. **Type Definitions**: Shared type definitions and interfaces
4. **Configuration Management**: Loading and accessing configuration

## Deployment Considerations

### Package Structure

When deploying the worker, it must include:

1. The entire `rhesis.backend` package
2. The `rhesis.sdk` package
3. Worker-specific code (`rhesis.backend.tasks` and `rhesis.backend.worker`)

### Environment Configuration

The worker requires the same environment variables as the backend, plus additional worker-specific settings:

```
# Backend variables also needed by worker
DATABASE_URL=postgresql://user:password@host/dbname
TENANT_ENABLED=true
LOG_LEVEL=INFO

# Worker-specific variables
BROKER_URL=rediss://:password@redis-host:6378/0?ssl_cert_reqs=CERT_NONE
CELERY_RESULT_BACKEND=rediss://:password@redis-host:6378/1?ssl_cert_reqs=CERT_NONE
CELERY_WORKER_CONCURRENCY=8
CELERY_WORKER_PREFETCH_MULTIPLIER=4
```

### Development Workflow

When developing tasks, you need to:

1. Write code in the backend repository
2. Ensure both backend and worker containers have access to the latest code
3. Test tasks using both API-triggered execution and direct worker execution

## Managing Circular Dependencies

One challenge in the worker-backend relationship is avoiding circular dependencies. The system follows these patterns:

1. Worker tasks can import backend modules
2. Backend modules should not directly import worker tasks (use dynamic imports if needed)
3. Shared dependencies go in the SDK package
4. Base task classes, task organization, and worker configuration belong in `rhesis.backend.tasks`

## Task Context and State

Because the worker executes backend code asynchronously:

1. The tenant context (organization/user IDs) must be explicitly passed to tasks
2. Database sessions must be properly managed (opened and closed)
3. Any state or context that would normally be available in an API request must be reconstructed

This is handled through:

```python
# In the backend API
from rhesis.backend.tasks import task_launcher

@router.post("/execute")
def execute_endpoint(current_user: User = Depends(get_current_user)):
    # Launch task with context
    result = task_launcher(
        my_task,
        arg1,
        arg2,
        current_user=current_user  # This automatically adds org_id and user_id
    )
    return {"task_id": result.id}

# In the worker
@app.task(base=BaseTask)
@with_tenant_context
def my_task(self, arg1, arg2, db=None):
    # Access context
    org_id = getattr(self.request, 'organization_id', None)
    user_id = getattr(self.request, 'user_id', None)

    # Use backend functionality with proper context
    result = backend_function(db, arg1, arg2)
    return result
```
