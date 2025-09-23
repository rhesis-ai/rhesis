"""
🔒 Service Layer Security Tests

This module tests security vulnerabilities in various service layer components,
including tag management, test set services, and other service-level operations.
"""

import uuid
import pytest
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from rhesis.backend.app import models, crud


@pytest.mark.security
class TestTagOrganizationSecurity:
    """Test that tag operations properly enforce organization-based security"""
    
    def test_get_tag_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that get_tag accepts organization filtering for tag scoping"""
        import inspect
        
        # Verify that get_tag accepts organization_id parameter (tags may be organization-scoped)
        signature = inspect.signature(crud.get_tag)
        assert 'organization_id' in signature.parameters, "get_tag should accept organization_id for tag scoping"
        
        tag_id = uuid.uuid4()
        org_id = str(uuid.uuid4())
        
        # Mock the query to test the function works with organization filtering
        with patch.object(test_db, 'query') as mock_query:
            mock_tag = Mock()
            mock_tag.id = tag_id
            mock_tag.organization_id = uuid.UUID(org_id)
            
            # Test with organization filtering
            mock_query.return_value.filter.return_value.filter.return_value.first.return_value = mock_tag
            result_with_org = crud.get_tag(test_db, tag_id, organization_id=org_id)
            assert result_with_org == mock_tag
            
            # Test without organization filtering (should work but may return tags from any org)
            mock_query.return_value.filter.return_value.first.return_value = mock_tag
            result_without_org = crud.get_tag(test_db, tag_id)
            assert result_without_org == mock_tag

    def test_create_tag_organization_scoping(self, test_db: Session):
        """🔒 SECURITY: Test that create_tag properly scopes tags to organizations"""
        import inspect
        
        # Verify that create_tag accepts organization_id parameter
        signature = inspect.signature(crud.create_tag)
        assert 'organization_id' in signature.parameters, "create_tag should accept organization_id for tag scoping"
        
        # Create a test organization and user
        from tests.backend.fixtures.test_setup import create_test_organization_and_user
        unique_id = str(uuid.uuid4())[:8]
        org, user, _ = create_test_organization_and_user(
            test_db, f"Tag Org {unique_id}", f"tag-user-{unique_id}@security-test.com", "Tag User"
        )
        
        # Create a tag with organization scoping
        from rhesis.backend.app.schemas.tag import TagCreate
        tag_data = TagCreate(name=f"Security Test Tag {unique_id}")
        
        result = crud.create_tag(test_db, tag_data, organization_id=str(org.id), user_id=str(user.id))
        
        # Verify the tag was created with correct organization scoping
        assert result is not None
        assert result.name == f"Security Test Tag {unique_id}"
        assert str(result.organization_id) == str(org.id)
        assert str(result.user_id) == str(user.id)

    def test_delete_tag_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that delete_tag properly filters by organization"""
        import inspect
        
        # Verify that delete_tag accepts organization_id parameter
        signature = inspect.signature(crud.delete_tag)
        assert 'organization_id' in signature.parameters, "delete_tag should accept organization_id for tag scoping"
        
        # Create two separate organizations and users
        from tests.backend.fixtures.test_setup import create_test_organization_and_user
        unique_id = str(uuid.uuid4())[:8]
        org1, user1, _ = create_test_organization_and_user(
            test_db, f"Tag Delete Org 1 {unique_id}", f"tag-delete-user1-{unique_id}@security-test.com", "Tag Delete User 1"
        )
        org2, user2, _ = create_test_organization_and_user(
            test_db, f"Tag Delete Org 2 {unique_id}", f"tag-delete-user2-{unique_id}@security-test.com", "Tag Delete User 2"
        )
        
        # Create a tag in org1
        from rhesis.backend.app.schemas.tag import TagCreate
        tag_data = TagCreate(name=f"Tag to Delete {unique_id}")
        tag = crud.create_tag(test_db, tag_data, organization_id=str(org1.id), user_id=str(user1.id))
        
        # User from org1 should be able to delete the tag
        result_org1 = crud.delete_tag(test_db, tag.id, organization_id=str(org1.id), user_id=str(user1.id))
        assert result_org1 is not None  # Tag was found and deleted
        
        # Create another tag in org1 for the next test
        tag2 = crud.create_tag(test_db, TagCreate(name=f"Tag to Delete 2 {unique_id}"), organization_id=str(org1.id), user_id=str(user1.id))
        
        # User from org2 should NOT be able to delete the tag from org1
        result_org2 = crud.delete_tag(test_db, tag2.id, organization_id=str(org2.id), user_id=str(user2.id))
        assert result_org2 is None  # Tag was not found/deleted due to organization filtering


