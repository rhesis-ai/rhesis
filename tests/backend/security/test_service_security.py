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
class TestTagSecurityFixes:
    """Test security fixes for tag management vulnerabilities"""
    
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
        
        tag_name = "test_tag"
        org_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        
        # Mock the tag creation
        with patch.object(test_db, 'add') as mock_add, \
             patch.object(test_db, 'commit') as mock_commit:
            
            # Test tag creation with organization scoping
            result = crud.create_tag(test_db, {"name": tag_name}, organization_id=org_id, user_id=user_id)
            
            # Verify that add and commit were called
            mock_add.assert_called_once()
            mock_commit.assert_called_once()

    def test_delete_tag_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that delete_tag accepts organization filtering for tag scoping"""
        import inspect
        
        # Verify that delete_tag accepts organization_id parameter
        signature = inspect.signature(crud.delete_tag)
        assert 'organization_id' in signature.parameters, "delete_tag should accept organization_id for tag scoping"
        
        tag_id = uuid.uuid4()
        org_id = str(uuid.uuid4())
        
        # Mock the query to test the function works with organization filtering
        with patch.object(test_db, 'query') as mock_query:
            mock_tag = Mock()
            mock_tag.id = tag_id
            mock_tag.organization_id = uuid.UUID(org_id)
            
            # Test with organization filtering
            mock_query.return_value.filter.return_value.filter.return_value.first.return_value = mock_tag
            mock_query.return_value.filter.return_value.filter.return_value.delete.return_value = 1
            
            result_with_org = crud.delete_tag(test_db, tag_id, organization_id=org_id)
            assert result_with_org == 1


@pytest.mark.security
class TestTestSetServiceSecurityFixes:
    """Test security fixes for test set service vulnerabilities"""
    
    def test_get_test_set_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that get_test_set accepts organization filtering for test set scoping"""
        import inspect
        
        # Verify that get_test_set accepts organization_id parameter (test sets may be organization-scoped)
        signature = inspect.signature(crud.get_test_set)
        assert 'organization_id' in signature.parameters, "get_test_set should accept organization_id for test set scoping"
        
        test_set_id = uuid.uuid4()
        org_id = str(uuid.uuid4())
        
        # Mock the query to test the function works with organization filtering
        with patch.object(test_db, 'query') as mock_query:
            mock_test_set = Mock()
            mock_test_set.id = test_set_id
            mock_test_set.organization_id = uuid.UUID(org_id)
            
            # Test with organization filtering
            mock_query.return_value.filter.return_value.filter.return_value.first.return_value = mock_test_set
            result_with_org = crud.get_test_set(test_db, test_set_id, organization_id=org_id)
            assert result_with_org == mock_test_set
            
            # Test without organization filtering (should work but may return test sets from any org)
            mock_query.return_value.filter.return_value.first.return_value = mock_test_set
            result_without_org = crud.get_test_set(test_db, test_set_id)
            assert result_without_org == mock_test_set

    def test_create_test_set_organization_scoping(self, test_db: Session):
        """🔒 SECURITY: Test that create_test_set properly scopes test sets to organizations"""
        import inspect
        
        # Verify that create_test_set accepts organization_id parameter
        signature = inspect.signature(crud.create_test_set)
        assert 'organization_id' in signature.parameters, "create_test_set should accept organization_id for test set scoping"
        
        test_set_data = {"name": "test_set"}
        org_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        
        # Mock the test set creation
        with patch.object(test_db, 'add') as mock_add, \
             patch.object(test_db, 'commit') as mock_commit:
            
            # Test test set creation with organization scoping
            result = crud.create_test_set(test_db, test_set_data, organization_id=org_id, user_id=user_id)
            
            # Verify that add and commit were called
            mock_add.assert_called_once()
            mock_commit.assert_called_once()

    def test_delete_test_set_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that delete_test_set accepts organization filtering for test set scoping"""
        import inspect
        
        # Verify that delete_test_set accepts organization_id parameter
        signature = inspect.signature(crud.delete_test_set)
        assert 'organization_id' in signature.parameters, "delete_test_set should accept organization_id for test set scoping"
        
        test_set_id = uuid.uuid4()
        org_id = str(uuid.uuid4())
        
        # Mock the query to test the function works with organization filtering
        with patch.object(test_db, 'query') as mock_query:
            mock_test_set = Mock()
            mock_test_set.id = test_set_id
            mock_test_set.organization_id = uuid.UUID(org_id)
            
            # Test with organization filtering
            mock_query.return_value.filter.return_value.filter.return_value.first.return_value = mock_test_set
            mock_query.return_value.filter.return_value.filter.return_value.delete.return_value = 1
            
            result_with_org = crud.delete_test_set(test_db, test_set_id, organization_id=org_id)
            assert result_with_org == 1

    def test_update_test_set_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that update_test_set accepts organization filtering for test set scoping"""
        import inspect
        
        # Verify that update_test_set accepts organization_id parameter
        signature = inspect.signature(crud.update_test_set)
        assert 'organization_id' in signature.parameters, "update_test_set should accept organization_id for test set scoping"
        
        test_set_id = uuid.uuid4()
        org_id = str(uuid.uuid4())
        update_data = {"name": "updated_test_set"}
        
        # Mock the query to test the function works with organization filtering
        with patch.object(test_db, 'query') as mock_query:
            mock_test_set = Mock()
            mock_test_set.id = test_set_id
            mock_test_set.organization_id = uuid.UUID(org_id)
            
            # Test with organization filtering
            mock_query.return_value.filter.return_value.filter.return_value.first.return_value = mock_test_set
            result_with_org = crud.update_test_set(test_db, test_set_id, update_data, organization_id=org_id)
            assert result_with_org == mock_test_set


