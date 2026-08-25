"""
Tests for base task functionality in rhesis.backend.jobs.base

This module tests the BaseJob class including:
- Tenant context management
- Database session handling
- Task context retrieval
- Logging with context
- Task decorators and utilities
"""

from contextlib import contextmanager
from typing import Optional, Tuple
from unittest.mock import Mock, patch

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app.models.enums import NotificationEventType
from rhesis.backend.jobs.base import (
    BaseJob,
    SilentJob,
    email_notification,
    in_app_notification,
)


class MockTask:
    """Mock task class for testing BaseJob functionality"""

    def __init__(self, *args, **kwargs):
        # Mock the request object that Celery normally provides
        self.request = Mock()
        self.request.id = "test-task-123"
        self.request.organization_id = "org-456"
        self.request.user_id = "user-789"

    def get_tenant_context(self) -> Tuple[Optional[str], Optional[str]]:
        """Get tenant context from task request"""
        request = getattr(self, "request", None)
        if not request:
            return None, None

        organization_id = getattr(request, "organization_id", None)
        user_id = getattr(request, "user_id", None)

        return organization_id, user_id

    def log_with_context(self, level: str, message: str, **kwargs):
        """Log a message with consistent tenant context information."""
        from rhesis.backend.jobs.base import logger

        org_id, user_id = self.get_tenant_context()
        task_id = getattr(self.request, "id", "unknown") if hasattr(self, "request") else "unknown"

        context_info = {
            "task_id": task_id,
            "organization_id": org_id or "unknown",
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
        """Get a database session (session management refactored)."""
        from rhesis.backend.app.database import SessionLocal

        db = SessionLocal()
        try:
            # Start with a clean session
            db.expire_all()

            # Note: set_tenant removed - tenant context now passed directly to CRUD operations
            # Get task context for reference (not used for session setup)
            org_id, user_id = self.get_tenant_context()

            yield db
        finally:
            db.close()


class TestBaseTask:
    """Test BaseJob class functionality"""

    def test_get_tenant_context_with_request_context(self):
        """Test getting tenant context from task request"""
        task = MockTask()
        task.request.organization_id = "org123"
        task.request.user_id = "user456"

        org_id, user_id = task.get_tenant_context()

        assert org_id == "org123"
        assert user_id == "user456"

    def test_get_tenant_context_no_request(self):
        """Test getting tenant context when no request object exists"""
        task = MockTask()
        task.request = None

        org_id, user_id = task.get_tenant_context()

        assert org_id is None
        assert user_id is None

    def test_get_tenant_context_missing_attributes(self):
        """Test getting tenant context when request lacks organization_id/user_id"""
        task = MockTask()
        task.request = Mock()
        # Explicitly set attributes to None to simulate missing attributes
        task.request.organization_id = None
        task.request.user_id = None

        org_id, user_id = task.get_tenant_context()

        assert org_id is None
        assert user_id is None

    def test_log_with_context_full_context(self):
        """Test logging with full tenant context"""
        task = MockTask()
        task.request.id = "task-123"
        task.request.organization_id = "org-456"
        task.request.user_id = "user-789"

        with patch("rhesis.backend.jobs.base.logger") as mock_logger:
            task.log_with_context("info", "Test message", extra_field="extra_value")

            # Verify logger.info was called with formatted message
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0]
            message = call_args[0]

            assert "Test message" in message
            assert "task_id=task-123" in message
            assert "organization_id=org-456" in message
            assert "user_id=user-789" in message
            assert "extra_field=extra_value" in message

    def test_log_with_context_missing_context(self):
        """Test logging when context information is missing"""
        task = MockTask()
        task.request = None

        with patch("rhesis.backend.jobs.base.logger") as mock_logger:
            task.log_with_context("warning", "Test warning")

            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args[0]
            message = call_args[0]

            assert "Test warning" in message
            assert "task_id=unknown" in message
            assert "organization_id=unknown" in message
            assert "user_id=unknown" in message

    def test_log_with_context_different_levels(self):
        """Test logging with different log levels"""
        task = MockTask()

        with patch("rhesis.backend.jobs.base.logger") as mock_logger:
            # Test different log levels
            task.log_with_context("debug", "Debug message")
            task.log_with_context("error", "Error message")
            task.log_with_context("warning", "Warning message")

            mock_logger.debug.assert_called_once()
            mock_logger.error.assert_called_once()
            mock_logger.warning.assert_called_once()

    def test_get_db_session_with_tenant_context(self):
        """Test getting database session with tenant context (session management refactored)"""
        task = MockTask()
        task.request.organization_id = "org123"
        task.request.user_id = "user456"

        mock_db = Mock(spec=Session)

        with patch(
            "rhesis.backend.app.database.SessionLocal", return_value=mock_db
        ) as mock_session_local:
            with task.get_db_session() as db:
                assert db == mock_db
                mock_db.expire_all.assert_called_once()
                # Note: set_tenant removed - tenant context now passed directly to CRUD operations

            # Verify cleanup
            mock_db.close.assert_called_once()

    def test_get_db_session_no_tenant_context(self):
        """Test getting database session without tenant context (session management refactored)"""
        task = MockTask()
        task.request = None

        mock_db = Mock(spec=Session)

        with patch("rhesis.backend.app.database.SessionLocal", return_value=mock_db):
            with task.get_db_session() as db:
                assert db == mock_db
                mock_db.expire_all.assert_called_once()
                # Note: set_tenant removed - tenant context now passed directly to CRUD operations

    def test_get_db_session_partial_context(self):
        """Test getting database session with partial tenant context (session management refactored)"""
        task = MockTask()
        task.request.organization_id = "org123"
        task.request.user_id = None  # Only org_id, no user_id

        mock_db = Mock(spec=Session)

        with patch("rhesis.backend.app.database.SessionLocal", return_value=mock_db):
            with task.get_db_session() as db:
                assert db == mock_db
                # Note: set_tenant removed - partial tenant context now passed directly to CRUD operations