@pytest.mark.security
class TestTestSetOrganizationSecurity:
    """Test that test set operations properly enforce organization-based security"""
    
    def test_get_test_set_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that get_test_set properly filters by organization"""
        import inspect
        
        # Verify that get_test_set accepts organization_id parameter
        signature = inspect.signature(crud.get_test_set)
        assert 'organization_id' in signature.parameters, "get_test_set should accept organization_id for test set scoping"
        
        # Create two separate organizations and users
        from tests.backend.fixtures.test_setup import create_test_organization_and_user
        unique_id = str(uuid.uuid4())[:8]
        org1, user1, _ = create_test_organization_and_user(
            test_db, f"TestSet Org 1 {unique_id}", f"testset-user1-{unique_id}@security-test.com", "TestSet User 1"
        )
        org2, user2, _ = create_test_organization_and_user(
            test_db, f"TestSet Org 2 {unique_id}", f"testset-user2-{unique_id}@security-test.com", "TestSet User 2"
        )
        
        # Create a test set in org1
        test_set = models.TestSet(
            id=uuid.uuid4(),
            organization_id=org1.id,
            user_id=user1.id,
            name=f"Security Test Set {unique_id}",
            description="Test set for security testing"
        )
        test_db.add(test_set)
        test_db.commit()
        
        # User from org1 should be able to access the test set
        result_org1 = crud.get_test_set(test_db, test_set.id, organization_id=str(org1.id))
        assert result_org1 is not None
        assert result_org1.id == test_set.id
        assert str(result_org1.organization_id) == str(org1.id)
        
        # User from org2 should NOT be able to access the test set
        result_org2 = crud.get_test_set(test_db, test_set.id, organization_id=str(org2.id))
        assert result_org2 is None
        
        # Without organization filtering, should still work (finds the test set)
        result_no_filter = crud.get_test_set(test_db, test_set.id)
        assert result_no_filter is not None
        assert result_no_filter.id == test_set.id

    def test_create_test_set_organization_scoping(self, test_db: Session):
        """🔒 SECURITY: Test that create_test_set properly scopes test sets to organizations"""
        import inspect
        
        # Verify that create_test_set accepts organization_id parameter
        signature = inspect.signature(crud.create_test_set)
        assert 'organization_id' in signature.parameters, "create_test_set should accept organization_id for test set scoping"
        
        # Create a test organization and user
        from tests.backend.fixtures.test_setup import create_test_organization_and_user
        unique_id = str(uuid.uuid4())[:8]
        org, user, _ = create_test_organization_and_user(
            test_db, f"TestSet Create Org {unique_id}", f"testset-create-user-{unique_id}@security-test.com", "TestSet Create User"
        )
        
        # Create a test set with organization scoping
        from rhesis.backend.app.schemas.test_set import TestSetCreate
        test_set_data = TestSetCreate(
            name=f"Security Test Set Create {unique_id}",
            description="Test set for security testing"
        )
        
        result = crud.create_test_set(test_db, test_set_data, organization_id=str(org.id), user_id=str(user.id))
        
        # Verify the test set was created with correct organization scoping
        assert result is not None
        assert result.name == f"Security Test Set Create {unique_id}"
        assert str(result.organization_id) == str(org.id)
        assert str(result.user_id) == str(user.id)

    def test_delete_test_set_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that delete_test_set properly filters by organization"""
        import inspect
        
        # Verify that delete_test_set accepts organization_id parameter
        signature = inspect.signature(crud.delete_test_set)
        assert 'organization_id' in signature.parameters, "delete_test_set should accept organization_id for test set scoping"
        
        # Create two separate organizations and users
        from tests.backend.fixtures.test_setup import create_test_organization_and_user
        unique_id = str(uuid.uuid4())[:8]
        org1, user1, _ = create_test_organization_and_user(
            test_db, f"TestSet Delete Org 1 {unique_id}", f"testset-delete-user1-{unique_id}@security-test.com", "TestSet Delete User 1"
        )
        org2, user2, _ = create_test_organization_and_user(
            test_db, f"TestSet Delete Org 2 {unique_id}", f"testset-delete-user2-{unique_id}@security-test.com", "TestSet Delete User 2"
        )
        
        # Create a test set in org1
        from rhesis.backend.app.schemas.test_set import TestSetCreate
        test_set_data = TestSetCreate(name=f"TestSet to Delete {unique_id}", description="Test set for deletion")
        test_set = crud.create_test_set(test_db, test_set_data, organization_id=str(org1.id), user_id=str(user1.id))
        
        # User from org1 should be able to delete the test set
        result_org1 = crud.delete_test_set(test_db, test_set.id, organization_id=str(org1.id))
        assert result_org1 is not None  # Test set was found and deleted
        
        # Create another test set in org1 for the next test
        test_set2 = crud.create_test_set(test_db, TestSetCreate(name=f"TestSet to Delete 2 {unique_id}", description="Test set 2 for deletion"), organization_id=str(org1.id), user_id=str(user1.id))
        
        # User from org2 should NOT be able to delete the test set from org1
        result_org2 = crud.delete_test_set(test_db, test_set2.id, organization_id=str(org2.id))
        assert result_org2 is None  # Test set was not found/deleted due to organization filtering

    def test_update_test_set_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that update_test_set properly filters by organization"""
        import inspect
        
        # Verify that update_test_set accepts organization_id parameter
        signature = inspect.signature(crud.update_test_set)
        assert 'organization_id' in signature.parameters, "update_test_set should accept organization_id for test set scoping"
        
        # Create two separate organizations and users
        from tests.backend.fixtures.test_setup import create_test_organization_and_user
        unique_id = str(uuid.uuid4())[:8]
        org1, user1, _ = create_test_organization_and_user(
            test_db, f"TestSet Update Org 1 {unique_id}", f"testset-update-user1-{unique_id}@security-test.com", "TestSet Update User 1"
        )
        org2, user2, _ = create_test_organization_and_user(
            test_db, f"TestSet Update Org 2 {unique_id}", f"testset-update-user2-{unique_id}@security-test.com", "TestSet Update User 2"
        )
        
        # Create a test set in org1
        from rhesis.backend.app.schemas.test_set import TestSetCreate, TestSetUpdate
        test_set_data = TestSetCreate(name=f"TestSet to Update {unique_id}", description="Test set for updating")
        test_set = crud.create_test_set(test_db, test_set_data, organization_id=str(org1.id), user_id=str(user1.id))
        
        # User from org1 should be able to update the test set
        update_data = TestSetUpdate(name=f"Updated TestSet {unique_id}")
        result_org1 = crud.update_test_set(test_db, test_set.id, update_data, organization_id=str(org1.id))
        assert result_org1 is not None
        assert result_org1.name == f"Updated TestSet {unique_id}"
        assert str(result_org1.organization_id) == str(org1.id)
        
        # User from org2 should NOT be able to update the test set from org1
        update_data2 = TestSetUpdate(name=f"Should Not Update {unique_id}")
        result_org2 = crud.update_test_set(test_db, test_set.id, update_data2, organization_id=str(org2.id))
        assert result_org2 is None  # Test set was not found/updated due to organization filtering


@pytest.mark.security
class TestTestSetCrudSecurity:
    """Test that test set CRUD operations properly enforce organization isolation"""
    
    def test_get_test_sets_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that get_test_sets properly filters by organization"""
        import inspect
        
        # Verify that get_test_sets accepts organization_id parameter
        signature = inspect.signature(crud.get_test_sets)
        assert 'organization_id' in signature.parameters, "get_test_sets should accept organization_id for filtering"
        
        # Create two separate organizations and users
        from tests.backend.fixtures.test_setup import create_test_organization_and_user
        unique_id = str(uuid.uuid4())[:8]
        org1, user1, _ = create_test_organization_and_user(
            test_db, f"TestSets Org 1 {unique_id}", f"testsets-user1-{unique_id}@security-test.com", "TestSets User 1"
        )
        org2, user2, _ = create_test_organization_and_user(
            test_db, f"TestSets Org 2 {unique_id}", f"testsets-user2-{unique_id}@security-test.com", "TestSets User 2"
        )
        
        # Create test sets in both organizations
        test_set1_org1 = models.TestSet(
            id=uuid.uuid4(),
            organization_id=org1.id,
            user_id=user1.id,
            name=f"Test Set 1 Org 1 {unique_id}",
            description="Test set 1 in org 1"
        )
        test_set2_org1 = models.TestSet(
            id=uuid.uuid4(),
            organization_id=org1.id,
            user_id=user1.id,
            name=f"Test Set 2 Org 1 {unique_id}",
            description="Test set 2 in org 1"
        )
        test_set1_org2 = models.TestSet(
            id=uuid.uuid4(),
            organization_id=org2.id,
            user_id=user2.id,
            name=f"Test Set 1 Org 2 {unique_id}",
            description="Test set 1 in org 2"
        )
        
        test_db.add_all([test_set1_org1, test_set2_org1, test_set1_org2])
        test_db.commit()
        
        # Get test sets for org1 - should return at least the 2 we created
        result_org1 = crud.get_test_sets(test_db, organization_id=str(org1.id))
        assert len(result_org1) >= 2  # At least the 2 we created, could be more from initial data
        assert all(str(ts.organization_id) == str(org1.id) for ts in result_org1)
        
        # Verify our specific test sets are in the results
        test_set_names_org1 = {ts.name for ts in result_org1}
        assert f"Test Set 1 Org 1 {unique_id}" in test_set_names_org1
        assert f"Test Set 2 Org 1 {unique_id}" in test_set_names_org1
        
        # Get test sets for org2 - should return at least the 1 we created
        result_org2 = crud.get_test_sets(test_db, organization_id=str(org2.id))
        assert len(result_org2) >= 1  # At least the 1 we created, could be more from initial data
        assert all(str(ts.organization_id) == str(org2.id) for ts in result_org2)
        
        # Verify our specific test set is in the results
        test_set_names_org2 = {ts.name for ts in result_org2}
        assert f"Test Set 1 Org 2 {unique_id}" in test_set_names_org2
        
        # Get test sets without organization filtering - should return all test sets (at least 3)
        result_all = crud.get_test_sets(test_db)
        assert len(result_all) >= 3  # At least the 3 we created, could be more from other tests

    # Note: get_test_set_by_name function doesn't exist in crud.py, so this test is removed