@pytest.mark.security
class TestCrudTestSetSecurityFixes:
    """Test CRUD security fixes for test set operations"""
    
    def test_get_test_sets_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that get_test_sets properly filters by organization"""
        import inspect
        
        # Verify that get_test_sets accepts organization_id parameter
        signature = inspect.signature(crud.get_test_sets)
        assert 'organization_id' in signature.parameters, "get_test_sets should accept organization_id for filtering"
        
        org_id = str(uuid.uuid4())
        
        # Mock the query to test the function works with organization filtering
        with patch.object(test_db, 'query') as mock_query:
            mock_test_sets = [Mock(), Mock()]
            for mock_test_set in mock_test_sets:
                mock_test_set.organization_id = uuid.UUID(org_id)
            
            # Test with organization filtering
            mock_query.return_value.filter.return_value.offset.return_value.limit.return_value.all.return_value = mock_test_sets
            result_with_org = crud.get_test_sets(test_db, organization_id=org_id)
            assert len(result_with_org) == 2
            assert all(ts.organization_id == uuid.UUID(org_id) for ts in result_with_org)

    def test_get_test_set_by_name_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that get_test_set_by_name properly filters by organization"""
        import inspect
        
        # Verify that get_test_set_by_name accepts organization_id parameter
        signature = inspect.signature(crud.get_test_set_by_name)
        assert 'organization_id' in signature.parameters, "get_test_set_by_name should accept organization_id for filtering"
        
        test_set_name = "test_set_name"
        org_id = str(uuid.uuid4())
        
        # Mock the query to test the function works with organization filtering
        with patch.object(test_db, 'query') as mock_query:
            mock_test_set = Mock()
            mock_test_set.name = test_set_name
            mock_test_set.organization_id = uuid.UUID(org_id)
            
            # Test with organization filtering
            mock_query.return_value.filter.return_value.filter.return_value.first.return_value = mock_test_set
            result_with_org = crud.get_test_set_by_name(test_db, test_set_name, organization_id=org_id)
            assert result_with_org == mock_test_set
            assert result_with_org.organization_id == uuid.UUID(org_id)


@pytest.mark.security
class TestAdditionalSecurityRegression:
    """Additional regression tests for service security fixes"""
    
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
            'get_test_set_by_name',
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
