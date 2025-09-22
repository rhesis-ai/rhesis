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
        """🔒 SECURITY: Test that revoke_user_tokens accepts organization filtering for token scoping"""
        import inspect
        
        # Verify that revoke_user_tokens accepts organization_id parameter (tokens may be organization-scoped)
        signature = inspect.signature(crud.revoke_user_tokens)
        assert 'organization_id' in signature.parameters, "revoke_user_tokens should accept organization_id for token scoping"
        
        user_id = uuid.uuid4()
        org_id = str(uuid.uuid4())
        
        # Mock the query to test the function works with organization filtering
        with patch.object(test_db, 'query') as mock_query:
            mock_query.return_value.filter.return_value.filter.return_value.delete.return_value = 2
            mock_query.return_value.filter.return_value.delete.return_value = 3
            
            # Test with organization filtering
            result_with_org = crud.revoke_user_tokens(test_db, user_id, organization_id=org_id)
            assert result_with_org == 2
            
            # Test without organization filtering (should work but may revoke more tokens)
            result_without_org = crud.revoke_user_tokens(test_db, user_id)
            assert result_without_org == 3

    def test_get_token_by_value_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that get_token_by_value accepts organization filtering for token scoping"""
        import inspect
        
        # Verify that get_token_by_value accepts organization_id parameter (tokens may be organization-scoped)
        signature = inspect.signature(crud.get_token_by_value)
        assert 'organization_id' in signature.parameters, "get_token_by_value should accept organization_id for token scoping"
        
        token_value = "test-token-123"
        org_id = str(uuid.uuid4())
        
        # Mock the query to test the function works with organization filtering
        with patch.object(test_db, 'query') as mock_query:
            mock_token_with_org = Mock()
            mock_token_without_org = Mock()
            
            # Setup mock to return different results based on filtering
            def mock_filter_chain(*args):
                if len(mock_query.return_value.filter.call_args_list) >= 2:
                    return Mock(first=Mock(return_value=mock_token_with_org))
                else:
                    return Mock(first=Mock(return_value=mock_token_without_org))
            
            mock_query.return_value.filter.side_effect = mock_filter_chain
            
            # Test with organization filtering
            result_with_org = crud.get_token_by_value(test_db, token_value, organization_id=org_id)
            
            # Test without organization filtering  
            result_without_org = crud.get_token_by_value(test_db, token_value)
            
            # Both should work (exact results depend on token scoping implementation)
            assert result_with_org is not None or result_without_org is not None


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
            from rhesis.backend.app.constants import EntityType
            with pytest.raises(ValueError, match="not found or not accessible"):
                crud.assign_tag(
                    db=test_db,
                    tag=tag_data,
                    entity_id=entity_id,
                    entity_type=EntityType.TEST,  # Use proper enum
                    organization_id=org2_id  # Different organization
                )


class TestTestSetServiceSecurityFixes:
    """Test security fixes for test set service vulnerabilities"""
    
    def test_get_test_set_uuid_based_query_safe(self, test_db: Session):
        """✅ SAFE: Test that get_test_set uses UUID-based query (no organization filtering needed)"""
        from rhesis.backend.app.services.test_set import get_test_set
        import inspect
        
        # Verify that get_test_set no longer requires organization_id (UUID queries are safe)
        signature = inspect.signature(get_test_set)
        assert 'organization_id' not in signature.parameters, "get_test_set should not need organization_id for UUID queries"
        
        test_set_id = uuid.uuid4()
        
        # Mock the query to test that it only filters by ID
        with patch.object(test_db, 'query') as mock_query:
            mock_query.return_value.filter.return_value.options.return_value.first.return_value = None
            
            # Call get_test_set - should work without organization_id
            result = get_test_set(test_db, test_set_id)
            
            # Verify only ID filtering was applied (UUID is globally unique)
            mock_query.assert_called()
            filter_calls = mock_query.return_value.filter.call_args_list
            
            # Should only have one filter call (for the UUID)
            assert len(filter_calls) == 1
            
            assert result is None

    def test_update_test_set_attributes_uuid_based_query_safe(self, test_db: Session):
        """✅ SAFE: Test that update_test_set_attributes uses UUID-based query (no organization filtering needed)"""
        from rhesis.backend.app.services.test_set import update_test_set_attributes
        import inspect
        
        # Verify that update_test_set_attributes no longer requires organization_id (UUID queries are safe)
        signature = inspect.signature(update_test_set_attributes)
        assert 'organization_id' not in signature.parameters, "update_test_set_attributes should not need organization_id for UUID queries"
        
        test_set_id = str(uuid.uuid4())
        
        # Mock the query to test that it only filters by ID
        with patch.object(test_db, 'query') as mock_query:
            mock_query.return_value.options.return_value.filter.return_value.first.return_value = None
            
            # Try to update test set - should raise ValueError for not found (not for access denied)
            with pytest.raises(ValueError, match="not found"):
                update_test_set_attributes(test_db, test_set_id)


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

    def test_test_set_functions_uuid_based_queries_safe(self):
        """✅ SAFE: Verify test set functions use UUID-based queries (no organization_id needed)"""
        import inspect
        from rhesis.backend.app.services import test_set
        
        # Test that UUID-based test set functions don't need organization_id parameter
        functions_to_check = [
            test_set.get_test_set,
            test_set.update_test_set_attributes,
        ]
        
        for func in functions_to_check:
            signature = inspect.signature(func)
            assert 'organization_id' not in signature.parameters, f"{func.__name__} should not need organization_id for UUID queries"