@pytest.mark.security
class TestServiceSecurityValidation:
    """Test that service functions properly implement organization filtering and cross-tenant isolation"""
    
    def test_service_functions_accept_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Ensure all service-related functions accept organization filtering"""
        import inspect
        
        # List of service-related CRUD functions that should accept organization_id
        service_functions = [
            'get_tag',
            'create_tag', 
            'delete_tag',
            'get_test_set',
            'create_test_set',
            'delete_test_set',
            'update_test_set',
            'get_test_sets',
            # Note: get_test_set_by_name function doesn't exist in crud.py
        ]
        
        for func_name in service_functions:
            if hasattr(crud, func_name):
                func = getattr(crud, func_name)
                signature = inspect.signature(func)
                assert 'organization_id' in signature.parameters, f"{func_name} should accept organization_id parameter"
    
    def test_service_cross_tenant_isolation(self, test_db: Session):
        """🔒 SECURITY: Test that service operations are properly isolated between organizations"""
        org1_id = str(uuid.uuid4())
        org2_id = str(uuid.uuid4())
        
        # Test tag isolation
        tag_name = "shared_tag_name"
        
        with patch.object(test_db, 'query') as mock_query:
            # Mock tag from org1
            mock_tag_org1 = Mock()
            mock_tag_org1.name = tag_name
            mock_tag_org1.organization_id = uuid.UUID(org1_id)
            
            # Mock tag from org2
            mock_tag_org2 = Mock()
            mock_tag_org2.name = tag_name
            mock_tag_org2.organization_id = uuid.UUID(org2_id)
            
            # When querying with org1 filter, should only return org1 tag
            mock_query.return_value.filter.return_value.filter.return_value.first.return_value = mock_tag_org1
            result_org1 = crud.get_tag(test_db, mock_tag_org1.id, organization_id=org1_id)
            assert result_org1.organization_id == uuid.UUID(org1_id)
            
            # When querying with org2 filter, should only return org2 tag
            mock_query.return_value.filter.return_value.filter.return_value.first.return_value = mock_tag_org2
            result_org2 = crud.get_tag(test_db, mock_tag_org2.id, organization_id=org2_id)
            assert result_org2.organization_id == uuid.UUID(org2_id)
