from celery import Task
from contextlib import contextmanager
from functools import wraps
from typing import Tuple, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app.database import (
    SessionLocal,
    set_tenant,
    maintain_tenant_context,
)
from rhesis.backend.tasks.enums import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_BACKOFF_MAX
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

    # Maximum number of retries - use centralized constant
    max_retries = DEFAULT_MAX_RETRIES

    # Exponential backoff: 1min, 5min, 25min
    retry_backoff = True
    retry_backoff_max = DEFAULT_RETRY_BACKOFF_MAX

    # Report started status
    track_started = True
    
    def get_tenant_context(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Get tenant context from task request in a consistent way.
        
        Returns:
            Tuple of (organization_id, user_id)
        """
        request = getattr(self, 'request', None)
        if not request:
            return None, None
            
        organization_id = getattr(request, 'organization_id', None)
        user_id = getattr(request, 'user_id', None)
        
        return organization_id, user_id
    
    def log_with_context(self, level: str, message: str, **kwargs):
        """
        Log a message with consistent tenant context information.
        
        Args:
            level: Log level ('info', 'warning', 'error', 'debug')
            message: The message to log
            **kwargs: Additional context to include in the log
        """
        from rhesis.backend.logging.rhesis_logger import logger
        
        org_id, user_id = self.get_tenant_context()
        task_id = getattr(self.request, 'id', 'unknown') if hasattr(self, 'request') else 'unknown'
        
        context_info = {
            'task_id': task_id,
            'organization_id': org_id or 'unknown',
            'user_id': user_id or 'unknown',
            **kwargs
        }
        
        # Format message with context
        context_str = ', '.join(f"{k}={v}" for k, v in context_info.items())
        formatted_message = f"{message} [{context_str}]"
        
        # Log at the appropriate level
        log_method = getattr(logger, level.lower(), logger.info)
        log_method(formatted_message)
    
    @contextmanager
    def get_db_session(self):
        """Get a database session with the proper tenant context."""
        db = SessionLocal()
        try:
            # Start with a clean session
            db.expire_all()
            
            # Get task context
            org_id, user_id = self.get_tenant_context()
            
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
        
    def on_success(self, retval, task_id, args, kwargs):
        """Log successful task completion with context information."""
        self.log_with_context('info', f"Task completed successfully", task_result_type=type(retval).__name__)
        return super().on_success(retval, task_id, args, kwargs)
        
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Log failed task with context information."""
        # Import TestExecutionError here to avoid circular imports
        from rhesis.backend.tasks.execution.run import TestExecutionError
        
        retries = getattr(self.request, 'retries', 0)
        
        # Don't retry if this is a TestExecutionError
        if isinstance(exc, TestExecutionError) or retries >= self.max_retries:
            self.log_with_context('error', 
                f"Task permanently failed after {retries} attempts", 
                error=str(exc), 
                exception_type=type(exc).__name__
            )
        else:
            self.log_with_context('warning',
                f"Task failed (will retry, attempt {retries}/{self.max_retries})", 
                error=str(exc),
                exception_type=type(exc).__name__
            )
        
        return super().on_failure(exc, task_id, args, kwargs, einfo)
        
    def before_start(self, task_id, args, kwargs):
        """Add organization_id and user_id to task request context."""
        # Move context from kwargs to request object
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