class TestWithTenantContextDecorator:
    """Test with_tenant_context decorator (REMOVED - decorator no longer needed)"""

    def test_with_tenant_context_decorator_success(self):
        """Test that demonstrates decorator is no longer needed (session management refactored)"""

        def mock_task_function(self, test_arg, db=None):
            # Note: with_tenant_context decorator removed - db session and tenant context
            # are now passed directly to task functions
            assert db is not None
            return f"Task executed with {test_arg}"

        # Create mock task instance
        task = MockTask()
        task.request.organization_id = "org123"
        task.request.user_id = "user456"

        mock_db = Mock(spec=Session)

        with patch.object(task, "get_db_session") as mock_get_db_session:
            # Mock the context manager
            mock_get_db_session.return_value.__enter__ = Mock(return_value=mock_db)
            mock_get_db_session.return_value.__exit__ = Mock(return_value=None)

            # Simulate direct function call (no decorator needed)
            result = mock_task_function(task, "test_value", db=mock_db)

            assert result == "Task executed with test_value"
            # Note: set_tenant removed - tenant context now passed directly to CRUD operations

    def test_with_tenant_context_decorator_no_context(self):
        """Test that demonstrates decorator is no longer needed when no tenant context (session management refactored)"""

        def mock_task_function(self, test_arg, db=None):
            assert db is not None
            return f"Task executed with {test_arg}"

        # Create mock task instance without context
        task = MockTask()
        task.request = Mock()
        # No organization_id or user_id set

        mock_db = Mock(spec=Session)

        with patch.object(task, "get_db_session") as mock_get_db_session:
            mock_get_db_session.return_value.__enter__ = Mock(return_value=mock_db)
            mock_get_db_session.return_value.__exit__ = Mock(return_value=None)

            # Simulate direct function call (no decorator needed)
            result = mock_task_function(task, "test_value", db=mock_db)

            assert result == "Task executed with test_value"
            # Note: set_tenant removed - tenant context now passed directly to CRUD operations


class TestEmailNotificationDecorator:
    """Test email_notification decorator"""

    def test_email_notification_decorator_basic(self):
        """Test basic email notification decorator functionality"""

        @email_notification(template="TEST_TEMPLATE", subject_template="Test Subject")
        def mock_task_function(self):
            return {"result": "success"}

        # Since we're testing the decorator structure, not the full email functionality
        # we just verify it can be applied and doesn't break the function
        task = MockTask()
        result = mock_task_function(task)

        assert result == {"result": "success"}

    def test_email_enabled_tasks_have_flag_set(self):
        """Test that tasks which should send emails have the correct base class and flag set."""
        from rhesis.backend.jobs.execution.results import collect_results
        from rhesis.backend.jobs.garak import import_garak_probes_task
        from rhesis.backend.jobs.test_set import generate_and_save_test_set

        # Verify that these tasks have the flag explicitly set to True
        assert getattr(generate_and_save_test_set, "send_email_notification_flag", False) is True
        assert getattr(collect_results, "send_email_notification_flag", False) is True
        assert getattr(import_garak_probes_task, "send_email_notification_flag", False) is True


