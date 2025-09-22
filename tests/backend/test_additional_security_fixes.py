"""
Additional security tests for the latest vulnerability fixes.

This module tests the additional security vulnerabilities that were
identified and fixed in the continued security improvement effort.
"""

import uuid
import pytest
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from rhesis.backend.app import models, crud


class TestTokenSecurityFixes:
    """Test security fixes for token management vulnerabilities"""
    
    def test_revoke_user_tokens_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that revoke_user_tokens properly filters by organization"""
        # Create two organizations
        org1_id = str(uuid.uuid4())
        org2_id = str(uuid.uuid4())
        
        org1 = models.Organization(id=uuid.UUID(org1_id), name="Org 1")
        org2 = models.Organization(id=uuid.UUID(org2_id), name="Org 2")
        test_db.add_all([org1, org2])
        test_db.flush()
        
        user_id = uuid.uuid4()
        
        # Mock the query to test organization filtering
        with patch.object(test_db, 'query') as mock_query:
            mock_query.return_value.filter.return_value.filter.return_value.delete.return_value = 2
            
            # Call revoke_user_tokens with organization filtering
            result = crud.revoke_user_tokens(test_db, user_id, organization_id=org1_id)
            
            # Verify organization filtering was applied
            mock_query.assert_called_with(models.Token)
            filter_calls = mock_query.return_value.filter.call_args_list
            
            # Should have been called with user_id filter first
            assert filter_calls[0][0][0].compare(models.Token.user_id == user_id)
            
            # Should have been called with organization_id filter second
            assert filter_calls[1][0][0].compare(models.Token.organization_id == uuid.UUID(org1_id))

    def test_get_token_by_value_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that get_token_by_value properly filters by organization"""
        # Create two organizations
        org1_id = str(uuid.uuid4())
        org2_id = str(uuid.uuid4())
        
        org1 = models.Organization(id=uuid.UUID(org1_id), name="Org 1")
        org2 = models.Organization(id=uuid.UUID(org2_id), name="Org 2")
        test_db.add_all([org1, org2])
        test_db.flush()
        
        token_value = "test-token-123"
        
        # Mock the query to test organization filtering
        with patch.object(test_db, 'query') as mock_query:
            mock_token = Mock()
            mock_token.organization_id = uuid.UUID(org1_id)
            mock_query.return_value.filter.return_value.filter.return_value.first.return_value = mock_token
            
            # Call get_token_by_value with organization filtering
            result = crud.get_token_by_value(test_db, token_value, organization_id=org1_id)
            
            # Verify organization filtering was applied
            mock_query.assert_called_with(models.Token)
            filter_calls = mock_query.return_value.filter.call_args_list
            
            # Should have been called with token value filter first
            assert filter_calls[0][0][0].compare(models.Token.token == token_value)
            
            # Should have been called with organization_id filter second
            assert filter_calls[1][0][0].compare(models.Token.organization_id == uuid.UUID(org1_id))
            
            assert result == mock_token


