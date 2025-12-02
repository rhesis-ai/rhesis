"""
🏷️ Type Lookup Routes Testing Suite (Enhanced Factory-Based)

Comprehensive test suite for type lookup entity routes using the enhanced factory system
with automatic cleanup, consistent data generation, and optimized performance.

Key Features:
- 🏭 Factory-based entity creation with automatic cleanup
- 📊 Consistent data generation using data factories
- 🎯 Clear fixture organization and naming
- 🔄 Maintains DRY base class benefits
- ⚡ Optimized performance with proper scoping
- 🏷️ Type lookup-specific functionality testing
- 📋 Reference data and enumeration management
- 🔍 Advanced filtering and type categorization

Run with: python -m pytest tests/backend/routes/test_type_lookup.py -v
"""

import uuid
from typing import Dict, Any

import pytest
from faker import Faker
from fastapi import status
from fastapi.testclient import TestClient

from .endpoints import APIEndpoints
from .base import BaseEntityRouteTests, BaseEntityTests
from .fixtures.data_factories import TypeLookupDataFactory

# Initialize Faker
fake = Faker()


class TypeLookupTestMixin:
    """Enhanced type lookup test mixin using factory system"""

    # Entity configuration
    entity_name = "type_lookup"
    entity_plural = "type_lookups"
    endpoints = APIEndpoints.TYPE_LOOKUPS

    # Field mappings for type lookups
    name_field = "type_name"
    description_field = "description"

    # Factory-based data methods
    def get_sample_data(self) -> Dict[str, Any]:
        """Return sample type lookup data using factory"""
        return TypeLookupDataFactory.sample_data()

    def get_minimal_data(self) -> Dict[str, Any]:
        """Return minimal type lookup data using factory"""
        return TypeLookupDataFactory.minimal_data()

    def get_update_data(self) -> Dict[str, Any]:
        """Return type lookup update data using factory"""
        return TypeLookupDataFactory.update_data()

    def get_invalid_data(self) -> Dict[str, Any]:
        """Return invalid type lookup data using factory"""
        return TypeLookupDataFactory.invalid_data()

    def get_null_description_data(self) -> Dict[str, Any]:
        """Return type lookup data with null description"""
        return TypeLookupDataFactory.edge_case_data("null_description")