class TestInAppNotificationDecorator:
    """Test in_app_notification decorator"""

    def test_decorator_sets_notification_kind(self):
        @in_app_notification(NotificationEventType.TestSet.GENERATION_COMPLETED)
        def mock_task_function(self):
            return {"result": "success"}

        assert (
            mock_task_function._notification_kind
            == NotificationEventType.TestSet.GENERATION_COMPLETED
        )

    def test_decorator_does_not_break_the_function(self):
        @in_app_notification(NotificationEventType.TestRun.EXECUTION_COMPLETED)
        def mock_task_function(self):
            return {"result": "success"}

        task = MockTask()
        assert mock_task_function(task) == {"result": "success"}

    def test_registered_tasks_carry_their_notification_kind(self):
        """Guards decorator *ordering* on the real tasks.

        ``@in_app_notification`` must sit above ``@app.task`` so it stamps the
        bound Task singleton. Below it, the attribute lands on the plain
        function that app.task wraps, ``self._notification_kind`` is never
        found at runtime, and the notification silently never fires.
        """
        from rhesis.backend.jobs.architect.chat import architect_chat_task
        from rhesis.backend.jobs.execution.results import collect_results
        from rhesis.backend.jobs.garak import import_garak_probes_task, sync_garak_test_set_task
        from rhesis.backend.jobs.test_set import (
            generate_and_save_owasp_test_set,
            generate_and_save_test_set,
        )

        assert (
            getattr(generate_and_save_test_set, "_notification_kind", None)
            == NotificationEventType.TestSet.GENERATION_COMPLETED
        )
        assert (
            getattr(generate_and_save_owasp_test_set, "_notification_kind", None)
            == NotificationEventType.TestSet.GENERATION_COMPLETED
        )
        assert (
            getattr(import_garak_probes_task, "_notification_kind", None)
            == NotificationEventType.TestSet.GARAK_IMPORT_COMPLETED
        )
        assert (
            getattr(sync_garak_test_set_task, "_notification_kind", None)
            == NotificationEventType.TestSet.GARAK_SYNC_COMPLETED
        )
        assert (
            getattr(collect_results, "_notification_kind", None)
            == NotificationEventType.TestRun.EXECUTION_COMPLETED
        )
        assert (
            getattr(architect_chat_task, "_notification_kind", None)
            == NotificationEventType.Architect.PLAN_COMPLETED
        )


def _real_base_task(retries: int = 0) -> BaseJob:
    """A BaseJob instance with a real (unbound) request context, to exercise
    on_success/on_failure without a real Celery worker or DB.

    ``Task.request`` is a read-only property backed by ``request_stack``
    (``None`` until a task is bound to an app); ``push_request`` is Celery's
    own supported way to populate it for a bare instance like this one.
    """
    from celery.utils.threads import LocalStack

    task = BaseJob()
    task.request_stack = LocalStack()
    task.push_request(id="task-1", retries=retries, headers={}, kwargs={})
    task.send_email_notification_flag = False
    return task


class TestOnSuccessInAppNotification:
    """on_success calls _send_task_completion_notification iff _notification_kind is set."""

    def test_calls_notification_when_kind_set(self):
        task = _real_base_task()
        task._notification_kind = NotificationEventType.TestSet.GENERATION_COMPLETED

        with (
            patch.object(task, "_send_task_completion_notification") as mock_notify,
            patch.object(task, "_get_execution_time", return_value="1s"),
            patch.object(task, "log_with_context"),
        ):
            task.on_success({"result": "ok"}, "task-1", [], {})

        mock_notify.assert_called_once_with({"result": "ok"}, None)

    def test_skips_notification_when_kind_not_set(self):
        task = _real_base_task()

        with (
            patch.object(task, "_send_task_completion_notification") as mock_notify,
            patch.object(task, "_get_execution_time", return_value="1s"),
            patch.object(task, "log_with_context"),
        ):
            task.on_success({"result": "ok"}, "task-1", [], {})

        mock_notify.assert_not_called()

    def test_notification_failure_does_not_propagate(self):
        task = _real_base_task()
        task._notification_kind = NotificationEventType.TestSet.GENERATION_COMPLETED

        with (
            patch.object(
                task,
                "_send_task_completion_notification",
                side_effect=RuntimeError("boom"),
            ),
            patch.object(task, "_get_execution_time", return_value="1s"),
            patch.object(task, "log_with_context"),
        ):
            # Must not raise -- a notification failure must not fail the task.
            task.on_success({"result": "ok"}, "task-1", [], {})