class TestTagSecurityFixes:
    """Test security fixes for tag assignment vulnerabilities"""
    
    def test_assign_tag_entity_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that assign_tag properly filters entity by organization"""
        # Create two organizations
        org1_id = str(uuid.uuid4())
        org2_id = str(uuid.uuid4())
        
        org1 = models.Organization(id=uuid.UUID(org1_id), name="Org 1")
        org2 = models.Organization(id=uuid.UUID(org2_id), name="Org 2")
        test_db.add_all([org1, org2])
        test_db.flush()
        
        entity_id = uuid.uuid4()
        
        # Mock the entity query to test organization filtering
        with patch.object(test_db, 'query') as mock_query:
            # Simulate entity not found due to organization filtering
            mock_query.return_value.filter.return_value.filter.return_value.first.return_value = None
            
            from rhesis.backend.app import schemas
            tag_data = schemas.TagCreate(name="test-tag", organization_id=uuid.UUID(org1_id))
            
            # Try to assign tag - should fail due to entity not found
            with pytest.raises(ValueError, match="not found or not accessible"):
                crud.assign_tag(
                    db=test_db,
                    tag=tag_data,
                    entity_id=entity_id,
                    entity_type="Test",
                    organization_id=org2_id  # Different organization
                )


class TestTestSetServiceSecurityFixes:
    """Test security fixes for test set service vulnerabilities"""
    
    def test_get_test_set_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that get_test_set service properly filters by organization"""
        from rhesis.backend.app.services.test_set import get_test_set
        
        # Create two organizations
        org1_id = str(uuid.uuid4())
        org2_id = str(uuid.uuid4())
        
        org1 = models.Organization(id=uuid.UUID(org1_id), name="Org 1")
        org2 = models.Organization(id=uuid.UUID(org2_id), name="Org 2")
        test_db.add_all([org1, org2])
        test_db.flush()
        
        test_set_id = uuid.uuid4()
        
        # Mock the query to test organization filtering
        with patch.object(test_db, 'query') as mock_query:
            # Simulate test set not found due to organization filtering
            mock_query.return_value.filter.return_value.filter.return_value.options.return_value.first.return_value = None
            
            # Try to get test set from different organization - should return None
            result = get_test_set(test_db, test_set_id, organization_id=org2_id)
            
            # Verify organization filtering was applied
            mock_query.assert_called()
            filter_calls = mock_query.return_value.filter.call_args_list
            
            # Should have been called with test_set_id filter first
            # Should have been called with organization_id filter second
            assert len(filter_calls) >= 2
            
            assert result is None

    def test_update_test_set_attributes_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that update_test_set_attributes properly filters by organization"""
        from rhesis.backend.app.services.test_set import update_test_set_attributes
        
        # Create two organizations
        org1_id = str(uuid.uuid4())
        org2_id = str(uuid.uuid4())
        
        org1 = models.Organization(id=uuid.UUID(org1_id), name="Org 1")
        org2 = models.Organization(id=uuid.UUID(org2_id), name="Org 2")
        test_db.add_all([org1, org2])
        test_db.flush()
        
        test_set_id = str(uuid.uuid4())
        
        # Mock the query to test organization filtering
        with patch.object(test_db, 'query') as mock_query:
            # Simulate test set not found due to organization filtering
            mock_query.return_value.options.return_value.filter.return_value.filter.return_value.first.return_value = None
            
            # Try to update test set from different organization - should raise ValueError
            with pytest.raises(ValueError, match="not found"):
                update_test_set_attributes(test_db, test_set_id, organization_id=org2_id)


class TestCrudTestSetSecurityFixes:
    """Test security fixes for CRUD test set vulnerabilities"""
    
    def test_get_test_sets_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that get_test_sets CRUD properly accepts organization filtering"""
        # Test that the function accepts organization_id parameter
        import inspect
        
        signature = inspect.signature(crud.get_test_sets)
        assert 'organization_id' in signature.parameters, "get_test_sets should accept organization_id parameter"
        
        # Test that it can be called with organization_id
        org_id = str(uuid.uuid4())
        
        # Mock the QueryBuilder to test organization filtering
        with patch('rhesis.backend.app.crud.QueryBuilder') as mock_builder:
            mock_instance = Mock()
            mock_builder.return_value = mock_instance
            mock_instance.with_joinedloads.return_value = mock_instance
            mock_instance.with_organization_filter.return_value = mock_instance
            mock_instance.with_visibility_filter.return_value = mock_instance
            mock_instance.with_odata_filter.return_value = mock_instance
            mock_instance.with_pagination.return_value = mock_instance
            mock_instance.with_sorting.return_value = mock_instance
            mock_instance.all.return_value = []
            
            # Call get_test_sets with organization filtering
            result = crud.get_test_sets(test_db, organization_id=org_id)
            
            # Verify with_organization_filter was called with the organization_id
            mock_instance.with_organization_filter.assert_called_with(org_id)
            
            assert result == []


@pytest.mark.security
class TestAdditionalSecurityRegression:
    """Additional regression tests for the latest security fixes"""
    
    def test_token_functions_accept_organization_id(self):
        """🔒 SECURITY: Verify token functions accept organization_id parameter"""
        import inspect
        
        # Test that token functions have organization_id parameter
        functions_to_check = [
            crud.revoke_user_tokens,
            crud.get_token_by_value,
        ]
        
        for func in functions_to_check:
            signature = inspect.signature(func)
            assert 'organization_id' in signature.parameters, f"{func.__name__} missing organization_id parameter"

    def test_tag_functions_accept_organization_id(self):
        """🔒 SECURITY: Verify tag functions accept organization_id parameter"""
        import inspect
        
        # Test that assign_tag function has organization_id parameter
        signature = inspect.signature(crud.assign_tag)
        assert 'organization_id' in signature.parameters, "assign_tag missing organization_id parameter"

    def test_test_set_functions_accept_organization_id(self):
        """🔒 SECURITY: Verify test set functions accept organization_id parameter"""
        import inspect
        from rhesis.backend.app.services import test_set
        
        # Test that test set service functions have organization_id parameter
        functions_to_check = [
            test_set.get_test_set,
            test_set.update_test_set_attributes,
        ]
        
        for func in functions_to_check:
            signature = inspect.signature(func)
            assert 'organization_id' in signature.parameters, f"{func.__name__} missing organization_id parameter"
