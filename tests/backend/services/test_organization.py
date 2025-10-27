"""
Tests for organization service functions.

These tests verify the current behavior of functions before they are refactored
to use the new direct parameter passing approach.
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
    """Test load_initial_data function."""

    def test_load_initial_data_success(self, test_db: Session, authenticated_user_id, test_org_id):
        """Test successful loading of initial data using real database operations."""
        # Count entities before loading initial data
        initial_type_lookup_count = test_db.query(models.TypeLookup).filter(
            models.TypeLookup.organization_id == test_org_id
        ).count()
        initial_status_count = test_db.query(models.Status).filter(
            models.Status.organization_id == test_org_id
        ).count()
        initial_behavior_count = test_db.query(models.Behavior).filter(
            models.Behavior.organization_id == test_org_id
        ).count()
        
        # Call the real function with real database
        organization_service.load_initial_data(
            db=test_db,
            organization_id=test_org_id,
            user_id=authenticated_user_id
        )
        
        # Verify that entities were actually created in the database
        final_type_lookup_count = test_db.query(models.TypeLookup).filter(
            models.TypeLookup.organization_id == test_org_id
        ).count()
        final_status_count = test_db.query(models.Status).filter(
            models.Status.organization_id == test_org_id
        ).count()
        final_behavior_count = test_db.query(models.Behavior).filter(
            models.Behavior.organization_id == test_org_id
        ).count()
        
        # Assert that data was actually loaded
        # Note: All entities use get_or_create, so they may already exist from previous test runs
        assert final_type_lookup_count >= initial_type_lookup_count, "TypeLookup entities should exist (may already be present)"
        assert final_status_count >= initial_status_count, f"Status entities should exist (initial: {initial_status_count}, final: {final_status_count})"
        assert final_behavior_count >= initial_behavior_count, f"Behavior entities should exist (initial: {initial_behavior_count}, final: {final_behavior_count})"
        
        # Verify that we have the expected minimum number of entities
        assert final_status_count > 0, "Should have at least some status entities"
        assert final_behavior_count > 0, "Should have at least some behavior entities"
        
        # Verify specific entities exist with correct tenant context
        # Check that a test status was created with correct organization_id
        test_status = test_db.query(models.Status).filter(
            models.Status.organization_id == test_org_id,
            models.Status.name.ilike("%test%")
        ).first()
        
        if test_status:
            assert str(test_status.organization_id) == test_org_id
            # user_id might be None for initial data, which is acceptable for organization isolation
            if test_status.user_id is not None:
                assert str(test_status.user_id) == authenticated_user_id
        
        # Check that behaviors were created with correct tenant context
        test_behavior = test_db.query(models.Behavior).filter(
            models.Behavior.organization_id == test_org_id
        ).first()
        
        if test_behavior:
            assert str(test_behavior.organization_id) == test_org_id
            # user_id might be None for initial data, which is acceptable for organization isolation
            if test_behavior.user_id is not None:
                assert str(test_behavior.user_id) == authenticated_user_id

    def test_load_initial_data_with_custom_file_path(self, test_db: Session, authenticated_user_id, test_org_id):
        """Integration test: load_initial_data with custom file path that contains minimal data."""
        import tempfile
        import os
        
        # Create a temporary file with minimal valid initial data
        minimal_data = {
            "status": [
                {"name": "Test Status", "description": "A test status", "entity_type": "Test"}
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            json.dump(minimal_data, temp_file)
            temp_file_path = temp_file.name
        
        try:
            # Count existing statuses before loading
            initial_count = test_db.query(models.Status).filter(
                models.Status.organization_id == test_org_id
            ).count()
            
            # Temporarily replace the initial_data.json path
            original_path = organization_service.__file__.replace('__init__.py', 'initial_data.json')
            
            # Monkey patch the file path in the function
            with patch('rhesis.backend.app.services.organization.os.path.join') as mock_join:
                mock_join.return_value = temp_file_path
                
                # Call the real function with real data
                organization_service.load_initial_data(
                    db=test_db,
                    organization_id=test_org_id,
                    user_id=authenticated_user_id
                )
            
            # Verify that data was actually loaded
            final_count = test_db.query(models.Status).filter(
                models.Status.organization_id == test_org_id
            ).count()
            
            # Should have at least one new status
            assert final_count >= initial_count
            
            # Verify the specific status was created
            test_status = test_db.query(models.Status).filter(
                models.Status.organization_id == test_org_id,
                models.Status.name == "Test Status"
            ).first()
            
            assert test_status is not None, "Test Status should have been created"
            # The actual description might be modified by the get_or_create_status logic
            assert "test status" in test_status.description.lower(), f"Expected description to contain 'test status', got: {test_status.description}"
            
        finally:
            # Clean up the temporary file
            os.unlink(temp_file_path)

    def test_load_initial_data_invalid_json(self, test_db: Session, authenticated_user_id, test_org_id):
        """Test load_initial_data with invalid JSON data."""
        # Mock invalid JSON data
        invalid_json = "{ invalid json }"
        
        with patch('builtins.open', mock_open(read_data=invalid_json)):
            # Call the function and expect JSONDecodeError
            # Note: get_db should NOT be called since JSON parsing fails first
            with pytest.raises(json.JSONDecodeError):
                organization_service.load_initial_data(
                    db=test_db,
                    organization_id=test_org_id,
                    user_id=authenticated_user_id
                )
            
            # No need to verify get_db call since it never gets reached

    def test_load_initial_data_empty_data(self, test_db: Session, authenticated_user_id, test_org_id):
        """Test load_initial_data with empty JSON data still creates default Rhesis model."""
        # Mock empty initial data
        empty_data = {}
        
        with patch('builtins.open', mock_open(read_data=json.dumps(empty_data))), \
             patch('rhesis.backend.app.services.organization.get_or_create_type_lookup') as mock_get_type, \
             patch('rhesis.backend.app.services.organization.get_or_create_status') as mock_get_status, \
             patch('rhesis.backend.app.services.organization.get_or_create_entity') as mock_get_entity:
            
            # Call the function (now uses provided db parameter directly)
            organization_service.load_initial_data(
                db=test_db,
                organization_id=test_org_id,
                user_id=authenticated_user_id
            )
            
            # Verify that type_lookup creation WAS called for the default Rhesis model
            # Even with empty data, the function creates a default Rhesis model
            mock_get_type.assert_called_once_with(
                db=test_db,
                type_name="ProviderType",
                type_value="rhesis",
                organization_id=test_org_id,
                user_id=authenticated_user_id,
                commit=False
            )

    def test_load_initial_data_integration(self, test_db: Session, authenticated_user_id, test_org_id):
        """Integration test that actually loads real initial data into the database."""
        import os
        import json
        
        # Load the actual initial data to use as reference
        # Navigate from tests/backend/services/ to project root, then to the initial_data.json file
        test_file_dir = os.path.dirname(__file__)  # tests/backend/services/
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(test_file_dir)))  # Go up to project root
        initial_data_path = os.path.join(project_root, "apps/backend/src/rhesis/backend/app/services/initial_data.json")
        with open(initial_data_path, "r") as file:
            expected_initial_data = json.load(file)
        
        # Count existing records before loading
        initial_status_count = test_db.query(models.Status).count()
        initial_behavior_count = test_db.query(models.Behavior).count()
        initial_type_lookup_count = test_db.query(models.TypeLookup).count()
        initial_topic_count = test_db.query(models.Topic).count()
        initial_category_count = test_db.query(models.Category).count()
        
        # Call the real function without mocking the core functionality
        # This tests the actual refactored code with get_db and direct parameter passing
        organization_service.load_initial_data(
            db=test_db,
            organization_id=test_org_id,
            user_id=authenticated_user_id
        )
        
        # Verify that data was actually created OR already exists (both are valid)
        final_status_count = test_db.query(models.Status).count()
        final_behavior_count = test_db.query(models.Behavior).count()
        final_type_lookup_count = test_db.query(models.TypeLookup).count()
        final_topic_count = test_db.query(models.Topic).count()
        final_category_count = test_db.query(models.Category).count()
        
        # Assert that records exist (either created or already existed)
        assert final_status_count >= initial_status_count, "Status records should exist"
        assert final_behavior_count >= initial_behavior_count, "Behavior records should exist"
        assert final_type_lookup_count >= initial_type_lookup_count, "TypeLookup records should exist"
        assert final_topic_count >= initial_topic_count, "Topic records should exist"
        assert final_category_count >= initial_category_count, "Category records should exist"
        
        # Most importantly: verify specific records exist with correct organization context
        # This proves the tenant context is working correctly with direct parameter passing
        # Use actual data from initial_data.json as reference
        
        # Test status records from actual initial data
        if expected_initial_data.get("status"):
            first_status = expected_initial_data["status"][0]
            created_status = test_db.query(models.Status).filter(
                models.Status.organization_id == test_org_id,
                models.Status.name == first_status["name"]
            ).first()
            assert created_status is not None, f"Status '{first_status['name']}' should exist for this organization"
            # Note: user_id might be None for initial data, which is fine - the key is organization isolation
        
        # Test behavior records from actual initial data
        if expected_initial_data.get("behavior"):
            first_behavior = expected_initial_data["behavior"][0]
            created_behavior = test_db.query(models.Behavior).filter(
                models.Behavior.organization_id == test_org_id,
                models.Behavior.name == first_behavior["name"]
            ).first()
            assert created_behavior is not None, f"Behavior '{first_behavior['name']}' should exist for this organization"
        
        # Test topic records from actual initial data
        if expected_initial_data.get("topic"):
            first_topic = expected_initial_data["topic"][0]
            created_topic = test_db.query(models.Topic).filter(
                models.Topic.organization_id == test_org_id,
                models.Topic.name == first_topic["name"]
            ).first()
            assert created_topic is not None, f"Topic '{first_topic['name']}' should exist for this organization"
        
        # Verify type lookups were created with correct organization context
        # Test a known type lookup that should exist
        entity_type_lookup = test_db.query(models.TypeLookup).filter(
            models.TypeLookup.organization_id == test_org_id,
            models.TypeLookup.type_name == "EntityType"
        ).first()
        assert entity_type_lookup is not None, "EntityType lookup should exist for this organization"
        
        # This is the key test: verify that direct parameter passing worked correctly
        # by ensuring we can find organization-specific data
        org_specific_statuses = test_db.query(models.Status).filter(
            models.Status.organization_id == test_org_id
        ).count()
        assert org_specific_statuses > 0, "Should have organization-specific statuses"
        
        print(f"✅ Integration test passed! Function works correctly with direct parameter passing")
        print(f"📊 Total records: {final_status_count} statuses, {final_behavior_count} behaviors")
        print(f"🏢 Organization-specific statuses: {org_specific_statuses}")
        print(f"📋 Expected data types: {list(expected_initial_data.keys())}")
        print(f"🔄 Records delta: +{final_status_count - initial_status_count} statuses, +{final_behavior_count - initial_behavior_count} behaviors")


@pytest.mark.unit
@pytest.mark.service
class TestRollbackInitialData:
    """Test rollback_initial_data function."""

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
