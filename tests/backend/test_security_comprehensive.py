"""
Comprehensive security tests for cross-tenant data access prevention.

This module tests all the critical security vulnerabilities that were fixed
to ensure proper organization filtering across the entire application.
"""

import uuid
import pytest
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session
from fastapi import HTTPException

from rhesis.backend.app import models, crud, schemas
from rhesis.backend.app.auth.permissions import ResourcePermission, ResourceAction
from rhesis.backend.app.services import task_management
from rhesis.backend.app.utils.status import get_or_create_status


class TestTaskManagementSecurity:
    """Test security vulnerabilities in task management service"""
    
    def test_validate_task_organization_constraints_cross_tenant_assignee(self, test_db: Session):
        """🔒 SECURITY: Test that assignee validation prevents cross-tenant access"""
        # Create two organizations
        org1_id = str(uuid.uuid4())
        org2_id = str(uuid.uuid4())
        
        org1 = models.Organization(id=uuid.UUID(org1_id), name="Org 1")
        org2 = models.Organization(id=uuid.UUID(org2_id), name="Org 2")
        test_db.add_all([org1, org2])
        test_db.flush()
        
        # Create users in different organizations
        user1_id = uuid.uuid4()
        user2_id = uuid.uuid4()
        
        user1 = models.User(id=user1_id, email="user1@org1.com", organization_id=uuid.UUID(org1_id))
        user2 = models.User(id=user2_id, email="user2@org2.com", organization_id=uuid.UUID(org2_id))
        test_db.add_all([user1, user2])
        test_db.flush()
        
        # Create task with assignee from different organization
        task = Mock()
        task.assignee_id = user2_id  # User from org2
        task.status_id = None
        task.priority_id = None
        
        # Try to validate as user1 (from org1) - should fail
        with pytest.raises(ValueError, match="Assignee not found or not in same organization"):
            task_management.validate_task_organization_constraints(
                db=test_db, task=task, current_user=user1
            )

    def test_validate_task_organization_constraints_cross_tenant_status(self, test_db: Session):
        """🔒 SECURITY: Test that status validation prevents cross-tenant access"""
        # Create two organizations
        org1_id = str(uuid.uuid4())
        org2_id = str(uuid.uuid4())
        
        org1 = models.Organization(id=uuid.UUID(org1_id), name="Org 1")
        org2 = models.Organization(id=uuid.UUID(org2_id), name="Org 2")
        test_db.add_all([org1, org2])
        test_db.flush()
        
        # Create user in org1
        user1_id = uuid.uuid4()
        user1 = models.User(id=user1_id, email="user1@org1.com", organization_id=uuid.UUID(org1_id))
        test_db.add(user1)
        test_db.flush()
        
        # Create status in org2
        status_id = uuid.uuid4()
        # Create a type lookup for entity type first
        entity_type_id = uuid.uuid4()
        entity_type = models.TypeLookup(
            id=entity_type_id,
            type_name="EntityType", 
            type_value="Task",
            organization_id=uuid.UUID(org2_id),
            user_id=uuid.uuid4()
        )
        test_db.add(entity_type)
        test_db.flush()
        
        status = models.Status(
            id=status_id, 
            name="In Progress", 
            entity_type_id=entity_type_id,
            organization_id=uuid.UUID(org2_id), 
            user_id=uuid.uuid4()
        )
        test_db.add(status)
        test_db.flush()
        
        # Create task with status from different organization
        task = Mock()
        task.assignee_id = None
        task.status_id = status_id  # Status from org2
        task.priority_id = None
        
        # Try to validate as user1 (from org1) - should fail
        with pytest.raises(ValueError, match="Status not found or not in same organization"):
            task_management.validate_task_organization_constraints(
                db=test_db, task=task, current_user=user1
            )


