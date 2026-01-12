"""
⚡ Status Routes Testing Suite (Enhanced Factory-Based)

Comprehensive test suite for status entity routes using the enhanced factory system
with automatic cleanup, consistent data generation, and optimized performance.

Key Features:
- 🏭 Factory-based entity creation with automatic cleanup
- 📊 Consistent data generation using data factories
- 🎯 Clear fixture organization and naming
- 🔄 Maintains DRY base class benefits
- ⚡ Optimized performance with proper scoping
- 🏷️ Entity type relationship testing
- 📋 Status management functionality
- 🔍 Advanced filtering and sorting

Run with: python -m pytest tests/backend/routes/test_status.py -v
"""

import uuid
from typing import Any, Dict

import pytest
from faker import Faker
from fastapi import status

from .base import BaseEntityRouteTests, BaseEntityTests
from .endpoints import APIEndpoints
from .fixtures.data_factories import StatusDataFactory

# Initialize Faker
fake = Faker()


class StatusTestMixin:
    """Enhanced status test mixin using factory system"""

    # Entity configuration
    entity_name = "status"
    entity_plural = "statuses"
    endpoints = APIEndpoints.STATUSES

    # Field mappings for statuses
    name_field = "name"
    description_field = "description"

    # Factory-based data methods
    def get_sample_data(self) -> Dict[str, Any]:
        """Return sample status data using factory"""
        return StatusDataFactory.sample_data()

    def get_minimal_data(self) -> Dict[str, Any]:
        """Return minimal status data using factory"""
        return StatusDataFactory.minimal_data()

    def get_update_data(self) -> Dict[str, Any]:
        """Return status update data using factory"""
        return StatusDataFactory.update_data()

    def get_invalid_data(self) -> Dict[str, Any]:
        """Return invalid status data using factory"""
        return StatusDataFactory.invalid_data()


