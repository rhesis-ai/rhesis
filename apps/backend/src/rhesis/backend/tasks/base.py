import os
from contextlib import contextmanager
from datetime import datetime
from typing import Optional, Tuple

from celery import Task

from rhesis.backend.app.database import (
    get_db_with_tenant_variables,
)
from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.tasks.enums import DEFAULT_MAX_RETRIES, DEFAULT_RETRY_BACKOFF_MAX

# Task database sessions automatically set PostgreSQL session variables for RLS
# Use self.get_db_session() for tenant-aware database operations


def email_notification(template=None, subject_template=None):
    """
    Decorator to configure email notifications for task completion.

    Args:
        template: EmailTemplate enum value to use for the email
        subject_template: Template string for the email subject (optional)

    Usage:
        @email_notification(template=EmailTemplate.TEST_EXECUTION_SUMMARY)
        @app.task(base=BaseTask, bind=True)
        def my_task(self, ...):
            ...
    """

    def decorator(task_func):
        # Store email configuration on the task function
        task_func._email_template = template
        task_func._email_subject_template = subject_template
        return task_func

    return decorator


class BaseTask(Task):
    """Base task class with tenant context, logging, retry logic, and email notifications."""

    # Default values for all tasks
    max_retries = 3
    default_retry_delay = 10
    send_email_notification = False  # Default: no emails
    send_default_completion_email = True  # New flag: whether to send default completion email

    def __init__(self):
        super().__init__()

    def get_display_name(self) -> str:
        """Get the user-friendly display name for this task."""
        # Check if display_name is set in task options (from decorator)
        if hasattr(self, "display_name") and self.display_name:
            return self.display_name
        # Fall back to task name or class name
        return getattr(self, "name", self.__class__.__name__)

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
        request = getattr(self, "request", None)
        if not request:
            return None, None

        organization_id = getattr(request, "organization_id", None)
        user_id = getattr(request, "user_id", None)

        return organization_id, user_id

    def log_with_context(self, level: str, message: str, **kwargs):
        """
        Log a message with consistent tenant context information.

        Args:
            level: Log level ('info', 'warning', 'error', 'debug')
            message: The message to log
            **kwargs: Additional context to include in the log
        """
        organization_id, user_id = self.get_tenant_context()
        task_id = getattr(self.request, "id", "unknown") if hasattr(self, "request") else "unknown"

        context_info = {
            "task_id": task_id,
            "organization_id": organization_id or "unknown",
            "user_id": user_id or "unknown",
            **kwargs,
        }

        # Format message with context
        context_str = ", ".join(f"{k}={v}" for k, v in context_info.items())
        formatted_message = f"{message} [{context_str}]"

        # Log at the appropriate level
        log_method = getattr(logger, level.lower(), logger.info)
        log_method(formatted_message)

    @contextmanager
    def get_db_session(self):
        """
        Get a database session with tenant context automatically set.

        Automatically sets PostgreSQL session variables for RLS using the same
        centralized logic as the router dependencies.
        """
        organization_id, user_id = self.get_tenant_context()

        with get_db_with_tenant_variables(organization_id or "", user_id or "") as db:
            yield db

    def validate_params(self, args, kwargs):
        """Check for organization_id and user_id in headers if not in kwargs."""
        # Headers take precedence, so no need to validate kwargs if they'll be overridden
        headers = self.request.headers if hasattr(self, "request") else {}

        # Only validate kwargs if headers don't contain the necessary context
        if not (headers and "organization_id" in headers and "user_id" in headers):
            # Only enforce these if the task has started without headers
            if hasattr(self, "request") and not (
                "organization_id" in kwargs or "user_id" in kwargs
            ):
                print(f"Warning: Task {self.name} executed without organization_id and user_id")

    def __call__(self, *args, **kwargs):
        """Execute the task with the given context."""
        # We don't validate here - we do it in before_start when the request is available
        return super().__call__(*args, **kwargs)

    def on_success(self, retval, task_id, args, kwargs):
        """Log successful task completion with context information."""
        self.log_with_context(
            "info", "Task completed successfully", task_result_type=type(retval).__name__
        )

        # Send email notification for successful completion if enabled
        if self.send_email_notification:
            try:
                self.log_with_context("debug", "Attempting to send success email notification")
                email_kwargs = {}

                # If task returns a dict, pass all the data to the email template
                if isinstance(retval, dict):
                    # Filter out parameters that conflict with method signature
                    filtered_retval = {
                        k: v for k, v in retval.items() if k not in ["status", "error_message"]
                    }
                    email_kwargs.update(filtered_retval)
                    self.log_with_context(
                        "debug",
                        f"Passing {len(filtered_retval)} variables from task result to email template",
                    )

                self._send_task_completion_email("success", **email_kwargs)
            except Exception as e:
                # Never let email failures break task completion
                self.log_with_context(
                    "error",
                    "Email notification failed in on_success",
                    error=str(e),
                    exception_type=type(e).__name__,
                )
        else:
            self.log_with_context("debug", "Email notification disabled for this task type")

        return super().on_success(retval, task_id, args, kwargs)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Log failed task with context information."""
        # Import TestExecutionError here to avoid circular imports
        from rhesis.backend.tasks.execution.run import TestExecutionError

        retries = getattr(self.request, "retries", 0)

        # Only send email notification if task permanently failed (not retrying) and email is enabled
        if isinstance(exc, TestExecutionError) or retries >= self.max_retries:
            self.log_with_context(
                "error",
                f"Task permanently failed after {retries} attempts",
                error=str(exc),
                exception_type=type(exc).__name__,
            )
            # Send email notification for permanent failure if enabled
            if self.send_email_notification:
                try:
                    self._send_task_completion_email("failed", error_message=str(exc))
                except Exception as email_error:
                    # Never let email failures break task error handling
                    self.log_with_context(
                        "error",
                        "Email notification failed in on_failure",
                        error=str(email_error),
                        exception_type=type(email_error).__name__,
                    )
            else:
                self.log_with_context("debug", "Email notification disabled for this task type")
        else:
            self.log_with_context(
                "warning",
                f"Task failed (will retry, attempt {retries}/{self.max_retries})",
                error=str(exc),
                exception_type=type(exc).__name__,
            )

        return super().on_failure(exc, task_id, args, kwargs, einfo)

    def before_start(self, task_id, args, kwargs):
        """Add organization_id and user_id to task request context."""
        # Get tenant context from headers (preferred) or kwargs (fallback)
        headers = getattr(self.request, "headers", {}) or {}

        # Set tenant context from headers first (primary mechanism)
        if headers:
            if "organization_id" in headers:
                self.request.organization_id = headers["organization_id"]
            if "user_id" in headers:
                self.request.user_id = headers["user_id"]

        # Fallback: Copy context from kwargs to request object (for backward compatibility)
        # This preserves tenant context for retries if it was passed via kwargs
        if "organization_id" in kwargs:
            self.request.organization_id = kwargs["organization_id"]
        if "user_id" in kwargs:
            self.request.user_id = kwargs["user_id"]

        # Do a soft validation (warning only)
        self.validate_params(args, kwargs)

        return super().before_start(task_id, args, kwargs)

    def _get_user_info(
        self, user_id: str, organization_id: str = None
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Get user email and name for notifications.

        Args:
            user_id: The user ID to look up

        Returns:
            Tuple of (email, name) or (None, None) if user not found
        """
        try:
            from rhesis.backend.app import crud

            with self.get_db_session() as db:
                # Session variables are automatically set by get_db_session()
                user = crud.get_user(db, user_id, organization_id=organization_id)
                if user:
                    display_name = (
                        user.display_name
                        if hasattr(user, "display_name")
                        else (user.name or user.given_name or user.email)
                    )
                    return user.email, display_name
                return None, None
        except Exception as e:
            self.log_with_context(
                "warning", "Failed to get user info for notifications", error=str(e)
            )
            return None, None

    def _send_task_completion_email(
        self, status: str, error_message: Optional[str] = None, **kwargs
    ):
        """
        Send email notification for task completion.

        Args:
            status: Task completion status ('success' or 'failed')
            error_message: Error message if task failed
            **kwargs: Additional context for the email (e.g., test_run_id)
        """
        try:
            from rhesis.backend.notifications import EmailTemplate, email_service

            # Get user context
            organization_id, user_id = self.get_tenant_context()

            self.log_with_context(
                "debug",
                "Email notification process started",
                status=status,
                organization_id=organization_id,
                user_id=user_id,
            )

            if not user_id:
                self.log_with_context("debug", "No user context available for email notification")
                return

            # Get user information
            self.log_with_context("debug", f"Looking up user information for user_id: {user_id}")
            user_email, user_name = self._get_user_info(user_id, organization_id)

            if not user_email:
                self.log_with_context("warning", f"No email found for user {user_id}")
                return

            self.log_with_context("debug", f"Found user email: {user_email}, name: {user_name}")

            # Skip placeholder emails (these are internal users without real emails)
            if "placeholder.rhesis.ai" in user_email:
                self.log_with_context(
                    "debug", f"Skipping notification for placeholder email: {user_email}"
                )
                return

            # Calculate execution time if possible
            execution_time = None
            if hasattr(self.request, "time_start") and self.request.time_start:
                try:
                    duration = datetime.utcnow().timestamp() - self.request.time_start
                    from rhesis.backend.tasks.utils import format_execution_time

                    execution_time = format_execution_time(duration)
                    self.log_with_context(
                        "debug", f"Calculated execution time from task timing: {execution_time}"
                    )
                except Exception as e:
                    self.log_with_context(
                        "warning",
                        "Failed to calculate execution time from task timing",
                        error=str(e),
                    )
            else:
                self.log_with_context(
                    "debug",
                    f"No task start time available - time_start: {getattr(self.request, 'time_start', 'not found')}",
                )

            # If we still don't have execution time, ensure we don't override a good value with None
            self.log_with_context("debug", f"Final calculated execution time: {execution_time}")

            # Get frontend URL for links
            frontend_url = os.getenv("FRONTEND_URL", "https://app.rhesis.ai")
            self.log_with_context("debug", f"Using frontend URL: {frontend_url}")

            # Check if email service is configured
            self.log_with_context(
                "debug", f"Email service configured: {email_service.is_configured}"
            )

            if not email_service.is_configured:
                self.log_with_context(
                    "warning", "Email service not configured - skipping email notification"
                )
                return

            # Get template and subject from decorator or use defaults
            template = getattr(self, "_email_template", EmailTemplate.TASK_COMPLETION)
            subject_template = getattr(self, "_email_subject_template", None)

            # Prepare template variables
            template_variables = {
                "recipient_name": user_name,
                "task_name": self.get_display_name(),
                "task_id": self.request.id,
                "status": status,
                "execution_time": execution_time,
                "error_message": error_message,
                "test_run_id": kwargs.get("test_run_id"),
                "frontend_url": frontend_url,
            }

            # Add any additional variables from the task result (but don't override with None values)
            for key, value in kwargs.items():
                if value is not None:
                    template_variables[key] = value

            # Special handling for execution_time - ensure we have a reasonable fallback
            if template_variables.get("execution_time") is None:
                template_variables["execution_time"] = "Unknown"
                self.log_with_context("debug", "Using fallback execution time: Unknown")

            # Build subject
            if subject_template:
                try:
                    # Create a copy of template variables with formatted status for subject
                    subject_variables = template_variables.copy()
                    subject_variables["status"] = status.title()  # Pre-format status for subject
                    subject = subject_template.format(**subject_variables)
                except (KeyError, AttributeError) as e:
                    self.log_with_context(
                        "warning", f"Subject template formatting error {e}, using default"
                    )
                    subject = f"Task Completed: {self.get_display_name()} - {status.title()}"
            else:
                subject = f"Task Completed: {self.get_display_name()} - {status.title()}"

            # Send the email using centralized approach
            self.log_with_context("info", f"Sending {status} email notification to {user_email}")
            success = email_service.send_email(
                template=template,
                recipient_email=user_email,
                subject=subject,
                template_variables=template_variables,
                task_id=self.request.id,
            )

            if success:
                self.log_with_context(
                    "info", f"Email notification sent successfully to {user_email}"
                )
            else:
                self.log_with_context("error", f"Email notification failed to send to {user_email}")

        except Exception as e:
            # Don't fail the task if email sending fails - just log the error
            self.log_with_context(
                "error",
                "Failed to send task completion email",
                error=str(e),
                exception_type=type(e).__name__,
                user_id=user_id if "user_id" in locals() else "unknown",
                email_address=user_email if "user_email" in locals() else "unknown",
            )

    def send_email_notification(
        self,
        recipient_email: str,
        recipient_name: str,
        status: str,
        execution_time: str,
        error_message: str = None,
        test_run_id: str = None,
        frontend_url: str = None,
    ) -> bool:
        """Send email notification using the email service."""
        try:
            from rhesis.backend.notifications import EmailTemplate, email_service

            return email_service.send_email(
                template=EmailTemplate.TASK_COMPLETION,
                recipient_email=recipient_email,
                subject=f"Task Completed: {self.get_display_name()} - {status.title()}",
                template_variables={
                    "recipient_name": recipient_name,
                    "task_name": self.get_display_name(),
                    "task_id": self.request.id,
                    "status": status,
                    "execution_time": execution_time,
                    "error_message": error_message,
                    "test_run_id": test_run_id,
                    "frontend_url": frontend_url,
                },
                task_id=self.request.id,
            )
        except Exception as e:
            logger.error(f"Failed to send email notification: {str(e)}")
            return False


class EmailEnabledTask(BaseTask):
    """Base task class with email notifications enabled (for user-facing tasks)."""

    send_email_notification = True


class SilentTask(BaseTask):
    """Base task class with email notifications disabled (for background/parallel tasks)."""

    send_email_notification = False
