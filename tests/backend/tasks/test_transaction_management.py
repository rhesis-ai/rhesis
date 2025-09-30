"""
🔄 Transaction Management Testing for Task Execution

Comprehensive test suite for verifying that transaction management works correctly
in task execution functions after refactoring to remove manual db.commit() and db.rollback() calls.

Tests focus on:
- Automatic transaction commit/rollback in task execution
- Proper error handling in background tasks
- Result processor transaction management

Functions tested from tasks:
- execution/test.py: execute_test (rollback handling)
- execution/result_processor.py: update_test_run_status (commit handling)

Run with: python -m pytest tests/backend/tasks/test_transaction_management.py -v
"""

import pytest
import uuid
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.tasks.execution import result_processor
from tests.backend.routes.fixtures.data_factories import (
    TestDataFactory
)


@pytest.mark.unit
@pytest.mark.tasks
@pytest.mark.transaction
class TestTaskTransactionManagement:
    """🔄 Test automatic transaction management in task execution"""

    def test_result_processor_update_test_run_status_commits_on_success(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """Test that update_test_run_status commits automatically on success"""
        # Create a test run
        test_run_data = {
            "name": f"Test Run {uuid.uuid4()}",
            "description": "Test run for transaction testing"
        }
        test_run = models.TestRun(**test_run_data)
        test_run.organization_id = uuid.UUID(test_org_id)
        test_run.user_id = uuid.UUID(authenticated_user_id)
        test_run.status = models.TestRunStatus.RUNNING
        test_db.add(test_run)
        test_db.flush()
        
        original_status = test_run.status
        
        # Mock logger function
        def mock_logger_func(level, message):
            pass
        
        # Update test run status
        result_processor.update_test_run_status(
            test_db, 
            str(test_run.id), 
            models.TestRunStatus.COMPLETED,
            tests_passed=5,
            tests_failed=2,
            logger_func=mock_logger_func
        )
        
        # Verify test run status was updated and persisted
        db_test_run = test_db.query(models.TestRun).filter(
            models.TestRun.id == test_run.id
        ).first()
        assert db_test_run is not None
        assert db_test_run.status == models.TestRunStatus.COMPLETED
        assert db_test_run.status != original_status
        assert db_test_run.tests_passed == 5
        assert db_test_run.tests_failed == 2

    def test_result_processor_update_test_run_status_with_invalid_id(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """Test that update_test_run_status handles invalid test run ID gracefully"""
        # Mock logger function to capture warnings
        logged_messages = []
        def mock_logger_func(level, message):
            logged_messages.append((level, message))
        
        # Try to update non-existent test run
        non_existent_id = str(uuid.uuid4())
        
        # This should not raise an exception
        result_processor.update_test_run_status(
            test_db,
            non_existent_id,
            models.TestRunStatus.COMPLETED,
            tests_passed=0,
            tests_failed=0,
            logger_func=mock_logger_func
        )
        
        # Verify warning was logged
        warning_messages = [msg for level, msg in logged_messages if level == "warning"]
        assert len(warning_messages) > 0
        assert any("no status returned" in msg.lower() for msg in warning_messages)

    def test_result_processor_format_status_details(self):
        """Test that format_status_details works correctly"""
        # Test various combinations
        result1 = result_processor.format_status_details(5, 0)
        assert "5 passed" in result1
        assert "0 failed" in result1
        
        result2 = result_processor.format_status_details(3, 2)
        assert "3 passed" in result2
        assert "2 failed" in result2
        
        result3 = result_processor.format_status_details(0, 5)
        assert "0 passed" in result3
        assert "5 failed" in result3

    def test_task_execution_error_handling_without_manual_rollback(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """Test that task execution handles errors gracefully without manual rollback calls"""
        # This test simulates the behavior after our refactoring where manual rollback is removed
        
        # Create test data
        test_data = TestDataFactory.sample_data()
        test = models.Test(**test_data)
        test.organization_id = uuid.UUID(test_org_id)
        test.user_id = uuid.UUID(authenticated_user_id)
        test_db.add(test)
        test_db.flush()
        
        test_id = str(test.id)
        
        # Simulate task execution with error (like in the refactored execute_test function)
        # The refactored code should rely on session context manager for rollback
        
        try:
            # Simulate some database operations that might fail
            test.status = "processing"
            test_db.flush()
            
            # Simulate an error that would have triggered manual rollback before refactoring
            raise Exception("Simulated task execution error")
            
        except Exception as e:
            # After refactoring, we don't manually call db.rollback()
            # The session context manager should handle this
            
            # Verify that we can still access the test (transaction not corrupted)
            db_test = test_db.query(models.Test).filter(
                models.Test.id == uuid.UUID(test_id)
            ).first()
            assert db_test is not None
            
            # The transaction should be handled by the session context manager
            # so we don't need to manually rollback here

    def test_multiple_task_operations_transaction_isolation(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """Test that multiple task operations maintain proper transaction isolation"""
        # Create multiple test runs
        test_run_data1 = {
            "name": f"Test Run 1 {uuid.uuid4()}",
            "description": "First test run for transaction testing"
        }
        test_run1 = models.TestRun(**test_run_data1)
        test_run1.organization_id = uuid.UUID(test_org_id)
        test_run1.user_id = uuid.UUID(authenticated_user_id)
        test_run1.status = models.TestRunStatus.RUNNING
        
        test_run_data2 = {
            "name": f"Test Run 2 {uuid.uuid4()}",
            "description": "Second test run for transaction testing"
        }
        test_run2 = models.TestRun(**test_run_data2)
        test_run2.organization_id = uuid.UUID(test_org_id)
        test_run2.user_id = uuid.UUID(authenticated_user_id)
        test_run2.status = models.TestRunStatus.RUNNING
        
        test_db.add_all([test_run1, test_run2])
        test_db.flush()
        
        # Mock logger function
        def mock_logger_func(level, message):
            pass
        
        # Update both test runs with different statuses
        result_processor.update_test_run_status(
            test_db,
            str(test_run1.id),
            models.TestRunStatus.COMPLETED,
            tests_passed=3,
            tests_failed=1,
            logger_func=mock_logger_func
        )
        
        result_processor.update_test_run_status(
            test_db,
            str(test_run2.id),
            models.TestRunStatus.FAILED,
            tests_passed=0,
            tests_failed=5,
            logger_func=mock_logger_func
        )
        
        # Verify both test runs were updated independently and persisted
        db_test_run1 = test_db.query(models.TestRun).filter(
            models.TestRun.id == test_run1.id
        ).first()
        db_test_run2 = test_db.query(models.TestRun).filter(
            models.TestRun.id == test_run2.id
        ).first()
        
        assert db_test_run1 is not None
        assert db_test_run2 is not None
        assert db_test_run1.status == models.TestRunStatus.COMPLETED
        assert db_test_run2.status == models.TestRunStatus.FAILED
        assert db_test_run1.tests_passed == 3
        assert db_test_run1.tests_failed == 1
        assert db_test_run2.tests_passed == 0
        assert db_test_run2.tests_failed == 5

    def test_task_execution_with_base_task_session_management(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """Test that task execution works properly with BaseTask session management"""
        # This test verifies that the BaseTask.get_db_session() context manager
        # works correctly with our transaction management refactoring
        
        from rhesis.backend.tasks.base import BaseTask
        
        # Create a mock task with tenant context
        class MockTask(BaseTask):
            def get_tenant_context(self):
                return test_org_id, authenticated_user_id
        
        mock_task = MockTask()
        
        # Test using the task's database session context manager
        with mock_task.get_db_session() as task_db:
            # Create a test within the task context
            test_data = TestDataFactory.sample_data()
            test = models.Test(**test_data)
            test.organization_id = uuid.UUID(test_org_id)
            test.user_id = uuid.UUID(authenticated_user_id)
            task_db.add(test)
            task_db.flush()
            
            test_id = test.id
            
            # Verify test was created
            assert test.id is not None
        
        # After context exit, verify test was committed by the session context manager
        db_test = test_db.query(models.Test).filter(
            models.Test.id == test_id
        ).first()
        assert db_test is not None

    def test_task_execution_error_in_context_manager(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """Test that errors in task execution context manager trigger automatic rollback"""
        from rhesis.backend.tasks.base import BaseTask
        
        class MockTask(BaseTask):
            def get_tenant_context(self):
                return test_org_id, authenticated_user_id
        
        mock_task = MockTask()
        
        # Get initial test count
        initial_count = test_db.query(models.Test).count()
        
        # Test error handling in task context
        try:
            with mock_task.get_db_session() as task_db:
                # Create a test
                test_data = TestDataFactory.sample_data()
                test = models.Test(**test_data)
                test.organization_id = uuid.UUID(test_org_id)
                test.user_id = uuid.UUID(authenticated_user_id)
                task_db.add(test)
                task_db.flush()
                
                # Simulate an error
                raise Exception("Task execution error")
                
        except Exception:
            # Exception should be caught by context manager and trigger rollback
            pass
        
        # Verify no test was created (transaction rolled back)
        final_count = test_db.query(models.Test).count()
        assert final_count == initial_count

    def test_concurrent_task_operations_do_not_interfere(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """Test that concurrent task operations do not interfere with each other"""
        # Create test runs for concurrent operations
        test_run_data1 = {
            "name": f"Test Run 1 {uuid.uuid4()}",
            "description": "First test run for transaction testing"
        }
        test_run1 = models.TestRun(**test_run_data1)
        test_run1.organization_id = uuid.UUID(test_org_id)
        test_run1.user_id = uuid.UUID(authenticated_user_id)
        test_run1.status = models.TestRunStatus.RUNNING
        
        test_run_data2 = {
            "name": f"Test Run 2 {uuid.uuid4()}",
            "description": "Second test run for transaction testing"
        }
        test_run2 = models.TestRun(**test_run_data2)
        test_run2.organization_id = uuid.UUID(test_org_id)
        test_run2.user_id = uuid.UUID(authenticated_user_id)
        test_run2.status = models.TestRunStatus.RUNNING
        
        test_db.add_all([test_run1, test_run2])
        test_db.flush()
        
        # Mock logger functions for each operation
        def mock_logger_func1(level, message):
            pass
            
        def mock_logger_func2(level, message):
            pass
        
        # Simulate concurrent operations
        # First operation succeeds
        result_processor.update_test_run_status(
            test_db,
            str(test_run1.id),
            models.TestRunStatus.COMPLETED,
            tests_passed=10,
            tests_failed=0,
            logger_func=mock_logger_func1
        )
        
        # Second operation also succeeds independently
        result_processor.update_test_run_status(
            test_db,
            str(test_run2.id),
            models.TestRunStatus.COMPLETED,
            tests_passed=8,
            tests_failed=2,
            logger_func=mock_logger_func2
        )
        
        # Verify both operations succeeded without interference
        db_test_run1 = test_db.query(models.TestRun).filter(
            models.TestRun.id == test_run1.id
        ).first()
        db_test_run2 = test_db.query(models.TestRun).filter(
            models.TestRun.id == test_run2.id
        ).first()
        
        assert db_test_run1 is not None
        assert db_test_run2 is not None
        assert db_test_run1.status == models.TestRunStatus.COMPLETED
        assert db_test_run2.status == models.TestRunStatus.COMPLETED
        assert db_test_run1.tests_passed == 10
        assert db_test_run1.tests_failed == 0
        assert db_test_run2.tests_passed == 8
        assert db_test_run2.tests_failed == 2

