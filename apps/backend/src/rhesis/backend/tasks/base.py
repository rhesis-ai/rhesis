from celery import Task
from contextlib import contextmanager
from functools import wraps

from sqlalchemy.orm import Session

from rhesis.backend.app.database import (
    SessionLocal,
    set_tenant,
    maintain_tenant_context,
)


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


class BaseTask(Task):
    """Base task class with retry settings and tenant context management."""

    # Automatically retry on exceptions except TestExecutionError
    autoretry_for = (Exception,)
    retry_for_unexpected_only = True  # Only retry for unexpected exceptions

    # Maximum number of retries
    max_retries = 3

    # Exponential backoff: 1min, 5min, 25min
    retry_backoff = True
    retry_backoff_max = 600  # 10 minutes max delay

    # Report started status
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

    def validate_params(self, args, kwargs):
        """Check for organization_id and user_id in headers if not in kwargs."""
        # Headers take precedence, so no need to validate kwargs if they'll be overridden
        headers = self.request.headers if hasattr(self, 'request') else {}
        
        # Only validate kwargs if headers don't contain the necessary context
        if not (headers and 'organization_id' in headers and 'user_id' in headers):
            # Only enforce these if the task has started without headers
            if hasattr(self, 'request') and not (
                'organization_id' in kwargs or 'user_id' in kwargs
            ):
                print(f"Warning: Task {self.name} executed without organization_id and user_id")

    def __call__(self, *args, **kwargs):
        """Execute the task with the given context."""
        # We don't validate here - we do it in before_start when the request is available
        return super().__call__(*args, **kwargs)
        
    def apply_async(self, args=None, kwargs=None, **options):
        """Store org_id and user_id in task context when task is queued."""
        args = args or ()
        kwargs = kwargs or {}
        
        # If organization_id and user_id are in kwargs, add them to headers
        if kwargs and ('organization_id' in kwargs or 'user_id' in kwargs):
            # Create or update task headers with context information
            headers = options.get('headers', {})
            
            if 'organization_id' in kwargs:
                headers['organization_id'] = kwargs.pop('organization_id')
                
            if 'user_id' in kwargs:  
                headers['user_id'] = kwargs.pop('user_id')
                
            options['headers'] = headers
            
        return super().apply_async(args, kwargs, **options)
        
    def on_success(self, retval, task_id, args, kwargs):
        """Log successful task completion with context information."""
        org_id = getattr(self.request, 'organization_id', 'unknown')
        user_id = getattr(self.request, 'user_id', 'unknown')
        
        print(f"Task {self.name}[{task_id}] completed successfully "
              f"for org: {org_id}, user: {user_id}")
        
        return super().on_success(retval, task_id, args, kwargs)
        
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Log failed task with context information."""
        # Import TestExecutionError here to avoid circular imports
        from rhesis.backend.tasks.execution.run import TestExecutionError
        
        org_id = getattr(self.request, 'organization_id', 'unknown')
        user_id = getattr(self.request, 'user_id', 'unknown')
        
        # Don't retry if this is a TestExecutionError
        retries = getattr(self.request, 'retries', 0)
        if isinstance(exc, TestExecutionError) or retries >= self.max_retries:
            print(f"Task {self.name}[{task_id}] permanently failed after {retries} attempts "
                  f"for org: {org_id}, user: {user_id} - Error: {str(exc)}")
        else:
            print(f"Task {self.name}[{task_id}] failed (will retry, attempt {retries}/{self.max_retries}) "
              f"for org: {org_id}, user: {user_id} - Error: {str(exc)}")
        
        return super().on_failure(exc, task_id, args, kwargs, einfo)
        
    def before_start(self, task_id, args, kwargs):
        """Add organization_id and user_id to task request context."""
        # Try to get from kwargs first
        if 'organization_id' in kwargs:
            self.request.organization_id = kwargs.pop('organization_id')
        if 'user_id' in kwargs:  
            self.request.user_id = kwargs.pop('user_id')
            
        # Headers take precedence over kwargs
        headers = getattr(self.request, 'headers', {}) or {}
        if headers:
            if 'organization_id' in headers:
                self.request.organization_id = headers['organization_id']
            if 'user_id' in headers:
                self.request.user_id = headers['user_id']
        
        # Do a soft validation (warning only)
        self.validate_params(args, kwargs)
            
        return super().before_start(task_id, args, kwargs)