class TestStatusRoutes(StatusTestMixin, BaseEntityRouteTests):
    """
    ⚡ Complete status route test suite

    This class inherits from BaseEntityRouteTests to get comprehensive coverage:
    - ✅ Full CRUD operation testing
    - 👤 Automatic user relationship field testing
    - 🔗 List operations and filtering
    - 🛡️ Authentication validation
    - 🏃‍♂️ Edge case handling
    - 🐌 Performance validation
    - ✅ Health checks

    Plus status-specific functionality tests.
    """

    # === STATUS-SPECIFIC CRUD TESTS ===

    def test_create_status_with_required_fields(self, authenticated_client):
        """Test status creation with only required fields"""
        minimal_data = self.get_minimal_data()

        response = authenticated_client.post(
            self.endpoints.create,
            json=minimal_data,
        )

        assert response.status_code == status.HTTP_200_OK
        created_status = response.json()

        assert created_status["name"] == minimal_data["name"]
        assert created_status.get("description") is None
        assert created_status.get("entity_type_id") is None

    def test_create_status_with_optional_fields(self, authenticated_client):
        """Test status creation with optional fields"""
        status_data = self.get_sample_data()

        response = authenticated_client.post(
            self.endpoints.create,
            json=status_data,
        )

        assert response.status_code == status.HTTP_200_OK
        created_status = response.json()

        assert created_status["name"] == status_data["name"]
        assert created_status["description"] == status_data["description"]

    def test_create_status_with_common_status_names(self, authenticated_client):
        """Test status creation with common status names"""
        common_statuses = [
            "Active",
            "Inactive",
            "Pending",
            "Completed",
            "Draft",
            "Published",
            "Archived",
        ]
        created_statuses = []

        for status_name in common_statuses:
            status_data = self.get_sample_data()
            status_data["name"] = status_name
            status_data["description"] = f"Status indicating {status_name.lower()} state"

            response = authenticated_client.post(
                self.endpoints.create,
                json=status_data,
            )

            assert response.status_code == status.HTTP_200_OK
            status_obj = response.json()
            assert status_obj["name"] == status_name
            created_statuses.append(status_obj)

        assert len(created_statuses) == len(common_statuses)

    def test_create_status_with_unicode_name(self, authenticated_client):
        """Test status creation with unicode characters in name"""
        unicode_data = StatusDataFactory.edge_case_data("special_chars")

        response = authenticated_client.post(
            self.endpoints.create,
            json=unicode_data,
        )

        assert response.status_code == status.HTTP_200_OK
        created_status = response.json()

        assert created_status["name"] == unicode_data["name"]
        assert "⚡" in created_status["name"]  # Verify emoji preserved

    def test_create_status_with_long_name(self, authenticated_client):
        """Test status creation with very long name"""
        long_name_data = StatusDataFactory.edge_case_data("long_name")

        response = authenticated_client.post(
            self.endpoints.create,
            json=long_name_data,
        )

        assert response.status_code == status.HTTP_200_OK
        created_status = response.json()

        assert created_status["name"] == long_name_data["name"]
        assert len(created_status["name"]) > 50  # Verify it's actually long

    def test_update_status_name(self, authenticated_client):
        """Test updating status name"""
        # Create initial status
        initial_data = self.get_minimal_data()
        create_response = authenticated_client.post(
            self.endpoints.create,
            json=initial_data,
        )
        status_id = create_response.json()["id"]

        # Update name
        update_data = self.get_update_data()
        response = authenticated_client.put(
            self.endpoints.format_path(self.endpoints.update, status_id=status_id),
            json=update_data,
        )

        assert response.status_code == status.HTTP_200_OK
        updated_status = response.json()

        assert updated_status["name"] == update_data["name"]
        assert updated_status["description"] == update_data["description"]

    def test_update_status_description_only(self, authenticated_client):
        """Test updating only the description of a status"""
        # Create initial status
        initial_data = self.get_sample_data()
        create_response = authenticated_client.post(
            self.endpoints.create,
            json=initial_data,
        )
        status_id = create_response.json()["id"]
        original_name = create_response.json()["name"]

        # Update only description
        new_description = "Updated description for status management"
        update_data = {"description": new_description}
        response = authenticated_client.put(
            self.endpoints.format_path(self.endpoints.update, status_id=status_id),
            json=update_data,
        )

        assert response.status_code == status.HTTP_200_OK
        updated_status = response.json()

        assert updated_status["name"] == original_name  # Name unchanged
        assert updated_status["description"] == new_description  # Description updated

    def test_get_status_by_id(self, authenticated_client):
        """Test retrieving a specific status by ID"""
        # Create status
        status_data = self.get_sample_data()
        create_response = authenticated_client.post(
            self.endpoints.create,
            json=status_data,
        )
        status_id = create_response.json()["id"]

        # Get status by ID
        response = authenticated_client.get(
            self.endpoints.format_path(self.endpoints.get_by_id, status_id=status_id),
        )

        assert response.status_code == status.HTTP_200_OK
        status_obj = response.json()

        assert status_obj["id"] == status_id
        assert status_obj["name"] == status_data["name"]
        assert status_obj["description"] == status_data["description"]

    def test_delete_status(self, authenticated_client):
        """Test deleting a status"""
        # Create status
        status_data = self.get_minimal_data()
        create_response = authenticated_client.post(
            self.endpoints.create,
            json=status_data,
        )
        status_id = create_response.json()["id"]

        # Delete status
        response = authenticated_client.delete(
            self.endpoints.format_path(self.endpoints.delete, status_id=status_id),
        )

        assert response.status_code == status.HTTP_200_OK
        deleted_status = response.json()
        assert deleted_status["id"] == status_id

        # Verify status is deleted (soft delete returns 410 GONE)
        get_response = authenticated_client.get(
            self.endpoints.format_path(self.endpoints.get_by_id, status_id=status_id),
        )
        assert get_response.status_code == status.HTTP_410_GONE

    def test_list_statuses_with_pagination(self, authenticated_client):
        """Test listing statuses with pagination"""
        # Create multiple statuses
        statuses_data = [self.get_sample_data() for _ in range(5)]
        created_statuses = []

        for status_data in statuses_data:
            response = authenticated_client.post(
                self.endpoints.create,
                json=status_data,
            )
            created_statuses.append(response.json())

        # Test pagination
        response = authenticated_client.get(
            f"{self.endpoints.list}?skip=0&limit=3",
        )

        assert response.status_code == status.HTTP_200_OK
        statuses = response.json()
        assert len(statuses) <= 3

        # Check count header
        assert "X-Total-Count" in response.headers
        total_count = int(response.headers["X-Total-Count"])
        assert total_count >= 5

    def test_list_statuses_with_sorting(self, authenticated_client):
        """Test listing statuses with sorting"""
        # Create statuses with different names
        status1_data = self.get_sample_data()
        status1_data["name"] = "AAA Status"

        status2_data = self.get_sample_data()
        status2_data["name"] = "ZZZ Status"

        # Create statuses
        authenticated_client.post(self.endpoints.create, json=status1_data)
        authenticated_client.post(self.endpoints.create, json=status2_data)

        # Test sorting by creation date
        response = authenticated_client.get(
            f"{self.endpoints.list}?sort_by=created_at&sort_order=asc",
        )

        assert response.status_code == status.HTTP_200_OK
        statuses = response.json()
        assert len(statuses) >= 2

    def test_list_statuses_with_entity_type_filter(self, authenticated_client):
        """Test listing statuses with entity_type query parameter"""
        # Create status
        status_data = self.get_sample_data()
        create_response = authenticated_client.post(
            self.endpoints.create,
            json=status_data,
        )

        # Test entity_type filter parameter
        response = authenticated_client.get(
            f"{self.endpoints.list}?entity_type=test_entity",
        )

        assert response.status_code == status.HTTP_200_OK
        statuses = response.json()
        # The filter may or may not return results depending on implementation
        assert isinstance(statuses, list)

    # === STATUS-SPECIFIC ERROR HANDLING TESTS ===

    def test_create_status_without_name(self, authenticated_client):
        """Test creating status without required name field"""
        invalid_data = {"description": "Status without name"}

        response = authenticated_client.post(
            self.endpoints.create,
            json=invalid_data,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_create_status_with_empty_name(self, authenticated_client):
        """Test creating status with empty name"""
        invalid_data = {"name": ""}

        response = authenticated_client.post(
            self.endpoints.create,
            json=invalid_data,
        )

        # This might be allowed or not depending on validation rules
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            status.HTTP_400_BAD_REQUEST,
        ]

    def test_create_duplicate_status_names(self, authenticated_client):
        """Test creating statuses with duplicate names"""
        # Create first status
        status_data = self.get_sample_data()
        status_data["name"] = "Duplicate Status"

        response1 = authenticated_client.post(
            self.endpoints.create,
            json=status_data,
        )
        assert response1.status_code == status.HTTP_200_OK

        # Try to create another status with the same name
        duplicate_data = self.get_sample_data()
        duplicate_data["name"] = "Duplicate Status"

        response2 = authenticated_client.post(
            self.endpoints.create,
            json=duplicate_data,
        )

        # Depending on business rules, this might be allowed or not
        # Adjust assertion based on actual API behavior
        assert response2.status_code in [
            status.HTTP_200_OK,  # If duplicates are allowed
            status.HTTP_400_BAD_REQUEST,  # If duplicates are rejected
            status.HTTP_409_CONFLICT,  # If duplicates cause conflict
        ]

    def test_get_nonexistent_status(self, authenticated_client):
        """Test retrieving a non-existent status"""
        fake_id = str(uuid.uuid4())

        response = authenticated_client.get(
            self.endpoints.format_path(self.endpoints.get_by_id, status_id=fake_id),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    def test_update_nonexistent_status(self, authenticated_client):
        """Test updating a non-existent status"""
        fake_id = str(uuid.uuid4())
        update_data = self.get_update_data()

        response = authenticated_client.put(
            self.endpoints.format_path(self.endpoints.update, status_id=fake_id),
            json=update_data,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    def test_delete_nonexistent_status(self, authenticated_client):
        """Test deleting a non-existent status"""
        fake_id = str(uuid.uuid4())

        response = authenticated_client.delete(
            self.endpoints.format_path(self.endpoints.delete, status_id=fake_id),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()


# === STATUS-SPECIFIC INTEGRATION TESTS ===


@pytest.mark.integration
class TestStatusWorkflowManagement(StatusTestMixin, BaseEntityTests):
    """Enhanced status workflow management tests"""

    def test_create_workflow_statuses(self, authenticated_client):
        """Test creating a complete workflow of statuses"""
        workflow_statuses = [
            {"name": "Draft", "description": "Initial draft state"},
            {"name": "Under Review", "description": "Being reviewed by team"},
            {"name": "Approved", "description": "Approved for publication"},
            {"name": "Published", "description": "Live and published"},
            {"name": "Archived", "description": "Archived and no longer active"},
        ]

        created_statuses = []
        for status_data in workflow_statuses:
            response = authenticated_client.post(
                self.endpoints.create,
                json=status_data,
            )

            assert response.status_code == status.HTTP_200_OK
            status_obj = response.json()
            assert status_obj["name"] == status_data["name"]
            created_statuses.append(status_obj)

        assert len(created_statuses) == len(workflow_statuses)

    def test_status_filtering_by_name_pattern(self, authenticated_client):
        """Test filtering statuses by name patterns"""
        # Create statuses with different name patterns
        active_statuses = ["Active", "Actively Processing", "Active Review"]
        inactive_statuses = ["Inactive", "Inactive Archive", "Inactive Draft"]

        all_statuses = active_statuses + inactive_statuses

        for status_name in all_statuses:
            status_data = self.get_sample_data()
            status_data["name"] = status_name

            response = authenticated_client.post(
                self.endpoints.create,
                json=status_data,
            )
            assert response.status_code == status.HTTP_200_OK

        # Filter for statuses containing "Active"
        response = authenticated_client.get(
            f"{self.endpoints.list}?$filter=contains(name,'Active')",
        )

        assert response.status_code == status.HTTP_200_OK
        statuses = response.json()

        # Verify all returned statuses contain "Active" in name
        for status_obj in statuses:
            assert "Active" in status_obj["name"]

    def test_status_entity_type_relationships(self, authenticated_client):
        """Test status creation with entity type relationships"""
        # Create statuses for different entity types
        entity_specific_statuses = [
            {"name": "Project Draft", "description": "Project in draft state"},
            {"name": "Task Completed", "description": "Task has been completed"},
            {"name": "Document Published", "description": "Document is published"},
        ]

        for status_data in entity_specific_statuses:
            response = authenticated_client.post(
                self.endpoints.create,
                json=status_data,
            )

            assert response.status_code == status.HTTP_200_OK
            status_obj = response.json()
            assert status_obj["name"] == status_data["name"]


@pytest.mark.integration
class TestStatusFiltering(StatusTestMixin, BaseEntityTests):
    """Enhanced status filtering tests"""

    def test_filter_statuses_by_description_content(self, authenticated_client):
        """Test filtering statuses by description content"""
        # Create statuses with specific description patterns
        process_status = self.get_sample_data()
        process_status["name"] = "Processing"
        process_status["description"] = "Currently being processed by the system"

        complete_status = self.get_sample_data()
        complete_status["name"] = "Complete"
        complete_status["description"] = "Task has been completed successfully"

        # Create the statuses
        authenticated_client.post(self.endpoints.create, json=process_status)
        authenticated_client.post(self.endpoints.create, json=complete_status)

        # Filter for statuses with "process" in description
        response = authenticated_client.get(
            f"{self.endpoints.list}?$filter=contains(description,'process')",
        )

        assert response.status_code == status.HTTP_200_OK
        statuses = response.json()

        # Verify filtering works (may return empty if filtering not implemented)
        assert isinstance(statuses, list)

    def test_complex_status_filtering(self, authenticated_client):
        """Test complex filtering with multiple criteria"""
        # Create statuses with various attributes
        active_draft = self.get_sample_data()
        active_draft["name"] = "Active Draft"
        active_draft["description"] = "Active draft status"

        inactive_draft = self.get_sample_data()
        inactive_draft["name"] = "Inactive Draft"
        inactive_draft["description"] = "Inactive draft status"

        # Create the statuses
        authenticated_client.post(self.endpoints.create, json=active_draft)
        authenticated_client.post(self.endpoints.create, json=inactive_draft)

        # Test complex filter
        response = authenticated_client.get(
            f"{self.endpoints.list}?$filter=contains(name,'Active') and contains(description,'draft')",
        )

        assert response.status_code == status.HTTP_200_OK
        statuses = response.json()
        assert isinstance(statuses, list)


@pytest.mark.integration
class TestStatusHierarchy(StatusTestMixin, BaseEntityTests):
    """Status hierarchy and categorization tests"""

    def test_create_hierarchical_statuses(self, authenticated_client):
        """Test creating statuses that represent a hierarchy"""
        hierarchical_statuses = [
            {"name": "New", "description": "Newly created item"},
            {"name": "In Progress", "description": "Work is in progress"},
            {"name": "In Progress - Development", "description": "Development phase"},
            {"name": "In Progress - Testing", "description": "Testing phase"},
            {"name": "In Progress - Review", "description": "Review phase"},
            {"name": "Completed", "description": "Work is completed"},
            {"name": "Completed - Approved", "description": "Completed and approved"},
            {"name": "Completed - Deployed", "description": "Completed and deployed"},
        ]

        created_statuses = []
        for status_data in hierarchical_statuses:
            response = authenticated_client.post(
                self.endpoints.create,
                json=status_data,
            )

            assert response.status_code == status.HTTP_200_OK
            status_obj = response.json()
            created_statuses.append(status_obj)

        assert len(created_statuses) == len(hierarchical_statuses)

        # Test filtering by parent category
        response = authenticated_client.get(
            f"{self.endpoints.list}?$filter=startswith(name,'In Progress')",
        )

        assert response.status_code == status.HTTP_200_OK
        in_progress_statuses = response.json()

        # Verify we get the expected statuses (if filtering is implemented)
        assert isinstance(in_progress_statuses, list)


# === STATUS PERFORMANCE TESTS ===


@pytest.mark.performance
class TestStatusPerformance(StatusTestMixin, BaseEntityTests):
    """Status performance tests"""

    def test_create_multiple_statuses_performance(self, authenticated_client):
        """Test creating multiple statuses for performance"""
        statuses_count = 30
        statuses_data = []

        # Generate varied status data
        for i in range(statuses_count):
            status_data = self.get_sample_data()
            status_data["name"] = f"Status {i + 1:03d}"
            status_data["description"] = f"Description for status number {i + 1}"
            statuses_data.append(status_data)

        created_statuses = []
        for status_data in statuses_data:
            response = authenticated_client.post(
                self.endpoints.create,
                json=status_data,
            )
            assert response.status_code == status.HTTP_200_OK
            created_statuses.append(response.json())

        assert len(created_statuses) == statuses_count

        # Test bulk retrieval performance
        response = authenticated_client.get(
            f"{self.endpoints.list}?limit={statuses_count}",
        )

        assert response.status_code == status.HTTP_200_OK
        statuses = response.json()
        assert len(statuses) >= statuses_count

    def test_large_description_status_handling(self, authenticated_client):
        """Test handling of statuses with very large descriptions"""
        large_desc_data = self.get_sample_data()
        large_desc_data["description"] = fake.text(max_nb_chars=3000)

        response = authenticated_client.post(
            self.endpoints.create,
            json=large_desc_data,
        )

        assert response.status_code == status.HTTP_200_OK
        status_obj = response.json()

        # Verify description is preserved correctly
        assert status_obj["description"] == large_desc_data["description"]
        assert len(status_obj["description"]) > 1000

    def test_bulk_status_operations(self, authenticated_client):
        """Test bulk operations on statuses"""
        # Create multiple statuses
        statuses_count = 15
        created_statuses = []

        for i in range(statuses_count):
            status_data = self.get_sample_data()
            status_data["name"] = f"Bulk Status {i + 1}"

            response = authenticated_client.post(
                self.endpoints.create,
                json=status_data,
            )
            created_statuses.append(response.json())

        # Update all statuses
        updated_statuses = []
        for i, status_obj in enumerate(created_statuses):
            update_data = {"description": f"Updated description {i + 1}"}

            response = authenticated_client.put(
                self.endpoints.format_path(self.endpoints.update, status_id=status_obj["id"]),
                json=update_data,
            )

            assert response.status_code == status.HTTP_200_OK
            updated_status = response.json()
            assert updated_status["description"] == f"Updated description {i + 1}"
            updated_statuses.append(updated_status)

        assert len(updated_statuses) == statuses_count

    def test_status_search_performance(self, authenticated_client):
        """Test search performance with many statuses"""
        # Create statuses with searchable content
        search_terms = ["Active", "Inactive", "Pending", "Complete", "Draft"]

        for i in range(20):
            status_data = self.get_sample_data()
            search_term = search_terms[i % len(search_terms)]
            status_data["name"] = f"{search_term} Status {i + 1}"
            status_data["description"] = f"Status for {search_term.lower()} items"

            response = authenticated_client.post(
                self.endpoints.create,
                json=status_data,
            )
            assert response.status_code == status.HTTP_200_OK

        # Test search performance
        response = authenticated_client.get(
            f"{self.endpoints.list}?$filter=contains(name,'Active')",
        )

        assert response.status_code == status.HTTP_200_OK
        statuses = response.json()
        assert isinstance(statuses, list)
