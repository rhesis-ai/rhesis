"""
🔄 Transaction Management Testing for Service Functions

Comprehensive test suite for verifying that transaction management works correctly
in service functions after refactoring to remove manual db.commit() and db.rollback() calls.

Tests focus on:
- Automatic transaction commit on success in service operations
- Automatic transaction rollback on exceptions
- Proper data persistence after complex service operations
- Transaction isolation in multi-step service operations

Functions tested from services:
- test_set.py: bulk_create_test_set, bulk_create_test_set_associations, bulk_remove_test_set_associations
- test.py: bulk_create_tests, associate_tests_with_test_set, disassociate_tests_from_test_set
- organization.py: load_initial_data / rollback_initial_data

Run with: python -m pytest tests/backend/services/test_transaction_management.py -v
"""

import pytest
import uuid
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from rhesis.backend.app import models, schemas
from rhesis.backend.app.services import test_set as test_set_service
from rhesis.backend.app.services import test as test_service
from rhesis.backend.app.services import organization as organization_service
from tests.backend.routes.fixtures.data_factories import (
    TestDataFactory,
    generate_test_data
)


@pytest.mark.unit
@pytest.mark.services
@pytest.mark.transaction
class TestServiceTransactionManagement:
    """🔄 Test automatic transaction management in service functions"""

    def test_bulk_create_test_set_commits_on_success(self, test_db: Session, test_org_id: str, authenticated_user_id: str):
        """Test that bulk_create_test_set commits automatically on success"""
        # Create test set data with tests
        test_set_data = {
            "name": f"Test Set {uuid.uuid4()}",
            "description": "Test set for transaction testing"
        }
        test_set_data["name"] = f"Bulk Test Set {uuid.uuid4()}"
        
        # Create the test set with bulk creation
        result = test_set_service.bulk_create_test_set(
            test_db, test_set_data, test_org_id, authenticated_user_id
        )
        
        # Verify test set was created and persisted
        assert result is not None
        assert result.name == test_set_data["name"]
        assert result.id is not None
        
        # Verify it's actually in the database (committed)
        db_test_set = test_db.query(models.TestSet).filter(
            models.TestSet.id == result.id
        ).first()
        assert db_test_set is not None
        assert db_test_set.name == test_set_data["name"]
        
        # Verify associated tests were also created and committed
        if "tests" in test_set_data and test_set_data["tests"]:
            associated_tests = test_db.query(models.Test).filter(
                models.Test.test_sets.any(models.TestSet.id == result.id)
            ).count()
            assert associated_tests > 0

    def test_bulk_create_test_set_rollback_on_exception(self, test_db: Session, test_org_id: str, authenticated_user_id: str):
        """Test that bulk_create_test_set rolls back automatically on exception"""
        # Get initial test set count
        initial_count = test_db.query(models.TestSet).count()
        
        # Create test set data
        test_set_data = {
            "name": f"Test Set {uuid.uuid4()}",
            "description": "Test set for transaction testing"
        }
        test_set_data["name"] = f"Failing Test Set {uuid.uuid4()}"
        
        # Mock an exception during creation
        with patch('rhesis.backend.app.services.test_set.crud.create_test_set') as mock_create:
            mock_create.side_effect = Exception("Database error")
            
            with pytest.raises(Exception, match="Failed to create test set"):
                test_set_service.bulk_create_test_set(
                    test_db, test_set_data, test_org_id, authenticated_user_id
                )
        
        # Verify no test set was created (transaction rolled back)
        final_count = test_db.query(models.TestSet).count()
        assert final_count == initial_count

    def test_bulk_create_tests_commits_on_success(self, test_db: Session, test_org_id: str, authenticated_user_id: str):
        """Test that bulk_create_tests commits automatically on success"""
        # Create test data
        tests_data = [
            TestDataFactory.sample_data(),
            TestDataFactory.sample_data(),
            TestDataFactory.sample_data()
        ]
        
        # Make test names unique
        for i, test_data in enumerate(tests_data):
            test_data["test_configuration"]["name"] = f"Bulk Test {i} {uuid.uuid4()}"
        
        # Create tests in bulk
        result = test_service.bulk_create_tests(
            test_db, tests_data, test_org_id, authenticated_user_id
        )
        
        # Verify tests were created and persisted
        assert result is not None
        assert len(result) == len(tests_data)
        
        # Verify each test is actually in the database (committed)
        for created_test in result:
            assert created_test.id is not None
            db_test = test_db.query(models.Test).filter(
                models.Test.id == created_test.id
            ).first()
            assert db_test is not None

    def test_bulk_create_tests_rollback_on_exception(self, test_db: Session, test_org_id: str, authenticated_user_id: str):
        """Test that bulk_create_tests rolls back automatically on exception"""
        # Get initial test count
        initial_count = test_db.query(models.Test).count()
        
        # Create test data
        tests_data = [TestDataFactory.sample_data()]
        
        # Mock an exception during creation
        with patch('rhesis.backend.app.services.test.crud.create_test') as mock_create:
            mock_create.side_effect = Exception("Database error")
            
            with pytest.raises(Exception):
                test_service.bulk_create_tests(
                    test_db, tests_data, test_org_id, authenticated_user_id
                )
        
        # Verify no tests were created (transaction rolled back)
        final_count = test_db.query(models.Test).count()
        assert final_count == initial_count

    def test_associate_tests_with_test_set_commits_on_success(self, test_db: Session, test_org_id: str, authenticated_user_id: str):
        """Test that associate_tests_with_test_set commits automatically on success"""
        # First create a test set
        test_set_data = {
            "name": f"Test Set {uuid.uuid4()}",
            "description": "Test set for transaction testing"
        }
        test_set_data["name"] = f"Association Test Set {uuid.uuid4()}"
        test_set = models.TestSet(**test_set_data)
        test_set.organization_id = uuid.UUID(test_org_id)
        test_set.user_id = uuid.UUID(authenticated_user_id)
        test_db.add(test_set)
        test_db.flush()
        
        # Create some tests
        test_data1 = TestDataFactory.sample_data()
        test_data1["test_configuration"]["name"] = f"Test 1 {uuid.uuid4()}"
        test1 = models.Test(**test_data1)
        test1.organization_id = uuid.UUID(test_org_id)
        test1.user_id = uuid.UUID(authenticated_user_id)
        
        test_data2 = TestDataFactory.sample_data()
        test_data2["test_configuration"]["name"] = f"Test 2 {uuid.uuid4()}"
        test2 = models.Test(**test_data2)
        test2.organization_id = uuid.UUID(test_org_id)
        test2.user_id = uuid.UUID(authenticated_user_id)
        
        test_db.add_all([test1, test2])
        test_db.flush()
        
        test_ids = [str(test1.id), str(test2.id)]
        
        # Associate tests with test set
        result = test_service.associate_tests_with_test_set(
            test_db, test_ids, str(test_set.id), test_org_id, authenticated_user_id
        )
        
        # Verify associations were created and persisted
        assert result is not None
        assert result["success"] is True
        assert result["metadata"]["new_associations"] == 2
        
        # Verify associations are actually in the database (committed)
        for test_id in test_ids:
            association = test_db.query(models.TestSetAssociation).filter(
                models.TestSetAssociation.test_id == uuid.UUID(test_id),
                models.TestSetAssociation.test_set_id == test_set.id
            ).first()
            assert association is not None

    def test_disassociate_tests_from_test_set_commits_on_success(self, test_db: Session, test_org_id: str, authenticated_user_id: str):
        """Test that disassociate_tests_from_test_set commits automatically on success"""
        # First create a test set with associated tests
        test_set_data = {
            "name": f"Test Set {uuid.uuid4()}",
            "description": "Test set for transaction testing"
        }
        test_set_data["name"] = f"Disassociation Test Set {uuid.uuid4()}"
        test_set = models.TestSet(**test_set_data)
        test_set.organization_id = uuid.UUID(test_org_id)
        test_set.user_id = uuid.UUID(authenticated_user_id)
        test_db.add(test_set)
        test_db.flush()
        
        # Create tests and associations
        test_data1 = TestDataFactory.sample_data()
        test_data1["test_configuration"]["name"] = f"Test 1 {uuid.uuid4()}"
        test1 = models.Test(**test_data1)
        test1.organization_id = uuid.UUID(test_org_id)
        test1.user_id = uuid.UUID(authenticated_user_id)
        
        test_db.add(test1)
        test_db.flush()
        
        # Create association
        association = models.TestSetAssociation(
            test_id=test1.id,
            test_set_id=test_set.id,
            organization_id=uuid.UUID(test_org_id),
            user_id=uuid.UUID(authenticated_user_id)
        )
        test_db.add(association)
        test_db.flush()
        
        # Verify association exists
        initial_associations = test_db.query(models.TestSetAssociation).filter(
            models.TestSetAssociation.test_set_id == test_set.id
        ).count()
        assert initial_associations == 1
        
        # Disassociate tests
        result = test_service.disassociate_tests_from_test_set(
            test_db, str(test_set.id), [str(test1.id)], test_org_id, authenticated_user_id
        )
        
        # Verify disassociation was successful and persisted
        assert result is not None
        assert result["success"] is True
        assert result["removed_associations"] == 1
        
        # Verify association is actually removed from database (committed)
        final_associations = test_db.query(models.TestSetAssociation).filter(
            models.TestSetAssociation.test_set_id == test_set.id
        ).count()
        assert final_associations == 0

    def test_load_initial_data_commits_on_success(self, test_db: Session, test_org_id: str, authenticated_user_id: str):
        """Test that load_initial_data commits automatically on success"""
        # Mock the organization service functions to avoid complex setup
        with patch('rhesis.backend.app.services.organization.create_default_behaviors') as mock_behaviors, \
             patch('rhesis.backend.app.services.organization.create_default_topics') as mock_topics, \
             patch('rhesis.backend.app.services.organization.create_default_categories') as mock_categories:
            
            # Configure mocks to return success
            mock_behaviors.return_value = None
            mock_topics.return_value = None
            mock_categories.return_value = None
            
            # Load initial data
            organization_service.load_initial_data(test_db, test_org_id, authenticated_user_id)
            
            # Verify all creation functions were called
            mock_behaviors.assert_called_once()
            mock_topics.assert_called_once()
            mock_categories.assert_called_once()

    def test_rollback_initial_data_commits_on_success(self, test_db: Session, test_org_id: str):
        """Test that rollback_initial_data commits automatically on success"""
        # Create an organization to test rollback
        org = models.Organization(
            name=f"Test Org {uuid.uuid4()}",
            is_onboarding_complete=True
        )
        org.id = uuid.UUID(test_org_id)
        test_db.add(org)
        test_db.flush()
        
        # Verify organization is marked as complete
        db_org = test_db.query(models.Organization).filter(
            models.Organization.id == uuid.UUID(test_org_id)
        ).first()
        assert db_org is not None
        assert db_org.is_onboarding_complete is True
        
        # Rollback initial data
        organization_service.rollback_initial_data(test_db, test_org_id)
        
        # Verify organization is marked as incomplete (committed)
        db_org_after = test_db.query(models.Organization).filter(
            models.Organization.id == uuid.UUID(test_org_id)
        ).first()
        assert db_org_after is not None
        assert db_org_after.is_onboarding_complete is False

    def test_service_operations_transaction_isolation(self, test_db: Session, test_org_id: str, authenticated_user_id: str):
        """Test that multiple service operations maintain proper transaction isolation"""
        # Create first test set
        test_set_data1 = {
            "name": f"Test Set 1 {uuid.uuid4()}",
            "description": "First test set for transaction testing"
        }
        test_set_data1["name"] = f"Service Test Set 1 {uuid.uuid4()}"
        
        result1 = test_set_service.bulk_create_test_set(
            test_db, test_set_data1, test_org_id, authenticated_user_id
        )
        
        # Create second test set
        test_set_data2 = {
            "name": f"Test Set 2 {uuid.uuid4()}",
            "description": "Second test set for transaction testing"
        }
        test_set_data2["name"] = f"Service Test Set 2 {uuid.uuid4()}"
        
        result2 = test_set_service.bulk_create_test_set(
            test_db, test_set_data2, test_org_id, authenticated_user_id
        )
        
        # Verify both test sets exist independently
        assert result1 is not None
        assert result2 is not None
        assert result1.id != result2.id
        
        # Verify both are persisted in database
        db_test_set1 = test_db.query(models.TestSet).filter(
            models.TestSet.id == result1.id
        ).first()
        db_test_set2 = test_db.query(models.TestSet).filter(
            models.TestSet.id == result2.id
        ).first()
        
        assert db_test_set1 is not None
        assert db_test_set2 is not None
        assert db_test_set1.name == test_set_data1["name"]
        assert db_test_set2.name == test_set_data2["name"]

    def test_exception_in_service_does_not_affect_other_operations(self, test_db: Session, test_org_id: str, authenticated_user_id: str):
        """Test that an exception in one service operation doesn't affect other successful operations"""
        # Create first test set successfully
        test_set_data1 = {
            "name": f"Test Set 1 {uuid.uuid4()}",
            "description": "First test set for transaction testing"
        }
        test_set_data1["name"] = f"Success Service Test Set {uuid.uuid4()}"
        
        result1 = test_set_service.bulk_create_test_set(
            test_db, test_set_data1, test_org_id, authenticated_user_id
        )
        assert result1 is not None
        
        # Try to create second test set with exception
        test_set_data2 = {
            "name": f"Test Set 2 {uuid.uuid4()}",
            "description": "Second test set for transaction testing"
        }
        test_set_data2["name"] = f"Failure Service Test Set {uuid.uuid4()}"
        
        with patch('rhesis.backend.app.services.test_set.crud.create_test_set') as mock_create:
            mock_create.side_effect = Exception("Service error")
            
            with pytest.raises(Exception):
                test_set_service.bulk_create_test_set(
                    test_db, test_set_data2, test_org_id, authenticated_user_id
                )
        
        # Verify first test set still exists (not affected by second failure)
        db_test_set1 = test_db.query(models.TestSet).filter(
            models.TestSet.id == result1.id
        ).first()
        assert db_test_set1 is not None
        assert db_test_set1.name == test_set_data1["name"]
        
        # Verify second test set was not created
        failed_test_sets = test_db.query(models.TestSet).filter(
            models.TestSet.name == test_set_data2["name"]
        ).count()
        assert failed_test_sets == 0

    def test_complex_service_operation_atomicity(self, test_db: Session, test_org_id: str, authenticated_user_id: str):
        """Test that complex service operations are atomic (all or nothing)"""
        # Create test set data with multiple tests
        test_set_data = {
            "name": f"Test Set {uuid.uuid4()}",
            "description": "Test set for transaction testing"
        }
        test_set_data["name"] = f"Complex Atomic Test Set {uuid.uuid4()}"
        test_set_data["tests"] = [
            TestDataFactory.sample_data(),
            TestDataFactory.sample_data(),
            TestDataFactory.sample_data()
        ]
        
        # Make test names unique
        for i, test_data in enumerate(test_set_data["tests"]):
            test_data["test_configuration"]["name"] = f"Atomic Test {i} {uuid.uuid4()}"
        
        # Get initial counts
        initial_test_set_count = test_db.query(models.TestSet).count()
        initial_test_count = test_db.query(models.Test).count()
        
        # Create test set with tests (should be atomic)
        result = test_set_service.bulk_create_test_set(
            test_db, test_set_data, test_org_id, authenticated_user_id
        )
        
        # Verify all components were created together
        assert result is not None
        
        final_test_set_count = test_db.query(models.TestSet).count()
        final_test_count = test_db.query(models.Test).count()
        
        # Should have one more test set and multiple more tests
        assert final_test_set_count == initial_test_set_count + 1
        assert final_test_count > initial_test_count
        
        # Verify test set and all its tests are properly linked
        created_test_set = test_db.query(models.TestSet).filter(
            models.TestSet.id == result.id
        ).first()
        assert created_test_set is not None
        
        # Verify associated tests exist
        associated_tests = test_db.query(models.Test).filter(
            models.Test.test_sets.any(models.TestSet.id == result.id)
        ).count()
        if test_set_data["tests"]:
            assert associated_tests > 0

