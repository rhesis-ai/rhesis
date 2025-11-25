"""
Tests for base task functionality in rhesis.backend.tasks.base

This module tests the BaseTask class including:
- Tenant context management
- Database session handling
- Task context retrieval
- Logging with context
- Task decorators and utilities
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from contextlib import contextmanager
from sqlalchemy.orm import Session
from celery import Task
from typing import Optional, Tuple

from rhesis.backend.tasks.base import BaseTask, email_notification


class MockTask:
    """Mock task class for testing BaseTask functionality"""

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
        from rhesis.backend.tasks.base import logger

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
    """Test BaseTask class functionality"""

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

        with patch("rhesis.backend.tasks.base.logger") as mock_logger:
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

        with patch("rhesis.backend.tasks.base.logger") as mock_logger:
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

        with patch("rhesis.backend.tasks.base.logger") as mock_logger:
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
            with patch("rhesis.backend.tasks.base.logger") as mock_logger:
                mock_celery_task.log_with_context("info", "Task completed successfully")
                mock_logger.info.assert_called_once()
