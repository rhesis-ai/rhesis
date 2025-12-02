"""
⚙️ User Settings Routes Testing Suite

Comprehensive test suite for user settings endpoints using the enhanced factory system.

Key Features:
- 🏭 Factory-based data generation
- 📊 Deep merge validation
- 🔐 Authentication testing
- 🎯 UUID serialization handling
- ⚡ JSONB mutation tracking validation

Endpoints tested:
- GET /users/settings - Retrieve user settings
- PATCH /users/settings - Update user settings (deep merge)

Run with: python -m pytest tests/backend/routes/test_user_settings.py -v
"""

import uuid
from typing import Dict, Any

import pytest
from faker import Faker
from fastapi import status
from fastapi.testclient import TestClient

# Initialize Faker
fake = Faker()


class TestUserSettingsRoutes:
    """
    ⚙️ Complete user settings route test suite

    Tests user settings functionality including:
    - GET settings retrieval
    - PATCH settings updates with deep merge
    - UUID serialization
    - Validation and error handling
    """

    # === FIXTURES ===

    @pytest.fixture
    def settings_endpoint(self):
        """Return the settings endpoint URL"""
        return "/users/settings"

    @pytest.fixture
    def sample_ui_settings(self):
        """Sample UI settings data"""
        return {
            "theme": "dark",
            "density": "comfortable",
            "sidebar_collapsed": False,
            "default_page_size": 25,
        }

    @pytest.fixture
    def sample_model_settings(self):
        """Sample model settings data with valid UUID"""
        return {
            "generation": {"model_id": str(uuid.uuid4()), "temperature": 0.7, "max_tokens": 2000},
            "evaluation": {"model_id": str(uuid.uuid4()), "temperature": 0.3, "max_tokens": 1000},
        }

    @pytest.fixture
    def sample_notification_settings(self):
        """Sample notification settings data"""
        return {
            "email": {"test_run_complete": True, "test_failures": True, "weekly_summary": False},
            "in_app": {"test_run_complete": True, "mentions": True},
        }

    @pytest.fixture
    def complete_settings(
        self, sample_ui_settings, sample_model_settings, sample_notification_settings
    ):
        """Complete settings data with all categories"""
        return {
            "models": sample_model_settings,
            "ui": sample_ui_settings,
            "notifications": sample_notification_settings,
            "localization": {
                "language": "en",
                "timezone": "UTC",
                "date_format": "YYYY-MM-DD",
                "time_format": "24h",
            },
            "privacy": {"show_email": False, "show_activity": True},
        }

    # === GET SETTINGS TESTS ===

    def test_get_settings_returns_200(self, authenticated_client, settings_endpoint):
        """✅ Test GET settings returns 200 OK"""
        response = authenticated_client.get(settings_endpoint)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() is not None

    def test_get_settings_returns_correct_structure(self, authenticated_client, settings_endpoint):
        """✅ Test GET settings returns correct data structure"""
        response = authenticated_client.get(settings_endpoint)
        data = response.json()

        # Verify top-level structure
        assert "version" in data
        assert "models" in data
        assert "ui" in data
        assert "notifications" in data
        assert "localization" in data
        assert "privacy" in data

        # Verify version
        assert data["version"] == 1

        # Verify nested structures
        assert "generation" in data["models"]
        assert "evaluation" in data["models"]
        assert "email" in data["notifications"]
        assert "in_app" in data["notifications"]

    def test_get_settings_no_id_fields(self, authenticated_client, settings_endpoint):
        """✅ Test GET settings response doesn't include unwanted id/nano_id fields"""
        response = authenticated_client.get(settings_endpoint)
        data = response.json()

        # Top level should not have id/nano_id
        assert "id" not in data
        assert "nano_id" not in data

        # Check nested objects don't have id/nano_id either
        def check_no_ids(obj):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if key in ["id", "nano_id"]:
                        return False
                    if not check_no_ids(value):
                        return False
            elif isinstance(obj, list):
                for item in obj:
                    if not check_no_ids(item):
                        return False
            return True

        assert check_no_ids(data), "Found unwanted id or nano_id fields in response"

    def test_get_settings_requires_authentication(self, client, settings_endpoint):
        """🔐 Test GET settings requires authentication"""
        response = client.get(settings_endpoint)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # === PATCH SETTINGS TESTS ===

    def test_patch_settings_ui_returns_200(
        self, authenticated_client, settings_endpoint, sample_ui_settings
    ):
        """✅ Test PATCH settings with UI data returns 200 OK"""
        update_data = {"ui": sample_ui_settings}

        response = authenticated_client.patch(settings_endpoint, json=update_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["ui"]["theme"] == sample_ui_settings["theme"]
        assert data["ui"]["default_page_size"] == sample_ui_settings["default_page_size"]

    def test_patch_settings_models_with_uuid(
        self, authenticated_client, settings_endpoint, sample_model_settings
    ):
        """✅ Test PATCH settings with model UUIDs persists correctly"""
        update_data = {"models": sample_model_settings}

        response = authenticated_client.patch(settings_endpoint, json=update_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert (
            data["models"]["generation"]["model_id"]
            == sample_model_settings["generation"]["model_id"]
        )
        assert (
            data["models"]["generation"]["temperature"]
            == sample_model_settings["generation"]["temperature"]
        )
        assert (
            data["models"]["evaluation"]["model_id"]
            == sample_model_settings["evaluation"]["model_id"]
        )

    def test_patch_settings_deep_merge(self, authenticated_client, settings_endpoint):
        """✅ Test PATCH settings performs deep merge, not replace"""
        # First, set some UI settings
        first_update = {"ui": {"theme": "dark", "default_page_size": 50}}
        response1 = authenticated_client.patch(settings_endpoint, json=first_update)
        assert response1.status_code == status.HTTP_200_OK

        # Then, update only theme
        second_update = {"ui": {"theme": "light"}}
        response2 = authenticated_client.patch(settings_endpoint, json=second_update)
        assert response2.status_code == status.HTTP_200_OK

        data = response2.json()
        # Theme should be updated
        assert data["ui"]["theme"] == "light"
        # But default_page_size should still be there (deep merge)
        assert data["ui"]["default_page_size"] == 50

    def test_patch_settings_persists_across_requests(
        self, authenticated_client, settings_endpoint, sample_ui_settings
    ):
        """✅ Test PATCH settings persists changes to database"""
        update_data = {"ui": sample_ui_settings}

        # Update settings
        patch_response = authenticated_client.patch(settings_endpoint, json=update_data)
        assert patch_response.status_code == status.HTTP_200_OK

        # Get settings again to verify persistence
        get_response = authenticated_client.get(settings_endpoint)
        assert get_response.status_code == status.HTTP_200_OK

        data = get_response.json()
        assert data["ui"]["theme"] == sample_ui_settings["theme"]
        assert data["ui"]["default_page_size"] == sample_ui_settings["default_page_size"]

    def test_patch_settings_multiple_categories(self, authenticated_client, settings_endpoint):
        """✅ Test PATCH settings with multiple categories at once"""
        update_data = {
            "ui": {"theme": "dark"},
            "notifications": {"email": {"test_run_complete": False}},
        }

        response = authenticated_client.patch(settings_endpoint, json=update_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["ui"]["theme"] == "dark"
        assert data["notifications"]["email"]["test_run_complete"] == False

    def test_patch_settings_preserves_version(self, authenticated_client, settings_endpoint):
        """✅ Test PATCH settings preserves version field"""
        update_data = {"ui": {"theme": "dark"}}

        response = authenticated_client.patch(settings_endpoint, json=update_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["version"] == 1

    def test_patch_settings_requires_authentication(self, client, settings_endpoint):
        """🔐 Test PATCH settings requires authentication"""
        update_data = {"ui": {"theme": "dark"}}

        response = client.patch(settings_endpoint, json=update_data)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # === VALIDATION TESTS ===

    def test_patch_settings_invalid_temperature_range(
        self, authenticated_client, settings_endpoint
    ):
        """❌ Test PATCH settings rejects invalid temperature range"""
        invalid_data = {
            "models": {
                "generation": {
                    "temperature": 3.0  # Invalid: should be 0.0-2.0
                }
            }
        }

        response = authenticated_client.patch(settings_endpoint, json=invalid_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_patch_settings_invalid_page_size(self, authenticated_client, settings_endpoint):
        """❌ Test PATCH settings rejects invalid page size"""
        invalid_data = {
            "ui": {
                "default_page_size": 150  # Invalid: should be <= 100
            }
        }

        response = authenticated_client.patch(settings_endpoint, json=invalid_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_patch_settings_invalid_uuid_format(self, authenticated_client, settings_endpoint):
        """❌ Test PATCH settings rejects invalid UUID format"""
        invalid_data = {"models": {"generation": {"model_id": "not-a-valid-uuid"}}}

        response = authenticated_client.patch(settings_endpoint, json=invalid_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_patch_settings_rejects_extra_fields(self, authenticated_client, settings_endpoint):
        """❌ Test PATCH settings rejects unexpected extra fields"""
        invalid_data = {"ui": {"theme": "dark"}, "invalid_field": "should_be_rejected"}

        response = authenticated_client.patch(settings_endpoint, json=invalid_data)

        # Should reject due to extra='forbid' in schema
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # === EDGE CASE TESTS ===

    def test_patch_settings_with_null_values(self, authenticated_client, settings_endpoint):
        """✅ Test PATCH settings handles null values correctly"""
        # Set a value first
        authenticated_client.patch(settings_endpoint, json={"ui": {"theme": "dark"}})

        # Try to set to null (should be accepted as optional field)
        update_data = {"ui": {"theme": None}}
        response = authenticated_client.patch(settings_endpoint, json=update_data)

        # With exclude_none=True, null values shouldn't update
        # So previous value should remain
        assert response.status_code == status.HTTP_200_OK

    def test_patch_settings_empty_object(self, authenticated_client, settings_endpoint):
        """✅ Test PATCH settings with empty object doesn't break"""
        update_data = {}

        response = authenticated_client.patch(settings_endpoint, json=update_data)

        # Should succeed but not change anything
        assert response.status_code == status.HTTP_200_OK

    def test_patch_settings_partial_nested_update(self, authenticated_client, settings_endpoint):
        """✅ Test PATCH settings with deeply nested partial update"""
        # Set initial notification settings
        initial = {
            "notifications": {
                "email": {"test_run_complete": True, "test_failures": True, "weekly_summary": False}
            }
        }
        authenticated_client.patch(settings_endpoint, json=initial)

        # Update only one email notification setting
        partial_update = {"notifications": {"email": {"weekly_summary": True}}}
        response = authenticated_client.patch(settings_endpoint, json=partial_update)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # All original values should be preserved
        assert data["notifications"]["email"]["test_run_complete"] == True
        assert data["notifications"]["email"]["test_failures"] == True
        # Only weekly_summary should be updated
        assert data["notifications"]["email"]["weekly_summary"] == True

    def test_patch_settings_with_all_optional_fields(
        self, authenticated_client, settings_endpoint, complete_settings
    ):
        """✅ Test PATCH settings with comprehensive data"""
        response = authenticated_client.patch(settings_endpoint, json=complete_settings)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify all categories were updated
        assert data["ui"]["theme"] == complete_settings["ui"]["theme"]
        assert (
            data["models"]["generation"]["temperature"]
            == complete_settings["models"]["generation"]["temperature"]
        )
        assert (
            data["notifications"]["email"]["test_run_complete"]
            == complete_settings["notifications"]["email"]["test_run_complete"]
        )
        assert data["localization"]["language"] == complete_settings["localization"]["language"]
        assert data["privacy"]["show_email"] == complete_settings["privacy"]["show_email"]

    # === UUID HANDLING TESTS ===

    def test_patch_settings_uuid_serialization(self, authenticated_client, settings_endpoint):
        """✅ Test PATCH settings properly serializes UUIDs to strings"""
        model_uuid = str(uuid.uuid4())
        update_data = {"models": {"generation": {"model_id": model_uuid}}}

        response = authenticated_client.patch(settings_endpoint, json=update_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # UUID should be returned as string
        assert isinstance(data["models"]["generation"]["model_id"], str)
        assert data["models"]["generation"]["model_id"] == model_uuid

    def test_patch_settings_multiple_uuids(self, authenticated_client, settings_endpoint):
        """✅ Test PATCH settings handles multiple UUIDs correctly"""
        gen_uuid = str(uuid.uuid4())
        eval_uuid = str(uuid.uuid4())

        update_data = {
            "models": {"generation": {"model_id": gen_uuid}, "evaluation": {"model_id": eval_uuid}}
        }

        response = authenticated_client.patch(settings_endpoint, json=update_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["models"]["generation"]["model_id"] == gen_uuid
        assert data["models"]["evaluation"]["model_id"] == eval_uuid

    # === REGRESSION TESTS ===

    def test_settings_manager_property_reuse(self, authenticated_client, settings_endpoint):
        """✅ Test settings updates don't create new manager instances mid-update"""
        # This tests the fix for the bug where user.settings property
        # created new instances on each access

        update_data = {
            "ui": {"theme": "dark"},
            "models": {"generation": {"model_id": str(uuid.uuid4()), "temperature": 0.8}},
        }

        response = authenticated_client.patch(settings_endpoint, json=update_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Both updates should be present (not lost due to manager re-creation)
        assert data["ui"]["theme"] == "dark"
        assert data["models"]["generation"]["temperature"] == 0.8

    def test_jsonb_mutation_tracking(self, authenticated_client, settings_endpoint):
        """✅ Test JSONB column mutations are properly tracked by SQLAlchemy"""
        # Update settings
        update_data = {"ui": {"theme": "dark"}}
        patch_response = authenticated_client.patch(settings_endpoint, json=update_data)
        assert patch_response.status_code == status.HTTP_200_OK

        # Immediately retrieve to verify flag_modified worked
        get_response = authenticated_client.get(settings_endpoint)
        data = get_response.json()

        assert data["ui"]["theme"] == "dark", "JSONB mutation was not persisted"


# Export test class for pytest discovery
__all__ = ["TestUserSettingsRoutes"]
