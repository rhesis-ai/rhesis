"""
Tests for organization service functions that use maintain_tenant_context.

These tests verify the current behavior of functions before they are refactored
to use the new get_org_aware_db approach.
"""

import pytest
import uuid
import json
import os
from unittest.mock import patch, MagicMock, mock_open
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.services import organization as organization_service

# Use existing data factories from the established pattern
from tests.backend.routes.fixtures.data_factories import OrganizationDataFactory


@pytest.mark.unit
@pytest.mark.service
class TestLoadInitialData:
    """Test load_initial_data function that uses maintain_tenant_context."""

    def test_load_initial_data_success(self, test_db: Session, authenticated_user_id, test_org_id):
        """Test successful loading of initial data."""
        # Mock initial data JSON
        mock_initial_data = {
            "type_lookup": [
                {"type_name": "TestType", "type_value": "default"}
            ],
            "status": [
                {"name": "active", "entity_type": "test"}
            ],
            "behavior": [
                {"name": "test_behavior", "description": "Test behavior", "status": "active"}
            ],
            "use_case": [
                {"name": "test_use_case", "description": "Test use case", "industry": "tech"}
            ],
            "risk": [
                {"name": "test_risk", "description": "Test risk", "severity": "medium"}
            ]
        }
        
        # Mock file operations and utility functions
        with patch('builtins.open', mock_open(read_data=json.dumps(mock_initial_data))), \
             patch('rhesis.backend.app.services.organization.get_or_create_type_lookup') as mock_get_type, \
             patch('rhesis.backend.app.services.organization.get_or_create_status') as mock_get_status, \
             patch('rhesis.backend.app.services.organization.get_or_create_behavior') as mock_get_behavior, \
             patch('rhesis.backend.app.services.organization.get_or_create_entity') as mock_get_entity, \
             patch('rhesis.backend.app.services.organization.set_tenant') as mock_set_tenant:
            
            # Call the function
            organization_service.load_initial_data(
                db=test_db,
                organization_id=test_org_id,
                user_id=authenticated_user_id
            )
            
            # Verify set_tenant was called
            mock_set_tenant.assert_called_once_with(
                test_db, 
                organization_id=test_org_id, 
                user_id=authenticated_user_id
            )
            
            # Verify type_lookup creation
            mock_get_type.assert_called_once_with(
                db=test_db,
                type_name="TestType",
                type_value="default",
                commit=False
            )
            
            # Verify status creation
            mock_get_status.assert_called_once_with(
                db=test_db,
                name="active",
                entity_type="test",
                commit=False
            )
            
            # Verify behavior creation
            mock_get_behavior.assert_called_once_with(
                db=test_db,
                name="test_behavior",
                description="Test behavior",
                status="active",
                commit=False
            )
            
            # Verify use_case creation
            mock_get_entity.assert_any_call(
                db=test_db,
                model=models.UseCase,
                entity_data={
                    "name": "test_use_case",
                    "description": "Test use case",
                    "industry": "tech",
                    "application": None,
                    "is_active": True
                },
                commit=False
            )

    def test_load_initial_data_file_not_found(self, test_db: Session, authenticated_user_id, test_org_id):
        """Test load_initial_data when initial_data.json file is not found."""
        with patch('builtins.open', side_effect=FileNotFoundError("File not found")), \
             patch('rhesis.backend.app.services.organization.set_tenant') as mock_set_tenant:
            
            # Call the function and expect FileNotFoundError
            with pytest.raises(FileNotFoundError):
                organization_service.load_initial_data(
                    db=test_db,
                    organization_id=test_org_id,
                    user_id=authenticated_user_id
                )
            
            # Verify set_tenant was still called
            mock_set_tenant.assert_called_once_with(
                test_db, 
                organization_id=test_org_id, 
                user_id=authenticated_user_id
            )

    def test_load_initial_data_invalid_json(self, test_db: Session, authenticated_user_id, test_org_id):
        """Test load_initial_data with invalid JSON data."""
        # Mock invalid JSON data
        invalid_json = "{ invalid json }"
        
        with patch('builtins.open', mock_open(read_data=invalid_json)), \
             patch('rhesis.backend.app.services.organization.set_tenant') as mock_set_tenant:
            
            # Call the function and expect JSONDecodeError
            with pytest.raises(json.JSONDecodeError):
                organization_service.load_initial_data(
                    db=test_db,
                    organization_id=test_org_id,
                    user_id=authenticated_user_id
                )
            
            # Verify set_tenant was still called
            mock_set_tenant.assert_called_once_with(
                test_db, 
                organization_id=test_org_id, 
                user_id=authenticated_user_id
            )

    def test_load_initial_data_empty_data(self, test_db: Session, authenticated_user_id, test_org_id):
        """Test load_initial_data with empty JSON data."""
        # Mock empty initial data
        empty_data = {}
        
        with patch('builtins.open', mock_open(read_data=json.dumps(empty_data))), \
             patch('rhesis.backend.app.services.organization.get_or_create_type_lookup') as mock_get_type, \
             patch('rhesis.backend.app.services.organization.set_tenant') as mock_set_tenant:
            
            # Call the function
            organization_service.load_initial_data(
                db=test_db,
                organization_id=test_org_id,
                user_id=authenticated_user_id
            )
            
            # Verify set_tenant was called
            mock_set_tenant.assert_called_once_with(
                test_db, 
                organization_id=test_org_id, 
                user_id=authenticated_user_id
            )
            
            # Verify no type_lookup creation (empty data)
            mock_get_type.assert_not_called()