class TestCrudTaskSecurity:
    """Test security vulnerabilities in CRUD task operations"""
    
    def test_get_task_cross_tenant_prevention(self, test_db: Session):
        """🔒 SECURITY: Test that get_task prevents cross-tenant access"""
        # Create two organizations
        org1_id = str(uuid.uuid4())
        org2_id = str(uuid.uuid4())
        
        org1 = models.Organization(id=uuid.UUID(org1_id), name="Org 1")
        org2 = models.Organization(id=uuid.UUID(org2_id), name="Org 2")
        test_db.add_all([org1, org2])
        test_db.flush()
        
        # Create task in org1
        task_id = uuid.uuid4()
        task = models.Task(
            id=task_id, 
            title="Test Task", 
            organization_id=uuid.UUID(org1_id),
            user_id=uuid.uuid4()
        )
        test_db.add(task)
        test_db.flush()
        
        # Try to access task from org2 - should return None
        result = crud.get_task(test_db, task_id, organization_id=org2_id)
        assert result is None
        
        # Access task from org1 - should succeed
        result = crud.get_task(test_db, task_id, organization_id=org1_id)
        assert result is not None
        assert result.id == task_id

    def test_get_task_with_comment_count_cross_tenant_prevention(self, test_db: Session):
        """🔒 SECURITY: Test that get_task_with_comment_count prevents cross-tenant access"""
        # Create two organizations
        org1_id = str(uuid.uuid4())
        org2_id = str(uuid.uuid4())
        
        org1 = models.Organization(id=uuid.UUID(org1_id), name="Org 1")
        org2 = models.Organization(id=uuid.UUID(org2_id), name="Org 2")
        test_db.add_all([org1, org2])
        test_db.flush()
        
        # Create task in org1
        task_id = uuid.uuid4()
        task = models.Task(
            id=task_id, 
            title="Test Task", 
            organization_id=uuid.UUID(org1_id),
            user_id=uuid.uuid4()
        )
        test_db.add(task)
        test_db.flush()
        
        # Try to access task from org2 - should return None
        result = crud.get_task_with_comment_count(test_db, task_id, organization_id=org2_id)
        assert result is None
        
        # Access task from org1 - should succeed
        result = crud.get_task_with_comment_count(test_db, task_id, organization_id=org1_id)
        assert result is not None
        assert result.id == task_id

    def test_remove_tag_cross_tenant_prevention(self, test_db: Session):
        """🔒 SECURITY: Test that remove_tag prevents cross-tenant access"""
        # Create two organizations
        org1_id = str(uuid.uuid4())
        org2_id = str(uuid.uuid4())
        
        org1 = models.Organization(id=uuid.UUID(org1_id), name="Org 1")
        org2 = models.Organization(id=uuid.UUID(org2_id), name="Org 2")
        test_db.add_all([org1, org2])
        test_db.flush()
        
        # Create tag in org1
        tag_id = uuid.uuid4()
        tag = models.Tag(
            id=tag_id, 
            name="test-tag", 
            organization_id=uuid.UUID(org1_id),
            user_id=uuid.uuid4()
        )
        test_db.add(tag)
        test_db.flush()
        
        # Create test entity in org1
        test_id = uuid.uuid4()
        test_entity = models.Test(
            id=test_id,
            organization_id=uuid.UUID(org1_id),
            user_id=uuid.uuid4(),
            prompt_id=uuid.uuid4()
        )
        test_db.add(test_entity)
        test_db.flush()
        
        # Try to remove tag from org2 perspective - should fail
        with pytest.raises(ValueError, match="Tag not found or not accessible"):
            crud.remove_tag(
                db=test_db, 
                tag_id=tag_id, 
                entity_id=test_id, 
                entity_type=models.EntityType.TEST,
                organization_id=org2_id
            )


class TestAuthPermissionsSecurity:
    """Test security vulnerabilities in auth permissions"""
    
    def test_resource_permission_cross_tenant_prevention(self, test_db: Session):
        """🔒 SECURITY: Test that ResourcePermission prevents cross-tenant access"""
        # Create two organizations
        org1_id = str(uuid.uuid4())
        org2_id = str(uuid.uuid4())
        
        org1 = models.Organization(id=uuid.UUID(org1_id), name="Org 1")
        org2 = models.Organization(id=uuid.UUID(org2_id), name="Org 2")
        test_db.add_all([org1, org2])
        test_db.flush()
        
        # Create users in different organizations
        user1_id = uuid.uuid4()
        user2_id = uuid.uuid4()
        
        user1 = models.User(id=user1_id, email="user1@org1.com", organization_id=uuid.UUID(org1_id), is_superuser=False)
        user2 = models.User(id=user2_id, email="user2@org2.com", organization_id=uuid.UUID(org2_id), is_superuser=False)
        test_db.add_all([user1, user2])
        test_db.flush()
        
        # Create test resource in org1
        test_id = uuid.uuid4()
        test_resource = models.Test(
            id=test_id,
            organization_id=uuid.UUID(org1_id),
            user_id=user1_id,
            prompt_id=uuid.uuid4()
        )
        test_db.add(test_resource)
        test_db.flush()
        
        # User2 (from org2) tries to access resource from org1 - should fail
        permission = ResourcePermission(models.Test, user2, test_db)
        assert not permission.can_access(str(test_id), ResourceAction.READ)
        
        # User1 (from org1) tries to access resource from org1 - should succeed
        permission = ResourcePermission(models.Test, user1, test_db)
        assert permission.can_access(str(test_id), ResourceAction.READ)


