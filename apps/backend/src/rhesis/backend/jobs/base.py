import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional, Tuple

from celery import Task

from rhesis.backend.app.config.settings import get_frontend_settings
from rhesis.backend.app.database import (
    get_db_with_tenant_variables,
)
from rhesis.backend.app.utils.database_exceptions import ItemDeletedException
from rhesis.backend.app.utils.model_errors import ModelConfigurationError
from rhesis.backend.jobs.enums import DEFAULT_MAX_RETRIES, DEFAULT_RETRY_BACKOFF_MAX

logger = logging.getLogger(__name__)

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
        @app.task(base=EmailEnabledJob, bind=True)
        def my_task(self, ...):
            ...

    EmailEnabledJob sets send_email_notification_flag so completion emails run; the
    decorator only selects the template (it does not enable sending by itself).
    """

    def decorator(task_func):
        # Store email configuration on the task function
        task_func._email_template = template
        task_func._email_subject_template = subject_template
        return task_func

    return decorator


def in_app_notification(event_type):
    """Decorator to enable an in-app notification for task completion.

    Args:
        event_type: NotificationEventType enum value identifying the
            NOTIFICATION_CATALOG entry to render and publish.

    Usage:
        @in_app_notification(NotificationEventType.TestSet.GENERATION_COMPLETED)
        @app.task(base=BaseJob, bind=True)
        def my_task(self, ...):
            ...

    Unlike ``email_notification``, no matching base class is needed:
    ``BaseJob.on_success``/``on_failure`` check for this attribute
    unconditionally, so the decorator alone is enough to enable it.
    """

    def decorator(task_func):
        task_func._notification_kind = event_type
        return task_func

    return decorator


class BaseJob(Task):
    """Base task class with tenant context, logging, retry logic, and email notifications."""

    # Default values for all tasks
    max_retries = 3
    default_retry_delay = 10
    send_email_notification_flag = False  # Default: no emails
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

    # Checked by Celery before autoretry_for. A bad model configuration (wrong
    # region, unknown model, missing credentials) returns the same error on
    # every attempt, so retrying it just multiplies the log noise. A
    # soft-deleted row is the same story: whatever it referenced stays deleted
    # on every retry.
    dont_autoretry_for = (ModelConfigurationError, ItemDeletedException)

    # Maximum number of retries - use centralized constant
    max_retries = DEFAULT_MAX_RETRIES

    # Exponential backoff: 1min, 5min, 25min
    retry_backoff = True
    retry_backoff_max = DEFAULT_RETRY_BACKOFF_MAX

    # Report started status
    track_started = True

    def get_tenant_context(self) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Get tenant context from task request in a consistent way.

        Returns:
            Tuple of (organization_id, user_id, project_id)
        """
        request = getattr(self, "request", None)
        if not request:
            return None, None, None

        organization_id = getattr(request, "organization_id", None)
        user_id = getattr(request, "user_id", None)
        project_id = getattr(request, "project_id", None)

        return organization_id, user_id, project_id

    def log_with_context(self, level: str, message: str, **kwargs):
        """
        Log a message with consistent tenant context information.

        Args:
            level: Log level ('info', 'warning', 'error', 'debug')
            message: The message to log
            **kwargs: Additional context to include in the log
        """
        organization_id, user_id, _ = self.get_tenant_context()
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

        Sets PostgreSQL session variables for RLS and stores the RequestScope on
        Session.info, which the auto-filter / auto-stamp listeners read. (Scope is
        stored on the session rather than a ContextVar so it is visible regardless
        of which thread issues the queries.)
        """
        organization_id, user_id, project_id = self.get_tenant_context()

        with get_db_with_tenant_variables(
            organization_id or "", user_id or "", project_id or ""
        ) as db:
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

    @staticmethod
    def _job_transition_for_success(retval) -> str:
        """A task that returns ``{"status": "cancelled", ...}`` ended cooperatively,
        not successfully -- the job row should say so rather than "completed".
        """
        if isinstance(retval, dict) and retval.get("status") == "cancelled":
            return "cancelled"
        return "completed"

    def on_success(self, retval, task_id, args, kwargs):
        """Log successful task completion with context information."""
        transition = self._job_transition_for_success(retval)
        self._advance_job_row(transition)

        self.log_with_context(
            "info",
            "Task cancelled" if transition == "cancelled" else "Task completed successfully",
            task_result_type=type(retval).__name__,
            execution_time=self._get_execution_time() or "Unknown",
        )

        # Send email notification for successful completion if enabled
        if self.send_email_notification_flag:
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
                        f"Passing {len(filtered_retval)} variables from task result"
                        " to email template",
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

        self._notify_task_success(retval)

        return super().on_success(retval, task_id, args, kwargs)

    def _notify_task_success(self, retval) -> None:
        """Send the in-app notification for a successful run, if one is configured.

        Split out of ``on_success`` so ``SilentJob`` can call it without
        inheriting the rest of that method -- see SilentJob.on_success.
        """
        if getattr(self, "_notification_kind", None) is None:
            return
        try:
            self._send_task_completion_notification(retval, None)
        except Exception as e:
            # Never let notification failures break task completion
            self.log_with_context(
                "error",
                "In-app notification failed in on_success",
                error=str(e),
                exception_type=type(e).__name__,
            )

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Log failed task with context information."""
        # Import TestExecutionError here to avoid circular imports
        from rhesis.backend.jobs.execution.run import TestExecutionError

        retries = getattr(self.request, "retries", 0)

        # Non-retryable exceptions are final on their first attempt, so don't
        # report them as "will retry" — Celery already stopped the autoretry.
        is_non_retryable = isinstance(exc, tuple(self.dont_autoretry_for or ()))

        # Only send email notification if task permanently failed (not retrying)
        # and email is enabled
        if isinstance(exc, TestExecutionError) or is_non_retryable or retries >= self.max_retries:
            reason = (
                "Task failed permanently (not retryable)"
                if is_non_retryable
                else f"Task permanently failed after {retries} attempts"
            )
            self.log_with_context(
                "error",
                reason,
                error=str(exc),
                exception_type=type(exc).__name__,
                execution_time=self._get_execution_time() or "Unknown",
            )
            # Send email notification for permanent failure if enabled
            if self.send_email_notification_flag:
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

            # Send in-app notification for permanent failure if enabled
            if getattr(self, "_notification_kind", None) is not None:
                try:
                    self._send_task_completion_notification(None, str(exc))
                except Exception as notification_error:
                    # Never let notification failures break task error handling
                    self.log_with_context(
                        "error",
                        "In-app notification failed in on_failure",
                        error=str(notification_error),
                        exception_type=type(notification_error).__name__,
                    )
            # Terminal, so the row can move to failed. Deliberately after the
            # notifications above: those already guard themselves, and the row
            # should record the outcome even if one of them misbehaved.
            self._advance_job_row("failed", error=exc)
        else:
            self.log_with_context(
                "warning",
                f"Task failed (will retry, attempt {retries}/{self.max_retries})",
                error=str(exc),
                exception_type=type(exc).__name__,
                execution_time=self._get_execution_time() or "Unknown",
            )
            # Not terminal: count the attempt but leave the job running, or the
            # Jobs screen would show a job as failed while it is about to run
            # again.
            self._advance_job_row("retrying")

        return super().on_failure(exc, task_id, args, kwargs, einfo)

    def before_start(self, task_id, args, kwargs):
        """Add organization_id and user_id to task request context."""
        # Store task start time for execution time calculation
        self.request.custom_start_time = datetime.now(timezone.utc)

        # Get tenant context from headers (preferred) or kwargs (fallback)
        headers = getattr(self.request, "headers", {}) or {}

        # Set tenant context from headers first (primary mechanism)
        if headers:
            if "organization_id" in headers:
                self.request.organization_id = headers["organization_id"]
            if "user_id" in headers:
                self.request.user_id = headers["user_id"]
            if "project_id" in headers:
                self.request.project_id = headers["project_id"]

        # Fallback: Copy context from kwargs to request object (for backward compatibility)
        # This preserves tenant context for retries if it was passed via kwargs
        if "organization_id" in kwargs:
            self.request.organization_id = kwargs["organization_id"]
        if "user_id" in kwargs:
            self.request.user_id = kwargs["user_id"]
        if "project_id" in kwargs:
            self.request.project_id = kwargs["project_id"]

        # Do a soft validation (warning only)
        self.validate_params(args, kwargs)

        self._advance_job_row("running")

        return super().before_start(task_id, args, kwargs)

    def _advance_job_row(self, transition: str, error: Optional[BaseException] = None) -> None:
        """Move this task's ``job`` row to its next state.

        A thin wrapper so the lifecycle hooks below stay readable and so the
        tenant triple is resolved in one place. ``tracking`` swallows its own
        failures, and this adds a second guard: a hook that raised would turn
        bookkeeping into a task failure.
        """
        from rhesis.backend.jobs import tracking

        try:
            celery_task_id = getattr(self.request, "id", None)
            if not celery_task_id:
                return

            org_id, user_id, project_id = self.get_tenant_context()
            args = (celery_task_id, org_id or "", user_id or "", project_id or "")

            if transition == "running":
                tracking.mark_running(*args)
            elif transition == "completed":
                tracking.mark_completed(*args)
            elif transition == "cancelled":
                tracking.mark_cancelled(*args)
            elif transition == "failed":
                tracking.mark_failed(*args, error=error or Exception("Unknown error"))
            elif transition == "retrying":
                tracking.mark_retrying(*args, attempt=getattr(self.request, "retries", 0) + 1)
        except Exception as exc:
            logger.warning(f"Job row transition '{transition}' failed: {exc}", exc_info=True)

        # Separate try/except: the activity-log narrative must not be able to
        # affect the job row transition above, in either direction.
        try:
            self._emit_lifecycle_event(transition, error=error)
        except Exception as exc:
            logger.warning(f"Lifecycle event '{transition}' failed: {exc}", exc_info=True)

    def _emit_lifecycle_event(self, transition: str, error: Optional[BaseException] = None) -> None:
        """The activity-log side of a job-row transition. See _advance_job_row."""
        from datetime import datetime, timezone

        from rhesis.backend.events import emit
        from rhesis.backend.events.correlation import resolve_ids
        from rhesis.backend.events.types import (
            JobCancelled,
            JobCompleted,
            JobFailed,
            JobRetried,
            JobStarted,
        )
        from rhesis.backend.jobs.tracking import job_type_for

        celery_task_id = getattr(self.request, "id", None)
        if not celery_task_id:
            return

        org_id, user_id, project_id = self.get_tenant_context()
        if not org_id:
            # No tenant to attribute this to -- matches _advance_job_row's
            # own silent no-op above rather than raising on a required field.
            return

        # Reads whatever attach_trace_context_for_task attached at
        # task_prerun -- the request's trace context, already current for
        # the whole task body by this point.
        trace_id, span_id = resolve_ids()
        source = job_type_for(getattr(self, "name", "") or "")
        common = dict(
            occurred_at=datetime.now(timezone.utc),
            organization_id=org_id,
            project_id=project_id,
            user_id=user_id,
            trace_id=trace_id,
            span_id=span_id,
            celery_task_id=celery_task_id,
            source=source,
        )

        if transition == "running":
            event = JobStarted(**common)
        elif transition == "completed":
            event = JobCompleted(**common)
        elif transition == "cancelled":
            event = JobCancelled(**common)
        elif transition == "failed":
            event = JobFailed(
                **common,
                error_type=type(error).__name__ if error else "Exception",
                error_message=str(error) if error else "Unknown error",
            )
        elif transition == "retrying":
            event = JobRetried(**common, attempt=getattr(self.request, "retries", 0) + 1)
        else:
            return

        emit(event)

    def set_progress(self, current: int, total: int) -> None:
        """Update this job's progress counters on the ``job`` row.

        The progress bar in the Jobs list/detail reads these columns.
        Safe to call at high frequency; each call opens its own session.
        """
        try:
            from rhesis.backend.jobs import tracking

            celery_task_id = getattr(self.request, "id", None)
            if not celery_task_id:
                return
            org_id, user_id, project_id = self.get_tenant_context()
            tracking.set_progress(
                celery_task_id,
                org_id or "",
                user_id or "",
                project_id or "",
                current=current,
                total=total,
            )
        except Exception as exc:
            logger.warning(f"set_progress failed: {exc}")

    def set_entity(self, entity_type: str, entity_id: str) -> None:
        """Link this job to the entity it produced (e.g. a TestSet created mid-task).

        For jobs whose entity exists at dispatch time, pass entity_type/entity_id
        to launch_job instead. This method covers the case where the entity is
        created inside the task body.
        """
        try:
            from rhesis.backend.jobs import tracking

            celery_task_id = getattr(self.request, "id", None)
            if not celery_task_id:
                return
            org_id, user_id, project_id = self.get_tenant_context()
            tracking.set_entity(
                celery_task_id,
                org_id or "",
                user_id or "",
                project_id or "",
                entity_type=entity_type,
                entity_id=entity_id,
            )
        except Exception as exc:
            logger.warning(f"set_entity failed: {exc}")

    def emit(self, message: str, level: str = "info", *, context: Optional[dict] = None) -> None:
        """Write a user-facing line to this job's activity log.

        Deliberately not ``log_with_context``: that stays developer logging
        to stdout. This is what shows up in the Jobs screen's detail view --
        "I recorded this for the user", not "I logged this for me". Also
        writes a DEBUG line via the dispatcher, so stdout keeps the full
        narrative regardless.

        A narration call is not allowed to fail the job it is narrating, so
        the whole body is wrapped -- unlike ``_emit_lifecycle_event``, which
        leaves that to each of its two callers, ``emit()`` is called directly
        from many task bodies and cannot rely on every call site remembering
        to guard it.
        """
        try:
            from datetime import datetime, timezone

            from rhesis.backend.events import emit as emit_event
            from rhesis.backend.events.correlation import resolve_ids
            from rhesis.backend.events.types import ActivityLogged
            from rhesis.backend.jobs.tracking import job_type_for

            celery_task_id = getattr(self.request, "id", None)
            org_id, user_id, project_id = self.get_tenant_context()
            if not org_id:
                self.log_with_context("warning", "emit() called with no tenant context, dropped")
                return

            trace_id, span_id = resolve_ids()
            emit_event(
                ActivityLogged(
                    occurred_at=datetime.now(timezone.utc),
                    organization_id=org_id,
                    project_id=project_id,
                    user_id=user_id,
                    trace_id=trace_id,
                    span_id=span_id,
                    celery_task_id=celery_task_id,
                    source=job_type_for(getattr(self, "name", "") or ""),
                    level=level,
                    message=message,
                    context=context,
                )
            )
        except Exception as exc:
            self.log_with_context("warning", f"emit() failed, message dropped: {exc}")

    def _get_execution_time(self) -> Optional[str]:
        """Return formatted task execution duration, if start time is available."""
        from rhesis.backend.jobs.utils import format_execution_time

        if hasattr(self.request, "custom_start_time") and self.request.custom_start_time:
            try:
                duration = (
                    datetime.now(timezone.utc) - self.request.custom_start_time
                ).total_seconds()
                return format_execution_time(duration)
            except Exception:
                pass
        elif hasattr(self.request, "time_start") and self.request.time_start:
            try:
                duration = datetime.now(timezone.utc).timestamp() - self.request.time_start
                return format_execution_time(duration)
            except Exception:
                pass
        return None

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
            from rhesis.backend.app.crud import user as user_crud

            with self.get_db_session() as db:
                # Session variables are automatically set by get_db_session()
                user = user_crud.get_user(db, user_id, organization_id=organization_id)
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
            organization_id, user_id, _ = self.get_tenant_context()

            if not user_id:
                return

            # Get user information
            user_email, user_name = self._get_user_info(user_id, organization_id)

            if not user_email:
                self.log_with_context("warning", f"No email found for user {user_id}")
                return

            # Skip placeholder emails (these are internal users without real emails)
            if "placeholder.rhesis.ai" in user_email:
                return

            execution_time = self._get_execution_time()

            # Get frontend URL for links
            frontend_url = get_frontend_settings().url

            if not email_service.is_configured:
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

            # Add any additional variables from the task result
            # (but don't override with None values)
            for key, value in kwargs.items():
                if value is not None:
                    template_variables[key] = value

            # Special handling for execution_time - ensure we have a reasonable fallback
            if template_variables.get("execution_time") is None:
                template_variables["execution_time"] = "Unknown"

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

            success = email_service.send_email(
                template=template,
                recipient_email=user_email,
                subject=subject,
                template_variables=template_variables,
                task_id=self.request.id,
            )

            if success:
                self.log_with_context(
                    "info",
                    f"Task completion email sent ({status})",
                    recipient_email=user_email,
                )
            else:
                self.log_with_context(
                    "error",
                    f"Task completion email failed ({status})",
                    recipient_email=user_email,
                )

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

    def _send_task_completion_notification(
        self, retval: Optional[dict], error: Optional[str]
    ) -> None:
        """Render and send the in-app notification configured via ``in_app_notification``.

        Args:
            retval: The task's return value on success, or None on failure.
            error: The exception message on failure, or None on success.
        """
        from rhesis.backend.app.services.notification import NOTIFICATION_CATALOG, notify

        event_type = self._notification_kind
        organization_id, user_id, project_id = self.get_tenant_context()
        if not user_id:
            self.log_with_context(
                "warning", "No user_id in tenant context, skipping in-app notification"
            )
            return

        kind = NOTIFICATION_CATALOG[event_type]
        if kind.render is None:
            raise ValueError(
                f"NotificationKind for {event_type!r} has no render fn for a Celery hook"
            )
        # Normalized to a dict here so every render function can read keys off it
        # directly. A task that returns None or a non-dict on success would
        # otherwise raise inside the renderer, and on_success swallows that --
        # losing the notification with only a log line.
        result = retval if isinstance(retval, dict) else {}
        rendered = kind.render(self, result, error)
        if rendered is None:
            # The renderer declined: this run completed but isn't a finished
            # job worth telling the user about (see RenderFn's docstring).
            return

        with self.get_db_session() as db:
            notify(
                db,
                event_type=event_type,
                rendered=rendered,
                user_id=user_id,
                organization_id=organization_id,
                project_id=project_id,
            )


class EmailEnabledJob(BaseJob):
    """Base task class with email notifications enabled (for user-facing tasks)."""

    send_email_notification_flag = True


class SilentJob(BaseJob):
    """Base task class with email notifications disabled (for background/parallel tasks)."""

    send_email_notification_flag = False

    def on_success(self, retval, task_id, args, kwargs):
        """Skip generic completion logging; callers log task-specific outcomes.

        In-app notifications still fire, and the job row still advances --
        "Silent" here means no email and no generic log line, not no
        bookkeeping. Without the ``_advance_job_row`` call, skipping
        ``BaseJob.on_success`` would leave every SilentJob-based task
        (test execution, embedding, architect chat, endpoint exploration)
        stuck at "running" forever, since ``on_failure`` (not overridden)
        already advances the row but nothing else does on this path.
        """
        self._advance_job_row(self._job_transition_for_success(retval))
        self._notify_task_success(retval)
        return super(BaseJob, self).on_success(retval, task_id, args, kwargs)
