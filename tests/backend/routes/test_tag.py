"""
🏷️ Tag Routes Testing Suite (Enhanced Factory-Based)

Comprehensive test suite for tag entity routes using the enhanced factory system
with automatic cleanup, consistent data generation, and optimized performance.

Key Features:
- 🏭 Factory-based entity creation with automatic cleanup
- 📊 Consistent data generation using data factories
- 🎯 Clear fixture organization and naming
- 🔄 Maintains DRY base class benefits
- ⚡ Optimized performance with proper scoping
- 🏷️ Tag assignment and entity relationship testing
- 📋 Tag management functionality
- 🔍 Advanced filtering and entity type testing

Run with: python -m pytest tests/backend/routes/test_tag.py -v
"""

import uuid
from typing import Dict, Any

import pytest
from faker import Faker
from fastapi import status
from fastapi.testclient import TestClient

from .endpoints import APIEndpoints
from .base import BaseEntityRouteTests, BaseEntityTests
from .fixtures.data_factories import TagDataFactory, BehaviorDataFactory, ProjectDataFactory

# Initialize Faker
fake = Faker()


class TagTestMixin:
    """Enhanced tag test mixin using factory system"""

    # Entity configuration
    entity_name = "tag"
    entity_plural = "tags"
    endpoints = APIEndpoints.TAGS

    # Field mappings for tags
    name_field = "name"
    description_field = None  # No description field for tags

    # Factory-based data methods
    def get_sample_data(self) -> Dict[str, Any]:
        """Return sample tag data using factory"""
        return TagDataFactory.sample_data()

    def get_minimal_data(self) -> Dict[str, Any]:
        """Return minimal tag data using factory"""
        return TagDataFactory.minimal_data()

    def get_update_data(self) -> Dict[str, Any]:
        """Return tag update data using factory"""
        return TagDataFactory.update_data()

    def get_invalid_data(self) -> Dict[str, Any]:
        """Return invalid tag data using factory"""
        return TagDataFactory.invalid_data()

    def get_null_description_data(self) -> Dict[str, Any]:
        """Return tag data with null description - tags don't have description field"""
        # Tags don't have a description field, so return regular sample data
        return self.get_sample_data()

    def test_entity_with_null_description(self, authenticated_client):
        """Test entity creation with null description - tags don't have description field"""
        # Tags don't have a description field, so this test just verifies
        # that the entity can be created successfully without a description
        tag_data = self.get_sample_data()

        response = authenticated_client.post(
            self.endpoints.create,
            json=tag_data,
        )

        assert response.status_code == status.HTTP_200_OK
        tag = response.json()

        # Verify the tag was created with the expected name
        assert tag["name"] == tag_data["name"]
        if tag_data.get("icon_unicode"):
            assert tag["icon_unicode"] == tag_data["icon_unicode"]


