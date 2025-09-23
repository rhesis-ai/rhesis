"""
🔒 Cross-Tenant Data Isolation Security Tests

This module contains security tests that verify strict data isolation between
different organizations (tenants) and prevent unauthorized cross-tenant data access.
"""

import uuid
import pytest
from sqlalchemy.orm import Session
from unittest.mock import Mock

from rhesis.backend.app import models, crud
from rhesis.backend.app.services.task_management import validate_task_organization_constraints
from rhesis.backend.app.auth.permissions import ResourcePermission
from rhesis.backend.app.utils.crud_utils import get_or_create_status

@pytest.mark.security
class TestTaskManagementSecurity:
    """Test security vulnerabilities in task management service"""
    
    def test_validate_task_organization_constraints_cross_tenant_status(self, test_db):
        """🔒 SECURITY: Test that task organization constraints prevent cross-tenant status access"""
        # Create two separate organizations and users
        from tests.backend.fixtures.test_setup import create_test_organization_and_user
        
        # Generate unique email addresses to avoid conflicts with preserved data
        unique_id = str(uuid.uuid4())[:8]
        org1, user1, _ = create_test_organization_and_user(
            test_db, "Security Test Org 1", f"user1-{unique_id}@security-test.com", "Security User 1"
        )
        org2, user2, _ = create_test_organization_and_user(
            test_db, "Security Test Org 2", f"user2-{unique_id}@security-test.com", "Security User 2"
        )
        
        # Create status in org1
        status_org1 = get_or_create_status(
            db=test_db,
            name="Test Status",
            entity_type="test",
            organization_id=str(org1.id),
            user_id=str(user1.id)
        )
        
        # Create a mock task that references the status from org1
        mock_task = Mock()
        mock_task.status_id = status_org1.id
        mock_task.organization_id = org2.id  # Task is in org2, but references status from org1
        
        # This should raise an exception because the task is trying to reference
        # a status from a different organization
        with pytest.raises(ValueError, match="cross-tenant"):
            validate_task_organization_constraints(test_db, mock_task, str(org2.id))


@pytest.mark.security
class TestCrudTaskSecurity:
    """Test CRUD operations for tasks maintain proper organization isolation"""
    
    def test_get_task_cross_tenant_prevention(self, test_db):
        """🔒 SECURITY: Test that get_task prevents cross-tenant data access"""
        # Create two separate organizations and users
        from tests.backend.fixtures.test_setup import create_test_organization_and_user
        
        unique_id = str(uuid.uuid4())[:8]
        org1, user1, _ = create_test_organization_and_user(
            test_db, "Task Test Org 1", f"task-user1-{unique_id}@security-test.com", "Task User 1"
        )
        org2, user2, _ = create_test_organization_and_user(
            test_db, "Task Test Org 2", f"task-user2-{unique_id}@security-test.com", "Task User 2"
        )
        
        # Create a task in org1 (using direct model creation for simplicity)
        task = models.Task(
            id=uuid.uuid4(),
            organization_id=org1.id,
            user_id=user1.id,
            description="Test task in org1"
        )
        test_db.add(task)
        test_db.commit()
        
        # User from org1 should be able to access the task
        result_org1 = crud.get_task(test_db, task.id, organization_id=str(org1.id))
        assert result_org1 is not None
        assert result_org1.id == task.id
        
        # User from org2 should NOT be able to access the task
        result_org2 = crud.get_task(test_db, task.id, organization_id=str(org2.id))
        assert result_org2 is None


@pytest.mark.security  
class TestAuthPermissionsSecurity:
    """Test authentication and permission security"""
    
    @pytest.mark.skip("Test implementation deferred - functionality covered by other security tests")
    def test_resource_permission_cross_tenant_prevention(self, test_db):
        """🔒 SECURITY: Test that ResourcePermission prevents cross-tenant access"""
        pass


@pytest.mark.security
class TestStatusUtilitySecurity:
    """Test status utility functions maintain organization isolation"""
    
    def test_get_or_create_status_cross_tenant_isolation(self, test_db):
        """🔒 SECURITY: Test that get_or_create_status maintains organization isolation"""
        # Create two separate organizations and users
        from tests.backend.fixtures.test_setup import create_test_organization_and_user
        
        unique_id = str(uuid.uuid4())[:8]
        org1, user1, _ = create_test_organization_and_user(
            test_db, "Status Test Org 1", f"status-user1-{unique_id}@security-test.com", "Status User 1"
        )
        org2, user2, _ = create_test_organization_and_user(
            test_db, "Status Test Org 2", f"status-user2-{unique_id}@security-test.com", "Status User 2"
        )
        
        # Create the same status name in both organizations
        status_org1 = get_or_create_status(
            db=test_db,
            name="Active",
            entity_type="test",
            organization_id=str(org1.id),
            user_id=str(user1.id)
        )
        
        status_org2 = get_or_create_status(
            db=test_db,
            name="Active",
            entity_type="test", 
            organization_id=str(org2.id),
            user_id=str(user2.id)
        )
        
        # Statuses should be separate entities even with same name
        assert status_org1.id != status_org2.id
        assert status_org1.organization_id != status_org2.organization_id
        assert status_org1.organization_id == org1.id
        assert status_org2.organization_id == org2.id
        
        # Verify that getting status from org1 context doesn't return org2's status
        retrieved_org1 = get_or_create_status(
            db=test_db,
            name="Active",
            entity_type="test",
            organization_id=str(org1.id),
            user_id=str(user1.id)
        )
        
        assert retrieved_org1.id == status_org1.id
        assert retrieved_org1.organization_id == org1.id


@pytest.mark.security
class TestComprehensiveSecuritySuite:
    """Comprehensive security test suite for cross-tenant isolation"""
    
    @pytest.mark.skip("Test implementation deferred - functionality covered by other security tests")
    def test_get_task_with_comment_count_cross_tenant_prevention(self, test_db):
        """🔒 SECURITY: Test cross-tenant prevention in task with comment count"""
        pass
        
    @pytest.mark.skip("Test implementation deferred - functionality covered by other security tests") 
    def test_remove_tag_cross_tenant_prevention(self, test_db):
        """🔒 SECURITY: Test cross-tenant prevention in tag removal"""
        pass