class TestSilentTaskInAppNotification:
    """SilentJob must still send in-app notifications on success.

    It overrides on_success with ``super(BaseJob, self)``, skipping
    BaseJob.on_success entirely. Since it does *not* override on_failure,
    dropping the notification here would leave a decorated SilentJob
    notifying on failure only -- the architect task is one such task.
    """

    @staticmethod
    def _silent_task() -> SilentJob:
        from celery.utils.threads import LocalStack

        task = SilentJob()
        task.request_stack = LocalStack()
        task.push_request(id="task-1", retries=0, headers={}, kwargs={})
        return task

    def test_notifies_on_success_when_kind_set(self):
        task = self._silent_task()
        task._notification_kind = NotificationEventType.Architect.PLAN_COMPLETED

        with (
            patch.object(task, "_send_task_completion_notification") as mock_notify,
            patch.object(task, "log_with_context"),
        ):
            task.on_success({"result": "ok"}, "task-1", [], {})

        mock_notify.assert_called_once_with({"result": "ok"}, None)

    def test_skips_notification_when_kind_not_set(self):
        task = self._silent_task()

        with (
            patch.object(task, "_send_task_completion_notification") as mock_notify,
            patch.object(task, "log_with_context"),
        ):
            task.on_success({"result": "ok"}, "task-1", [], {})

        mock_notify.assert_not_called()

    def test_notification_failure_does_not_propagate(self):
        task = self._silent_task()
        task._notification_kind = NotificationEventType.Architect.PLAN_COMPLETED

        with (
            patch.object(
                task,
                "_send_task_completion_notification",
                side_effect=RuntimeError("boom"),
            ),
            patch.object(task, "log_with_context"),
        ):
            # Must not raise -- a notification failure must not fail the task.
            task.on_success({"result": "ok"}, "task-1", [], {})


class TestDecliningRenderer:
    """A renderer returning None means no notification row is written."""

    def test_declined_render_writes_nothing(self):
        task = _real_base_task()
        task._notification_kind = NotificationEventType.Architect.PLAN_COMPLETED

        with (
            patch.object(task, "get_tenant_context", return_value=("org-1", "user-1", "proj-1")),
            patch("rhesis.backend.app.services.notification.notify") as mock_notify,
            patch.object(task, "get_db_session") as mock_session,
            patch.object(task, "log_with_context"),
        ):
            # An ordinary interactive turn: no resume prefix, so the architect
            # renderer declines.
            task._send_task_completion_notification({"session_id": "s-1"}, None)

        mock_notify.assert_not_called()
        mock_session.assert_not_called()


class TestOnFailureInAppNotification:
    """on_failure only notifies once a task has permanently failed, not on a retry."""

    def test_does_not_notify_while_retrying(self):
        task = _real_base_task(retries=0)
        task._notification_kind = NotificationEventType.TestRun.EXECUTION_COMPLETED
        task.max_retries = 3

        with (
            patch.object(task, "_send_task_completion_notification") as mock_notify,
            patch.object(task, "_get_execution_time", return_value="1s"),
            patch.object(task, "log_with_context"),
        ):
            task.on_failure(ValueError("boom"), "task-1", [], {}, None)

        mock_notify.assert_not_called()

    def test_notifies_on_permanent_failure(self):
        task = _real_base_task(retries=3)
        task._notification_kind = NotificationEventType.TestRun.EXECUTION_COMPLETED
        task.max_retries = 3

        with (
            patch.object(task, "_send_task_completion_notification") as mock_notify,
            patch.object(task, "_get_execution_time", return_value="1s"),
            patch.object(task, "log_with_context"),
        ):
            task.on_failure(ValueError("boom"), "task-1", [], {}, None)

        mock_notify.assert_called_once_with(None, "boom")


class TestTaskValidation:
    """Test task parameter validation"""

    def test_validate_params_basic(self):
        """Test basic parameter validation"""
        task = MockTask()

        # Test that validate_params can be called without error
        # (The actual implementation may vary based on specific validation logic)
        try:
            task.validate_params([], {})
        except AttributeError:
            # Method might not be implemented in base class
            pass
        except Exception as e:
            pytest.fail(f"validate_params raised unexpected exception: {e}")


@pytest.fixture
def mock_celery_task():
    """Fixture providing a mock Celery task for testing"""
    task = MockTask()
    task.request = Mock()
    task.request.id = "test-task-123"
    task.request.organization_id = "org-456"
    task.request.user_id = "user-789"
    return task


@pytest.fixture
def mock_db_session():
    """Fixture providing a mock database session"""
    return Mock(spec=Session)


class TestTaskIntegration:
    """Integration tests for task functionality"""

    def test_full_task_lifecycle(self, mock_celery_task, mock_db_session):
        """Test complete task execution lifecycle (session management refactored)"""

        with patch("rhesis.backend.app.database.SessionLocal", return_value=mock_db_session):
            # Test getting tenant context
            org_id, user_id = mock_celery_task.get_tenant_context()
            assert org_id == "org-456"
            assert user_id == "user-789"

            # Test database session with context
            with mock_celery_task.get_db_session() as db:
                assert db == mock_db_session
                # Note: set_tenant removed - tenant context now passed directly to CRUD operations

            # Test logging with context
            with patch("rhesis.backend.jobs.base.logger") as mock_logger:
                mock_celery_task.log_with_context("info", "Task completed successfully")
                mock_logger.info.assert_called_once()