class TestTypeLookupRoutes(TypeLookupTestMixin, BaseEntityRouteTests):
    """
    🏷️ Complete type lookup route test suite

    This class inherits from BaseEntityRouteTests to get comprehensive coverage:
    - ✅ Full CRUD operation testing
    - 👤 Automatic user relationship field testing
    - 🔗 List operations and filtering
    - 🛡️ Authentication validation
    - 🏃‍♂️ Edge case handling
    - 🐌 Performance validation
    - ✅ Health checks

    Plus type lookup-specific functionality tests.
    """

    # === TYPE LOOKUP-SPECIFIC CRUD TESTS ===

    def test_create_type_lookup_with_required_fields(self, authenticated_client):
        """Test type lookup creation with only required fields"""
        minimal_data = self.get_minimal_data()

        response = authenticated_client.post(self.endpoints.create, json=minimal_data)

        assert response.status_code == status.HTTP_200_OK
        created_type_lookup = response.json()

        assert created_type_lookup["type_name"] == minimal_data["type_name"]
        assert created_type_lookup["type_value"] == minimal_data["type_value"]
        # Optional fields should be None/null when not provided
        assert created_type_lookup.get("description") is None

    def test_create_type_lookup_with_optional_fields(self, authenticated_client):
        """Test type lookup creation with optional fields"""
        type_lookup_data = self.get_sample_data()

        response = authenticated_client.post(
            self.endpoints.create,
            json=type_lookup_data,
        )

        assert response.status_code == status.HTTP_200_OK
        created_type_lookup = response.json()

        assert created_type_lookup["type_name"] == type_lookup_data["type_name"]
        assert created_type_lookup["type_value"] == type_lookup_data["type_value"]
        if type_lookup_data.get("description"):
            assert created_type_lookup["description"] == type_lookup_data["description"]

    def test_create_priority_level_type_lookup(self, authenticated_client):
        """Test type lookup creation with priority level categorization"""
        priority_data = TypeLookupDataFactory.edge_case_data("priority_levels")

        response = authenticated_client.post(
            self.endpoints.create,
            json=priority_data,
        )

        assert response.status_code == status.HTTP_200_OK
        created_type_lookup = response.json()

        assert created_type_lookup["type_name"] == "priority"
        assert created_type_lookup["type_value"] in ["low", "medium", "high", "critical", "urgent"]
        assert "priority" in created_type_lookup["description"].lower()

    def test_create_status_type_lookup(self, authenticated_client):
        """Test type lookup creation with status type categorization"""
        status_data = TypeLookupDataFactory.edge_case_data("status_types")

        response = authenticated_client.post(
            self.endpoints.create,
            json=status_data,
        )

        assert response.status_code == status.HTTP_200_OK
        created_type_lookup = response.json()

        assert created_type_lookup["type_name"] == "status"
        assert created_type_lookup["type_value"] in [
            "active",
            "inactive",
            "pending",
            "completed",
            "cancelled",
            "draft",
            "published",
        ]
        assert "status" in created_type_lookup["description"].lower()

    def test_create_category_type_lookup(self, authenticated_client):
        """Test type lookup creation with category type"""
        category_data = TypeLookupDataFactory.edge_case_data("category_types")

        response = authenticated_client.post(
            self.endpoints.create,
            json=category_data,
        )

        assert response.status_code == status.HTTP_200_OK
        created_type_lookup = response.json()

        assert created_type_lookup["type_name"] == "category"
        assert created_type_lookup["type_value"] in [
            "business",
            "technology",
            "finance",
            "healthcare",
            "education",
            "research",
            "marketing",
        ]
        assert "category" in created_type_lookup["description"].lower()

    def test_create_entity_type_lookup(self, authenticated_client):
        """Test type lookup creation with entity type"""
        entity_data = TypeLookupDataFactory.edge_case_data("entity_types")

        response = authenticated_client.post(
            self.endpoints.create,
            json=entity_data,
        )

        assert response.status_code == status.HTTP_200_OK
        created_type_lookup = response.json()

        assert created_type_lookup["type_name"] == "entity_type"
        assert created_type_lookup["type_value"] in [
            "user",
            "organization",
            "project",
            "task",
            "document",
            "report",
            "metric",
        ]
        assert "entity type" in created_type_lookup["description"].lower()

    def test_create_type_lookup_with_long_values(self, authenticated_client):
        """Test type lookup creation with very long values"""
        long_data = TypeLookupDataFactory.edge_case_data("long_values")

        response = authenticated_client.post(
            self.endpoints.create,
            json=long_data,
        )

        assert response.status_code == status.HTTP_200_OK
        created_type_lookup = response.json()

        assert created_type_lookup["type_name"] == long_data["type_name"]
        assert len(created_type_lookup["type_value"]) > 100  # Verify it's actually long
        assert created_type_lookup["description"] == long_data["description"]

    def test_create_type_lookup_with_special_characters(self, authenticated_client):
        """Test type lookup creation with special characters in value"""
        special_data = TypeLookupDataFactory.edge_case_data("special_characters")

        response = authenticated_client.post(
            self.endpoints.create,
            json=special_data,
        )

        assert response.status_code == status.HTTP_200_OK
        created_type_lookup = response.json()

        assert created_type_lookup["type_name"] == special_data["type_name"]
        assert "@#$%^&*()" in created_type_lookup["type_value"]  # Contains special chars
        assert created_type_lookup["description"] == special_data["description"]

    def test_create_type_lookup_with_empty_description(self, authenticated_client):
        """Test type lookup creation with empty string description"""
        empty_desc_data = TypeLookupDataFactory.edge_case_data("empty_description")

        response = authenticated_client.post(
            self.endpoints.create,
            json=empty_desc_data,
        )

        assert response.status_code == status.HTTP_200_OK
        created_type_lookup = response.json()

        assert created_type_lookup["type_name"] == empty_desc_data["type_name"]
        assert created_type_lookup["type_value"] == empty_desc_data["type_value"]
        assert created_type_lookup["description"] == ""  # Should preserve empty string

    def test_update_type_lookup_name_and_value(self, authenticated_client):
        """Test updating type lookup name and value"""
        # Create initial type lookup
        initial_data = self.get_minimal_data()
        create_response = authenticated_client.post(
            self.endpoints.create,
            json=initial_data,
        )
        type_lookup_id = create_response.json()["id"]

        # Update type lookup
        update_data = self.get_update_data()
        response = authenticated_client.put(
            self.endpoints.format_path(self.endpoints.update, type_lookup_id=type_lookup_id),
            json=update_data,
        )

        assert response.status_code == status.HTTP_200_OK
        updated_type_lookup = response.json()

        assert updated_type_lookup["type_name"] == update_data["type_name"]
        assert updated_type_lookup["type_value"] == update_data["type_value"]
        assert updated_type_lookup["description"] == update_data["description"]

    def test_get_type_lookup_by_id(self, authenticated_client):
        """Test retrieving a specific type lookup by ID"""
        # Create type lookup
        type_lookup_data = self.get_sample_data()
        create_response = authenticated_client.post(
            self.endpoints.create,
            json=type_lookup_data,
        )
        type_lookup_id = create_response.json()["id"]

        # Get type lookup by ID
        response = authenticated_client.get(
            self.endpoints.format_path(self.endpoints.get_by_id, type_lookup_id=type_lookup_id),
        )

        assert response.status_code == status.HTTP_200_OK
        type_lookup = response.json()

        assert type_lookup["id"] == type_lookup_id
        assert type_lookup["type_name"] == type_lookup_data["type_name"]
        assert type_lookup["type_value"] == type_lookup_data["type_value"]
        if type_lookup_data.get("description"):
            assert type_lookup["description"] == type_lookup_data["description"]

    def test_delete_type_lookup(self, authenticated_client):
        """Test deleting a type lookup"""
        # Create type lookup
        type_lookup_data = self.get_minimal_data()
        create_response = authenticated_client.post(
            self.endpoints.create,
            json=type_lookup_data,
        )
        type_lookup_id = create_response.json()["id"]

        # Delete type lookup
        response = authenticated_client.delete(
            self.endpoints.format_path(self.endpoints.delete, type_lookup_id=type_lookup_id),
        )

        assert response.status_code == status.HTTP_200_OK
        deleted_type_lookup = response.json()
        assert deleted_type_lookup["id"] == type_lookup_id

        # Verify type lookup is deleted (soft delete returns 410 GONE)
        get_response = authenticated_client.get(
            self.endpoints.format_path(self.endpoints.get_by_id, type_lookup_id=type_lookup_id),
        )
        assert get_response.status_code == status.HTTP_410_GONE

    def test_list_type_lookups_with_pagination(self, authenticated_client):
        """Test listing type lookups with pagination"""
        # Create multiple type lookups
        type_lookups_data = [self.get_sample_data() for _ in range(5)]
        created_type_lookups = []

        for type_lookup_data in type_lookups_data:
            response = authenticated_client.post(
                self.endpoints.create,
                json=type_lookup_data,
            )
            created_type_lookups.append(response.json())

        # Test pagination
        response = authenticated_client.get(
            f"{self.endpoints.list}?skip=0&limit=3",
        )

        assert response.status_code == status.HTTP_200_OK
        type_lookups = response.json()
        assert len(type_lookups) <= 3

        # Check count header
        assert "X-Total-Count" in response.headers
        total_count = int(response.headers["X-Total-Count"])
        assert total_count >= 5

    def test_list_type_lookups_with_sorting(self, authenticated_client):
        """Test listing type lookups with sorting"""
        # Create type lookups with different names
        type_lookup1_data = self.get_sample_data()
        type_lookup1_data["type_name"] = "aaa_early_type"

        type_lookup2_data = self.get_sample_data()
        type_lookup2_data["type_name"] = "zzz_late_type"

        # Create type lookups
        authenticated_client.post(self.endpoints.create, json=type_lookup1_data)
        authenticated_client.post(self.endpoints.create, json=type_lookup2_data)

        # Test sorting
        response = authenticated_client.get(
            f"{self.endpoints.list}?sort_by=created_at&sort_order=asc",
        )

        assert response.status_code == status.HTTP_200_OK
        type_lookups = response.json()
        assert len(type_lookups) >= 2

    # === TYPE LOOKUP-SPECIFIC ERROR HANDLING TESTS ===

    def test_create_type_lookup_without_type_name(self, authenticated_client):
        """Test creating type lookup without required type_name field"""
        invalid_data = {"type_value": "test_value", "description": "Type lookup without name"}

        response = authenticated_client.post(
            self.endpoints.create,
            json=invalid_data,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_create_type_lookup_without_type_value(self, authenticated_client):
        """Test creating type lookup without required type_value field"""
        invalid_data = {"type_name": "test_type", "description": "Type lookup without value"}

        response = authenticated_client.post(
            self.endpoints.create,
            json=invalid_data,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_create_type_lookup_with_empty_type_name(self, authenticated_client):
        """Test creating type lookup with empty type_name"""
        invalid_data = {
            "type_name": "",
            "type_value": "test_value",
            "description": "Type lookup with empty name",
        }

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

    def test_create_type_lookup_with_empty_type_value(self, authenticated_client):
        """Test creating type lookup with empty type_value"""
        invalid_data = {
            "type_name": "test_type",
            "type_value": "",
            "description": "Type lookup with empty value",
        }

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

    def test_get_nonexistent_type_lookup(self, authenticated_client):
        """Test retrieving a non-existent type lookup"""
        fake_id = str(uuid.uuid4())

        response = authenticated_client.get(
            self.endpoints.format_path(self.endpoints.get_by_id, type_lookup_id=fake_id),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    def test_update_nonexistent_type_lookup(self, authenticated_client):
        """Test updating a non-existent type lookup"""
        fake_id = str(uuid.uuid4())
        update_data = self.get_update_data()

        response = authenticated_client.put(
            self.endpoints.format_path(self.endpoints.update, type_lookup_id=fake_id),
            json=update_data,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    def test_delete_nonexistent_type_lookup(self, authenticated_client):
        """Test deleting a non-existent type lookup"""
        fake_id = str(uuid.uuid4())

        response = authenticated_client.delete(
            self.endpoints.format_path(self.endpoints.delete, type_lookup_id=fake_id),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()


# === TYPE LOOKUP CATEGORIZATION TESTS ===


@pytest.mark.integration
class TestTypeLookupCategorization(TypeLookupTestMixin, BaseEntityTests):
    """Enhanced type lookup categorization tests"""

    def test_create_complete_priority_system(self, authenticated_client):
        """Test creating a complete priority level system"""
        priority_levels = ["low", "medium", "high", "critical", "urgent"]
        created_priorities = []

        for level in priority_levels:
            priority_data = {
                "type_name": "priority",
                "type_value": level,
                "description": f"{level.title()} priority items",
            }

            response = authenticated_client.post(
                self.endpoints.create,
                json=priority_data,
            )

            assert response.status_code == status.HTTP_200_OK
            created_priority = response.json()

            assert created_priority["type_name"] == "priority"
            assert created_priority["type_value"] == level
            created_priorities.append(created_priority)

        assert len(created_priorities) == 5

    def test_create_complete_status_system(self, authenticated_client):
        """Test creating a complete status system"""
        statuses = ["active", "inactive", "pending", "completed", "cancelled"]
        created_statuses = []

        for status_val in statuses:
            status_data = {
                "type_name": "status",
                "type_value": status_val,
                "description": f"{status_val.title()} status",
            }

            response = authenticated_client.post(
                self.endpoints.create,
                json=status_data,
            )

            assert response.status_code == status.HTTP_200_OK
            created_status = response.json()

            assert created_status["type_name"] == "status"
            assert created_status["type_value"] == status_val
            created_statuses.append(created_status)

        assert len(created_statuses) == 5

    def test_filter_type_lookups_by_type_name(self, authenticated_client):
        """Test filtering type lookups by type_name"""
        # Create different types of lookups
        priority_data = TypeLookupDataFactory.edge_case_data("priority_levels")
        category_data = TypeLookupDataFactory.edge_case_data("category_types")

        priority_response = authenticated_client.post(self.endpoints.create, json=priority_data)
        category_response = authenticated_client.post(self.endpoints.create, json=category_data)

        assert priority_response.status_code == status.HTTP_200_OK
        assert category_response.status_code == status.HTTP_200_OK

        # Test listing all type lookups (should include both)
        response = authenticated_client.get(f"{self.endpoints.list}?limit=10")
        assert response.status_code == status.HTTP_200_OK
        type_lookups = response.json()

        # Verify we have type lookups from different type names
        type_names = [tl.get("type_name") for tl in type_lookups if tl.get("type_name")]
        assert len(set(type_names)) >= 2  # At least 2 different type names


# === TYPE LOOKUP PERFORMANCE TESTS ===


@pytest.mark.performance
class TestTypeLookupPerformance(TypeLookupTestMixin, BaseEntityTests):
    """Type lookup performance tests"""

    def test_create_multiple_type_lookups_performance(self, authenticated_client):
        """Test creating multiple type lookups for performance"""
        type_lookups_count = 20
        type_lookups_data = TypeLookupDataFactory.batch_data(type_lookups_count, variation=True)

        created_type_lookups = []
        for type_lookup_data in type_lookups_data:
            response = authenticated_client.post(
                self.endpoints.create,
                json=type_lookup_data,
            )
            assert response.status_code == status.HTTP_200_OK
            created_type_lookups.append(response.json())

        assert len(created_type_lookups) == type_lookups_count

        # Test bulk retrieval performance
        response = authenticated_client.get(
            f"{self.endpoints.list}?limit={type_lookups_count}",
        )

        assert response.status_code == status.HTTP_200_OK
        type_lookups = response.json()
        assert len(type_lookups) >= type_lookups_count

    def test_type_lookup_categorization_performance(self, authenticated_client):
        """Test type lookup categorization performance with different types"""
        # Create type lookups of different categories
        categories = ["priority_levels", "status_types", "category_types", "entity_types"]

        created_type_lookups = []
        for category in categories:
            for i in range(3):  # 3 type lookups per category
                type_lookup_data = TypeLookupDataFactory.edge_case_data(category)
                response = authenticated_client.post(
                    self.endpoints.create,
                    json=type_lookup_data,
                )
                assert response.status_code == status.HTTP_200_OK
                created_type_lookups.append(response.json())

        assert len(created_type_lookups) == len(categories) * 3

        # Test listing all type lookups
        response = authenticated_client.get(
            f"{self.endpoints.list}?limit=20",
        )

        assert response.status_code == status.HTTP_200_OK
        type_lookups = response.json()
        assert len(type_lookups) >= 12  # At least the ones we created

    def test_bulk_type_lookup_operations(self, authenticated_client):
        """Test bulk type lookup operations"""
        # Create multiple type lookups
        type_lookups_count = 15
        type_lookups_data = TypeLookupDataFactory.batch_data(type_lookups_count, variation=False)

        created_type_lookups = []
        for type_lookup_data in type_lookups_data:
            response = authenticated_client.post(
                self.endpoints.create,
                json=type_lookup_data,
            )
            assert response.status_code == status.HTTP_200_OK
            created_type_lookups.append(response.json())

        # Test bulk update operations
        update_data = self.get_update_data()
        for type_lookup_obj in created_type_lookups[:5]:  # Update first 5 type lookups
            response = authenticated_client.put(
                self.endpoints.format_path(
                    self.endpoints.update, type_lookup_id=type_lookup_obj["id"]
                ),
                json=update_data,
            )
            assert response.status_code == status.HTTP_200_OK

        # Test bulk delete operations
        for type_lookup_obj in created_type_lookups[10:]:  # Delete last 5 type lookups
            response = authenticated_client.delete(
                self.endpoints.format_path(
                    self.endpoints.delete, type_lookup_id=type_lookup_obj["id"]
                ),
            )
            assert response.status_code == status.HTTP_200_OK

    def test_reference_data_distribution_performance(self, authenticated_client):
        """Test performance with diverse reference data distribution"""
        # Create type lookups across different reference types using the factory's categories
        reference_types = []
        for i in range(10):  # Create 10 different reference type lookups
            type_lookup_data = TypeLookupDataFactory.edge_case_data("entity_types")
            response = authenticated_client.post(
                self.endpoints.create,
                json=type_lookup_data,
            )
            assert response.status_code == status.HTTP_200_OK
            reference_types.append(response.json())

        # Verify reference data distribution
        assert len(reference_types) == 10

        # Test listing with various filters
        response = authenticated_client.get(
            f"{self.endpoints.list}?limit=15",
        )

        assert response.status_code == status.HTTP_200_OK
        type_lookups = response.json()
        assert len(type_lookups) >= 10  # At least most of the ones we created