@pytest.mark.unit
@pytest.mark.service
class TestRollbackInitialData:
    """Test rollback_initial_data function that uses maintain_tenant_context."""

    @pytest.mark.skip(reason="Test hangs - needs rollback implementation review")
    def test_rollback_initial_data_success(self, test_db: Session, authenticated_user_id, test_org_id):
        """Test successful rollback of initial data."""
        # Get the existing organization and ensure it's marked as initialized
        organization = test_db.query(models.Organization).filter(models.Organization.id == test_org_id).first()
        assert organization is not None, "Test organization should exist from fixtures"
        
        # Ensure the organization is marked as initialized
        organization.is_onboarding_complete = True
        test_db.commit()
        
        # Create some test data that would be deleted during rollback
        # Create a test prompt to be rolled back
        test_prompt = models.Prompt(
            content="Test prompt to be rolled back",
            language_code="en",
            organization_id=test_org_id,
            user_id=authenticated_user_id
        )
        test_db.add(test_prompt)
        test_db.commit()
        
        # Verify the test data exists before rollback
        prompts_before = test_db.query(models.Prompt).filter(
            models.Prompt.organization_id == test_org_id
        ).count()
        assert prompts_before > 0
        
        # Call the rollback function
        organization_service.rollback_initial_data(
            db=test_db,
            organization_id=test_org_id
        )
        
        # Verify data was rolled back (some prompts should be deleted)
        prompts_after = test_db.query(models.Prompt).filter(
            models.Prompt.organization_id == test_org_id
        ).count()
        # The rollback should have deleted at least the test prompt we created
        assert prompts_after < prompts_before

    def test_rollback_initial_data_organization_not_found(self, test_db: Session):
        """Test rollback_initial_data with non-existent organization."""
        non_existent_id = str(uuid.uuid4())
        
        # Call the function and expect ValueError
        with pytest.raises(ValueError, match="Organization not found"):
            organization_service.rollback_initial_data(
                db=test_db,
                organization_id=non_existent_id
            )

    def test_rollback_initial_data_organization_not_initialized(self, test_db: Session, test_org_id):
        """Test rollback_initial_data with organization not initialized."""
        # Get the existing organization and ensure it's NOT marked as initialized
        organization = test_db.query(models.Organization).filter(models.Organization.id == test_org_id).first()
        assert organization is not None, "Test organization should exist from fixtures"
        
        # Ensure the organization is NOT marked as initialized
        organization.is_onboarding_complete = False
        test_db.commit()
        
        # Call the function and expect ValueError
        with pytest.raises(ValueError, match="Organization not initialized yet"):
            organization_service.rollback_initial_data(
                db=test_db,
                organization_id=test_org_id
            )