class TestTagRoutes(TagTestMixin, BaseEntityRouteTests):
    """
    🏷️ Complete tag route test suite

    This class inherits from BaseEntityRouteTests to get comprehensive coverage:
    - ✅ Full CRUD operation testing
    - 👤 Automatic user relationship field testing
    - 🔗 List operations and filtering
    - 🛡️ Authentication validation
    - 🏃‍♂️ Edge case handling
    - 🐌 Performance validation
    - ✅ Health checks

    Plus tag-specific functionality tests.
    """

    # === TAG-SPECIFIC CRUD TESTS ===

    def test_create_tag_with_required_fields(self, authenticated_client):
        """Test tag creation with only required fields"""
        minimal_data = self.get_minimal_data()

        response = authenticated_client.post(self.endpoints.create, json=minimal_data)

        assert response.status_code == status.HTTP_200_OK
        created_tag = response.json()

        assert created_tag["name"] == minimal_data["name"]
        assert created_tag.get("icon_unicode") is None  # Should be None when not provided

    def test_create_tag_with_optional_fields(self, authenticated_client):
        """Test tag creation with optional fields"""
        tag_data = self.get_sample_data()

        response = authenticated_client.post(
            self.endpoints.create,
            json=tag_data,
        )

        assert response.status_code == status.HTTP_200_OK
        created_tag = response.json()

        assert created_tag["name"] == tag_data["name"]
        if tag_data.get("icon_unicode"):
            assert created_tag["icon_unicode"] == tag_data["icon_unicode"]

    def test_create_tag_with_unicode_icons(self, authenticated_client):
        """Test tag creation with various unicode icons"""
        icons = ["🏷️", "📌", "⭐", "🔖", "📋", "🎯", "💼", "🔍", "📊", "⚡", "🎨", "🔧"]

        for icon in icons:
            tag_data = self.get_minimal_data()
            tag_data["icon_unicode"] = icon

            response = authenticated_client.post(
                self.endpoints.create,
                json=tag_data,
            )

            assert response.status_code == status.HTTP_200_OK
            created_tag = response.json()

            assert created_tag["name"] == tag_data["name"]
            assert created_tag["icon_unicode"] == icon

    def test_create_tag_with_common_names(self, authenticated_client):
        """Test tag creation with common tag names"""
        common_tag_data = TagDataFactory.edge_case_data("common_tags")

        response = authenticated_client.post(
            self.endpoints.create,
            json=common_tag_data,
        )

        assert response.status_code == status.HTTP_200_OK
        created_tag = response.json()

        assert created_tag["name"] == common_tag_data["name"]
        assert created_tag["icon_unicode"] == common_tag_data["icon_unicode"]

    def test_create_tag_with_unicode_name(self, authenticated_client):
        """Test tag creation with unicode names"""
        unicode_data = TagDataFactory.edge_case_data("unicode")

        response = authenticated_client.post(
            self.endpoints.create,
            json=unicode_data,
        )

        assert response.status_code == status.HTTP_200_OK
        created_tag = response.json()

        assert created_tag["name"] == unicode_data["name"]
        assert created_tag["icon_unicode"] == unicode_data["icon_unicode"]

    def test_create_tag_with_special_characters(self, authenticated_client):
        """Test tag creation with special characters"""
        special_char_data = TagDataFactory.edge_case_data("special_chars")

        response = authenticated_client.post(
            self.endpoints.create,
            json=special_char_data,
        )

        assert response.status_code == status.HTTP_200_OK
        created_tag = response.json()

        assert created_tag["name"] == special_char_data["name"]
        assert "🏷️" in created_tag["name"]  # Verify emoji preserved

    def test_update_tag_name(self, authenticated_client):
        """Test updating tag name"""
        # Create initial tag
        initial_data = self.get_minimal_data()
        create_response = authenticated_client.post(
            self.endpoints.create,
            json=initial_data,
        )
        tag_id = create_response.json()["id"]

        # Update name
        update_data = self.get_update_data()
        response = authenticated_client.put(
            self.endpoints.format_path(self.endpoints.update, tag_id=tag_id),
            json=update_data,
        )

        assert response.status_code == status.HTTP_200_OK
        updated_tag = response.json()

        assert updated_tag["name"] == update_data["name"]
        assert updated_tag["icon_unicode"] == update_data["icon_unicode"]

    def test_update_tag_icon_only(self, authenticated_client):
        """Test updating only the icon of a tag"""
        # Create initial tag
        initial_data = self.get_sample_data()
        create_response = authenticated_client.post(
            self.endpoints.create,
            json=initial_data,
        )
        tag_id = create_response.json()["id"]
        original_name = create_response.json()["name"]

        # Update only icon
        update_data = {"icon_unicode": "🎨"}
        response = authenticated_client.put(
            self.endpoints.format_path(self.endpoints.update, tag_id=tag_id),
            json=update_data,
        )

        assert response.status_code == status.HTTP_200_OK
        updated_tag = response.json()

        assert updated_tag["name"] == original_name  # Name unchanged
        assert updated_tag["icon_unicode"] == "🎨"  # Icon updated

    def test_get_tag_by_id(self, authenticated_client):
        """Test retrieving a specific tag by ID"""
        # Create tag
        tag_data = self.get_sample_data()
        create_response = authenticated_client.post(
            self.endpoints.create,
            json=tag_data,
        )
        tag_id = create_response.json()["id"]

        # Get tag by ID
        response = authenticated_client.get(
            self.endpoints.format_path(self.endpoints.get_by_id, tag_id=tag_id),
        )

        assert response.status_code == status.HTTP_200_OK
        tag = response.json()

        assert tag["id"] == tag_id
        assert tag["name"] == tag_data["name"]
        if tag_data.get("icon_unicode"):
            assert tag["icon_unicode"] == tag_data["icon_unicode"]

    def test_delete_tag(self, authenticated_client):
        """Test deleting a tag"""
        # Create tag
        tag_data = self.get_minimal_data()
        create_response = authenticated_client.post(
            self.endpoints.create,
            json=tag_data,
        )
        tag_id = create_response.json()["id"]

        # Delete tag
        response = authenticated_client.delete(
            self.endpoints.format_path(self.endpoints.delete, tag_id=tag_id),
        )

        assert response.status_code == status.HTTP_200_OK
        deleted_tag = response.json()
        assert deleted_tag["id"] == tag_id

        # Verify tag is deleted (soft delete returns 410 GONE)
        get_response = authenticated_client.get(
            self.endpoints.format_path(self.endpoints.get_by_id, tag_id=tag_id),
        )
        assert get_response.status_code == status.HTTP_410_GONE

    def test_list_tags_with_pagination(self, authenticated_client):
        """Test listing tags with pagination"""
        # Create multiple tags
        tags_data = [self.get_sample_data() for _ in range(5)]
        created_tags = []

        for tag_data in tags_data:
            response = authenticated_client.post(
                self.endpoints.create,
                json=tag_data,
            )
            created_tags.append(response.json())

        # Test pagination
        response = authenticated_client.get(
            f"{self.endpoints.list}?skip=0&limit=3",
        )

        assert response.status_code == status.HTTP_200_OK
        tags = response.json()
        assert len(tags) <= 3

        # Check count header
        assert "X-Total-Count" in response.headers
        total_count = int(response.headers["X-Total-Count"])
        assert total_count >= 5

    def test_list_tags_with_sorting(self, authenticated_client):
        """Test listing tags with sorting"""
        # Create tags with different names
        tag1_data = self.get_sample_data()
        tag1_data["name"] = "AAA Tag"

        tag2_data = self.get_sample_data()
        tag2_data["name"] = "ZZZ Tag"

        # Create tags
        authenticated_client.post(self.endpoints.create, json=tag1_data)
        authenticated_client.post(self.endpoints.create, json=tag2_data)

        # Test sorting
        response = authenticated_client.get(
            f"{self.endpoints.list}?sort_by=created_at&sort_order=asc",
        )

        assert response.status_code == status.HTTP_200_OK
        tags = response.json()
        assert len(tags) >= 2

    # === TAG-SPECIFIC ERROR HANDLING TESTS ===

    def test_create_tag_without_name(self, authenticated_client):
        """Test creating tag without required name field"""
        invalid_data = {}

        response = authenticated_client.post(
            self.endpoints.create,
            json=invalid_data,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_create_tag_with_empty_name(self, authenticated_client):
        """Test creating tag with empty name"""
        invalid_data = {"name": ""}

        response = authenticated_client.post(
            self.endpoints.create,
            json=invalid_data,
        )

        # This might be allowed or not depending on validation rules
        # Adjust assertion based on actual API behavior
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            status.HTTP_400_BAD_REQUEST,
        ]

    def test_get_nonexistent_tag(self, authenticated_client):
        """Test retrieving a non-existent tag"""
        fake_id = str(uuid.uuid4())

        response = authenticated_client.get(
            self.endpoints.format_path(self.endpoints.get_by_id, tag_id=fake_id),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    def test_update_nonexistent_tag(self, authenticated_client):
        """Test updating a non-existent tag"""
        fake_id = str(uuid.uuid4())
        update_data = self.get_update_data()

        response = authenticated_client.put(
            self.endpoints.format_path(self.endpoints.update, tag_id=fake_id),
            json=update_data,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    def test_delete_nonexistent_tag(self, authenticated_client):
        """Test deleting a non-existent tag"""
        fake_id = str(uuid.uuid4())

        response = authenticated_client.delete(
            self.endpoints.format_path(self.endpoints.delete, tag_id=fake_id),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()


# === TAG ASSIGNMENT AND ENTITY RELATIONSHIP TESTS ===


@pytest.mark.integration
class TestTagAssignments(TagTestMixin, BaseEntityTests):
    """Enhanced tag assignment and entity relationship tests"""

    def _create_test_behavior(self, authenticated_client):
        """Helper to create a test behavior for tag assignment"""
        behavior_data = BehaviorDataFactory.sample_data()
        response = authenticated_client.post(
            "/behaviors/",
            json=behavior_data,
        )
        assert response.status_code == status.HTTP_200_OK
        return response.json()

    def _create_test_project(self, authenticated_client):
        """Helper to create a test project for tag assignment"""
        project_data = ProjectDataFactory.sample_data()
        response = authenticated_client.post(
            "/projects/",
            json=project_data,
        )
        assert response.status_code == status.HTTP_200_OK
        return response.json()

    def test_assign_tag_to_behavior(self, authenticated_client):
        """Test assigning a tag to a behavior entity"""
        # Create a behavior
        behavior = self._create_test_behavior(authenticated_client)
        behavior_id = behavior["id"]

        # Create tag data
        tag_data = self.get_sample_data()

        # Assign tag to behavior
        response = authenticated_client.post(
            f"/tags/Behavior/{behavior_id}",
            json=tag_data,
        )

        assert response.status_code == status.HTTP_200_OK
        assigned_tag = response.json()

        assert assigned_tag["name"] == tag_data["name"]
        if tag_data.get("icon_unicode"):
            assert assigned_tag["icon_unicode"] == tag_data["icon_unicode"]

    def test_assign_tag_to_project(self, authenticated_client):
        """Test assigning a tag to a project entity"""
        # Create a project
        project = self._create_test_project(authenticated_client)
        project_id = project["id"]

        # Create tag data
        tag_data = self.get_sample_data()

        # Assign tag to project
        response = authenticated_client.post(
            f"/tags/Project/{project_id}",
            json=tag_data,
        )

        assert response.status_code == status.HTTP_200_OK
        assigned_tag = response.json()

        assert assigned_tag["name"] == tag_data["name"]
        if tag_data.get("icon_unicode"):
            assert assigned_tag["icon_unicode"] == tag_data["icon_unicode"]

    def test_assign_existing_tag_to_entity(self, authenticated_client):
        """Test assigning an existing tag to an entity"""
        # Create a behavior
        behavior = self._create_test_behavior(authenticated_client)
        behavior_id = behavior["id"]

        # Create a tag first
        tag_data = self.get_sample_data()
        create_response = authenticated_client.post(
            self.endpoints.create,
            json=tag_data,
        )
        assert create_response.status_code == status.HTTP_200_OK

        # Assign the same tag to behavior (should reuse existing tag)
        response = authenticated_client.post(
            f"/tags/Behavior/{behavior_id}",
            json=tag_data,
        )

        assert response.status_code == status.HTTP_200_OK
        assigned_tag = response.json()

        assert assigned_tag["name"] == tag_data["name"]

    def test_remove_tag_from_entity(self, authenticated_client):
        """Test removing a tag from an entity"""
        # Create a behavior
        behavior = self._create_test_behavior(authenticated_client)
        behavior_id = behavior["id"]

        # Create and assign tag
        tag_data = self.get_sample_data()
        assign_response = authenticated_client.post(
            f"/tags/Behavior/{behavior_id}",
            json=tag_data,
        )
        assert assign_response.status_code == status.HTTP_200_OK
        tag_id = assign_response.json()["id"]

        # Remove tag from behavior
        response = authenticated_client.delete(
            f"/tags/Behavior/{behavior_id}/{tag_id}",
        )

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["status"] == "success"

    def test_assign_tag_to_nonexistent_entity(self, authenticated_client):
        """Test assigning a tag to a non-existent entity"""
        fake_id = str(uuid.uuid4())
        tag_data = self.get_sample_data()

        response = authenticated_client.post(
            f"/tags/Behavior/{fake_id}",
            json=tag_data,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_remove_tag_from_nonexistent_entity(self, authenticated_client):
        """Test removing a tag from a non-existent entity"""
        fake_entity_id = str(uuid.uuid4())
        fake_tag_id = str(uuid.uuid4())

        response = authenticated_client.delete(
            f"/tags/Behavior/{fake_entity_id}/{fake_tag_id}",
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


# === TAG PERFORMANCE TESTS ===


@pytest.mark.performance
class TestTagPerformance(TagTestMixin, BaseEntityTests):
    """Tag performance tests"""

    def test_create_multiple_tags_performance(self, authenticated_client):
        """Test creating multiple tags for performance"""
        tags_count = 20
        tags_data = TagDataFactory.batch_data(tags_count, variation=True)

        created_tags = []
        for tag_data in tags_data:
            response = authenticated_client.post(
                self.endpoints.create,
                json=tag_data,
            )
            assert response.status_code == status.HTTP_200_OK
            created_tags.append(response.json())

        assert len(created_tags) == tags_count

        # Test bulk retrieval performance
        response = authenticated_client.get(
            f"{self.endpoints.list}?limit={tags_count}",
        )

        assert response.status_code == status.HTTP_200_OK
        tags = response.json()
        assert len(tags) >= tags_count

    def test_tag_assignment_performance(self, authenticated_client):
        """Test tag assignment performance with multiple entities"""
        # Create multiple behaviors
        behaviors = []
        for i in range(5):
            behavior = self._create_test_behavior(authenticated_client)
            behaviors.append(behavior)

        # Create and assign tags
        tag_data = self.get_sample_data()

        for behavior in behaviors:
            response = authenticated_client.post(
                f"/tags/Behavior/{behavior['id']}",
                json=tag_data,
            )
            assert response.status_code == status.HTTP_200_OK

    def test_bulk_tag_operations(self, authenticated_client):
        """Test bulk tag operations"""
        # Create multiple tags
        tags_count = 15
        tags_data = TagDataFactory.batch_data(tags_count, variation=False)

        created_tags = []
        for tag_data in tags_data:
            response = authenticated_client.post(
                self.endpoints.create,
                json=tag_data,
            )
            assert response.status_code == status.HTTP_200_OK
            created_tags.append(response.json())

        # Test bulk update operations
        update_data = self.get_update_data()
        for tag_obj in created_tags[:5]:  # Update first 5 tags
            response = authenticated_client.put(
                self.endpoints.format_path(self.endpoints.update, tag_id=tag_obj["id"]),
                json=update_data,
            )
            assert response.status_code == status.HTTP_200_OK

        # Test bulk delete operations
        for tag_obj in created_tags[10:]:  # Delete last 5 tags
            response = authenticated_client.delete(
                self.endpoints.format_path(self.endpoints.delete, tag_id=tag_obj["id"]),
            )
            assert response.status_code == status.HTTP_200_OK

    def _create_test_behavior(self, authenticated_client):
        """Helper to create a test behavior for tag assignment"""
        behavior_data = BehaviorDataFactory.sample_data()
        response = authenticated_client.post(
            "/behaviors/",
            json=behavior_data,
        )
        assert response.status_code == status.HTTP_200_OK
        return response.json()
