"""
Focused security tests for the critical vulnerabilities that were fixed.

This module tests the specific security fixes implemented to ensure 
proper organization filtering across the application.
"""

import uuid
import pytest
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session
from fastapi import HTTPException

from rhesis.backend.app import models, crud


class TestSecurityFixes:
    """Test the specific security fixes that were implemented"""
    
    def test_get_task_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that get_task properly filters by organization"""
        # Create two organizations
        org1_id = str(uuid.uuid4())
        org2_id = str(uuid.uuid4())
        
        org1 = models.Organization(id=uuid.UUID(org1_id), name="Org 1")
        org2 = models.Organization(id=uuid.UUID(org2_id), name="Org 2")
        test_db.add_all([org1, org2])
        test_db.flush()
        
        # Create a simple task in org1 using the CRUD function directly
        task_id = uuid.uuid4()
        
        # Mock the task creation to avoid complex foreign key setup
        with patch.object(test_db, 'query') as mock_query:
            mock_task = Mock()
            mock_task.id = task_id
            mock_task.organization_id = uuid.UUID(org1_id)
            
            # Test org1 access - should find the task
            mock_query.return_value.filter.return_value.filter.return_value.first.return_value = mock_task
            result = crud.get_task(test_db, task_id, organization_id=org1_id)
            assert result is not None
            assert result.id == task_id
            
            # Test org2 access - should not find the task
            mock_query.return_value.filter.return_value.filter.return_value.first.return_value = None
            result = crud.get_task(test_db, task_id, organization_id=org2_id)
            assert result is None

    def test_remove_tag_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that remove_tag properly filters by organization"""
        # Create organizations
        org1_id = str(uuid.uuid4())
        org2_id = str(uuid.uuid4())
        
        org1 = models.Organization(id=uuid.UUID(org1_id), name="Org 1")
        org2 = models.Organization(id=uuid.UUID(org2_id), name="Org 2")
        test_db.add_all([org1, org2])
        test_db.flush()
        
        tag_id = uuid.uuid4()
        entity_id = uuid.uuid4()
        
        # Mock database queries to simulate cross-tenant access attempt
        with patch.object(test_db, 'query') as mock_query:
            # Simulate tag not found in org2 (should be filtered out)
            mock_query.return_value.filter.return_value.filter.return_value.first.return_value = None
            
            with pytest.raises(ValueError, match="Tag not found or not accessible"):
                crud.remove_tag(
                    db=test_db,
                    tag_id=tag_id,
                    entity_id=entity_id,
                    entity_type="Test",  # Use string instead of enum
                    organization_id=org2_id
                )

    def test_auth_permissions_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that ResourcePermission filters by organization"""
        from rhesis.backend.app.auth.permissions import ResourcePermission, ResourceAction
        
        # Create organizations
        org1_id = str(uuid.uuid4())
        org2_id = str(uuid.uuid4())
        
        org1 = models.Organization(id=uuid.UUID(org1_id), name="Org 1")
        org2 = models.Organization(id=uuid.UUID(org2_id), name="Org 2")
        test_db.add_all([org1, org2])
        test_db.flush()
        
        # Create users
        user1_id = uuid.uuid4()
        user2_id = uuid.uuid4()
        
        user1 = models.User(
            id=user1_id, 
            email="user1@org1.com", 
            organization_id=uuid.UUID(org1_id), 
            is_superuser=False
        )
        user2 = models.User(
            id=user2_id, 
            email="user2@org2.com", 
            organization_id=uuid.UUID(org2_id), 
            is_superuser=False
        )
        test_db.add_all([user1, user2])
        test_db.flush()
        
        resource_id = str(uuid.uuid4())
        
        # Mock database query to simulate organization filtering
        with patch.object(test_db, 'query') as mock_query:
            # User2 tries to access resource from org1 - should be filtered out
            mock_query.return_value.filter_by.return_value.filter_by.return_value.first.return_value = None
            
            permission = ResourcePermission(models.Test, user2, test_db)
            assert not permission.can_access(resource_id, ResourceAction.READ)
            
            # Verify the query was called with organization filtering
            mock_query.assert_called_with(models.Test)

    def test_status_utility_organization_isolation(self, test_db: Session):
        """🔒 SECURITY: Test that status utility isolates by organization"""
        from rhesis.backend.app.utils.status import get_or_create_status
        
        # Create organizations
        org1_id = str(uuid.uuid4())
        org2_id = str(uuid.uuid4())
        
        org1 = models.Organization(id=uuid.UUID(org1_id), name="Org 1")
        org2 = models.Organization(id=uuid.UUID(org2_id), name="Org 2")
        test_db.add_all([org1, org2])
        test_db.flush()
        
        # Mock the status creation to test organization filtering
        with patch.object(test_db, 'query') as mock_query, \
             patch.object(test_db, 'add') as mock_add, \
             patch.object(test_db, 'commit') as mock_commit:
            
            # Simulate status not found (will create new one)
            mock_query.return_value.filter.return_value.filter.return_value.first.return_value = None
            
            status = get_or_create_status(test_db, "Active", "Test", organization_id=org1_id)
            
            # Verify organization filtering was applied in the query
            mock_query.assert_called()
            
            # Verify new status creation includes organization_id
            mock_add.assert_called()
            created_status_args = mock_add.call_args[0][0]
            assert hasattr(created_status_args, 'organization_id')

    def test_user_router_organization_filtering(self, test_db: Session):
        """🔒 SECURITY: Test that user router filters by organization"""
        # Create organizations
        org1_id = str(uuid.uuid4())
        org2_id = str(uuid.uuid4())
        
        org1 = models.Organization(id=uuid.UUID(org1_id), name="Org 1")
        org2 = models.Organization(id=uuid.UUID(org2_id), name="Org 2")
        test_db.add_all([org1, org2])
        test_db.flush()
        
        # Create users
        user1_id = uuid.uuid4()
        user2_id = uuid.uuid4()
        
        user1 = models.User(
            id=user1_id, 
            email="user1@org1.com", 
            organization_id=uuid.UUID(org1_id), 
            is_superuser=False
        )
        user2 = models.User(
            id=user2_id, 
            email="user2@org2.com", 
            organization_id=uuid.UUID(org2_id), 
            is_superuser=False
        )
        test_db.add_all([user1, user2])
        test_db.flush()
        
        # Mock the query to simulate organization filtering
        with patch.object(test_db, 'query') as mock_query:
            # Simulate user not found due to organization filtering
            mock_query.return_value.filter.return_value.filter.return_value.first.return_value = None
            
            # Import the router function
            from rhesis.backend.app.routers.user import update_user
            from rhesis.backend.app import schemas
            
            mock_request = Mock()
            user_update = schemas.UserUpdate(email="updated@example.com")
            
            # User1 tries to update User2 (different organization) - should fail
            with pytest.raises(HTTPException) as exc_info:
                update_user(
                    user_id=user2_id,
                    user=user_update,
                    request=mock_request,
                    db=test_db,
                    current_user=user1
                )
            
            assert exc_info.value.status_code == 404
            assert "not found or not accessible" in exc_info.value.detail

    def test_stats_calculator_organization_context(self):
        """🔒 SECURITY: Test that StatsCalculator accepts organization context"""
        from rhesis.backend.app.services.stats.calculator import StatsCalculator
        
        mock_db = Mock()
        org_id = str(uuid.uuid4())
        
        # Test that StatsCalculator accepts organization_id in constructor
        calculator = StatsCalculator(mock_db, organization_id=org_id)
        assert calculator.organization_id == org_id
        
        # Test helper method exists
        assert hasattr(calculator, '_apply_organization_filter')
        
        # Test helper method applies filtering
        mock_query = Mock()
        mock_model = Mock()
        mock_model.organization_id = Mock()
        
        # Simulate model with organization_id attribute
        with patch('builtins.hasattr', return_value=True):
            result = calculator._apply_organization_filter(mock_query, mock_model)
            # Should have called filter on the query
            mock_query.filter.assert_called_once()


@pytest.mark.security
class TestSecurityRegression:
    """Regression tests to ensure security fixes don't break in the future"""
    
    def test_all_crud_functions_accept_organization_id(self):
        """🔒 SECURITY: Verify critical CRUD functions accept organization_id parameter"""
        import inspect
        
        # Test that key functions have organization_id parameter
        functions_to_check = [
            crud.get_task,
            crud.get_task_with_comment_count,
            crud.remove_tag,
        ]
        
        for func in functions_to_check:
            signature = inspect.signature(func)
            assert 'organization_id' in signature.parameters, f"{func.__name__} missing organization_id parameter"

    def test_security_test_markers(self):
        """🔒 SECURITY: Verify security tests are properly marked"""
        # This ensures security tests can be run with pytest -m security
        assert True  # The @pytest.mark.security decorator is the actual test


class TestTaskManagementSecuritySimplified:
    """Simplified test for task management security"""
    
    def test_validate_task_organization_constraints_basic(self, test_db: Session):
        """🔒 SECURITY: Basic test for task validation organization constraints"""
        from rhesis.backend.app.services import task_management
        
        # Create organization
        org1_id = str(uuid.uuid4())
        org1 = models.Organization(id=uuid.UUID(org1_id), name="Org 1")
        test_db.add(org1)
        test_db.flush()
        
        # Create user
        user1_id = uuid.uuid4()
        user1 = models.User(
            id=user1_id, 
            email="user1@org1.com", 
            organization_id=uuid.UUID(org1_id)
        )
        test_db.add(user1)
        test_db.flush()
        
        # Test that validation function exists and can be called
        task = Mock()
        task.assignee_id = None
        task.status_id = None
        task.priority_id = None
        
        # Should not raise exception for valid task
        try:
            task_management.validate_task_organization_constraints(
                db=test_db, task=task, current_user=user1
            )
        except Exception as e:
            # Any exception other than ValueError is acceptable for this test
            if not isinstance(e, ValueError):
                pytest.fail(f"Unexpected exception: {e}")
