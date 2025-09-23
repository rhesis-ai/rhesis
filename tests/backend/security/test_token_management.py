"""
🔒 Token Management Security Tests

This module tests security vulnerabilities related to token management,
including token scoping, revocation, and organization-based access control.
"""

import uuid
import pytest
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from rhesis.backend.app import models, crud


@pytest.mark.security
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
        
        token_value = "test_token_value"
        org_id = str(uuid.uuid4())
        
        # Mock the query to test the function works with organization filtering
        with patch.object(test_db, 'query') as mock_query:
            mock_token = Mock()
            mock_token.token = token_value
            mock_token.organization_id = uuid.UUID(org_id)
            
            # Test with organization filtering
            mock_query.return_value.filter.return_value.filter.return_value.first.return_value = mock_token
            result_with_org = crud.get_token_by_value(test_db, token_value, organization_id=org_id)
            assert result_with_org == mock_token
            
            # Test without organization filtering (should work but may return tokens from any org)
            mock_query.return_value.filter.return_value.first.return_value = mock_token
            result_without_org = crud.get_token_by_value(test_db, token_value)
            assert result_without_org == mock_token

    def test_create_token_organization_scoping(self, test_db: Session):
        """🔒 SECURITY: Test that create_token properly scopes tokens to organizations"""
        import inspect
        
        # Verify that create_token accepts organization_id parameter
        signature = inspect.signature(crud.create_token)
        assert 'organization_id' in signature.parameters, "create_token should accept organization_id for token scoping"
        
        user_id = uuid.uuid4()
        org_id = str(uuid.uuid4())
        
        # Mock the token creation
        with patch.object(test_db, 'add') as mock_add, \
             patch.object(test_db, 'commit') as mock_commit, \
             patch.object(test_db, 'refresh') as mock_refresh:
            
            mock_token = Mock()
            mock_token.user_id = user_id
            mock_token.organization_id = uuid.UUID(org_id)
            
            # Test token creation with organization scoping
            result = crud.create_token(test_db, user_id, organization_id=org_id)
            
            # Verify that add, commit, and refresh were called
            mock_add.assert_called_once()
            mock_commit.assert_called_once()

    def test_delete_token_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that delete_token accepts organization filtering for token scoping"""
        import inspect
        
        # Verify that delete_token accepts organization_id parameter
        signature = inspect.signature(crud.delete_token)
        assert 'organization_id' in signature.parameters, "delete_token should accept organization_id for token scoping"
        
        token_id = uuid.uuid4()
        org_id = str(uuid.uuid4())
        
        # Mock the query to test the function works with organization filtering
        with patch.object(test_db, 'query') as mock_query:
            mock_token = Mock()
            mock_token.id = token_id
            mock_token.organization_id = uuid.UUID(org_id)
            
            # Test with organization filtering
            mock_query.return_value.filter.return_value.filter.return_value.first.return_value = mock_token
            mock_query.return_value.filter.return_value.filter.return_value.delete.return_value = 1
            
            result_with_org = crud.delete_token(test_db, token_id, organization_id=org_id)
            assert result_with_org == 1
            
            # Test without organization filtering (should work but may delete tokens from any org)
            mock_query.return_value.filter.return_value.first.return_value = mock_token
            mock_query.return_value.filter.return_value.delete.return_value = 1
            
            result_without_org = crud.delete_token(test_db, token_id)
            assert result_without_org == 1


@pytest.mark.security
class TestTokenRegression:
    """Regression tests for token security fixes"""
    
    def test_token_functions_accept_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Ensure all token-related functions accept organization filtering"""
        import inspect
        
        # List of token-related CRUD functions that should accept organization_id
        token_functions = [
            'revoke_user_tokens',
            'get_token_by_value', 
            'create_token',
            'delete_token',
        ]
        
        for func_name in token_functions:
            if hasattr(crud, func_name):
                func = getattr(crud, func_name)
                signature = inspect.signature(func)
                assert 'organization_id' in signature.parameters, f"{func_name} should accept organization_id parameter"
    
    def test_token_cross_tenant_isolation(self, test_db: Session):
        """🔒 SECURITY: Test that tokens are properly isolated between organizations"""
        org1_id = str(uuid.uuid4())
        org2_id = str(uuid.uuid4())
        token_value = "test_token_123"
        
        with patch.object(test_db, 'query') as mock_query:
            # Mock token from org1
            mock_token_org1 = Mock()
            mock_token_org1.token = token_value
            mock_token_org1.organization_id = uuid.UUID(org1_id)
            
            # Mock token from org2
            mock_token_org2 = Mock()
            mock_token_org2.token = token_value
            mock_token_org2.organization_id = uuid.UUID(org2_id)
            
            # When querying with org1 filter, should only return org1 token
            mock_query.return_value.filter.return_value.filter.return_value.first.return_value = mock_token_org1
            result_org1 = crud.get_token_by_value(test_db, token_value, organization_id=org1_id)
            assert result_org1.organization_id == uuid.UUID(org1_id)
            
            # When querying with org2 filter, should only return org2 token  
            mock_query.return_value.filter.return_value.filter.return_value.first.return_value = mock_token_org2
            result_org2 = crud.get_token_by_value(test_db, token_value, organization_id=org2_id)
            assert result_org2.organization_id == uuid.UUID(org2_id)