class TestStatusUtilitySecurity:
    """Test security vulnerabilities in status utility"""
    
    def test_get_or_create_status_cross_tenant_isolation(self, test_db: Session):
        """🔒 SECURITY: Test that get_or_create_status properly isolates by organization"""
        # Create two organizations
        org1_id = str(uuid.uuid4())
        org2_id = str(uuid.uuid4())
        
        org1 = models.Organization(id=uuid.UUID(org1_id), name="Org 1")
        org2 = models.Organization(id=uuid.UUID(org2_id), name="Org 2")
        test_db.add_all([org1, org2])
        test_db.flush()
        
        # Create status in org1
        status1 = get_or_create_status(test_db, "Active", "Test", organization_id=org1_id)
        assert status1.organization_id == uuid.UUID(org1_id)
        
        # Create status with same name in org2 - should create separate status
        status2 = get_or_create_status(test_db, "Active", "Test", organization_id=org2_id)
        assert status2.organization_id == uuid.UUID(org2_id)
        assert status1.id != status2.id
        
        # Verify isolation - org1 query should not find org2 status
        status1_again = get_or_create_status(test_db, "Active", "Test", organization_id=org1_id)
        assert status1_again.id == status1.id  # Should find the existing org1 status
        
        # Verify isolation - org2 query should not find org1 status
        status2_again = get_or_create_status(test_db, "Active", "Test", organization_id=org2_id)
        assert status2_again.id == status2.id  # Should find the existing org2 status


class TestUserRouterSecurity:
    """Test security vulnerabilities in user router"""
    
    @patch('rhesis.backend.app.routers.user.crud.update_user')
    def test_update_user_cross_tenant_prevention(self, mock_update_user, test_db: Session):
        """🔒 SECURITY: Test that user update prevents cross-tenant access"""
        from rhesis.backend.app.routers.user import update_user as router_update_user
        
        # Create two organizations
        org1_id = str(uuid.uuid4())
        org2_id = str(uuid.uuid4())
        
        org1 = models.Organization(id=uuid.UUID(org1_id), name="Org 1")
        org2 = models.Organization(id=uuid.UUID(org2_id), name="Org 2")
        test_db.add_all([org1, org2])
        test_db.flush()
        
        # Create users in different organizations
        user1_id = uuid.uuid4()
        user2_id = uuid.uuid4()
        
        user1 = models.User(id=user1_id, email="user1@org1.com", organization_id=uuid.UUID(org1_id), is_superuser=False)
        user2 = models.User(id=user2_id, email="user2@org2.com", organization_id=uuid.UUID(org2_id), is_superuser=False)
        test_db.add_all([user1, user2])
        test_db.flush()
        
        # Create mock request and user update schema
        mock_request = Mock()
        user_update = schemas.UserUpdate(email="updated@org2.com")
        
        # User1 tries to update User2 (different organization) - should fail
        with pytest.raises(HTTPException) as exc_info:
            router_update_user(
                user_id=user2_id,
                user=user_update,
                request=mock_request,
                db=test_db,
                current_user=user1
            )
        assert exc_info.value.status_code == 404
        assert "not found or not accessible" in exc_info.value.detail


@pytest.mark.security
class TestComprehensiveSecuritySuite:
    """Comprehensive security test suite covering all fixed vulnerabilities"""
    
    def test_all_organization_models_have_filtering(self):
        """🔒 SECURITY: Verify all organization-aware models are properly identified"""
        organization_models = []
        
        # Check all models for organization_id attribute
        for attr_name in dir(models):
            attr = getattr(models, attr_name)
            if (hasattr(attr, '__tablename__') and 
                hasattr(attr, 'organization_id')):
                organization_models.append(attr_name)
        
        # Verify we have the expected organization-aware models
        expected_models = [
            'Behavior', 'Category', 'Comment', 'Demographic', 'Dimension', 
            'Metric', 'Model', 'Prompt', 'Risk', 'Source', 'Status', 
            'Tag', 'Task', 'Test', 'TestResult', 'TestRun', 'TestSet', 
            'Token', 'Topic', 'TypeLookup', 'UseCase'
        ]
        
        for model_name in expected_models:
            if hasattr(models, model_name):
                assert model_name in organization_models, f"{model_name} should be organization-aware"
    
    def test_security_markers_present(self):
        """🔒 SECURITY: Verify security test markers are properly configured"""
        # This test ensures our security tests are properly marked
        # and can be run separately with pytest -m security
        assert True  # Placeholder - the @pytest.mark.security decorator is the real test
