"""
🧪 Dimension Routes Testing Suite

Comprehensive test suite for all dimension entity routes using the DRY approach
with base test classes. This ensures uniformity across all backend route implementations.

Run with: python -m pytest tests/backend/routes/test_dimension.py -v
"""

import uuid
from typing import Dict, Any

import pytest
from faker import Faker
from fastapi import status
from fastapi.testclient import TestClient

from .endpoints import APIEndpoints
from .base import BaseEntityRouteTests, BaseEntityTests
from .faker_utils import TestDataGenerator, generate_dimension_data

# Initialize Faker
fake = Faker()


class DimensionTestMixin:
    """Mixin providing dimension-specific test data and configuration"""

    # Entity configuration
    entity_name = "dimension"
    entity_plural = "dimensions"
    endpoints = APIEndpoints.DIMENSIONS

    def get_sample_data(self) -> Dict[str, Any]:
        """Return sample dimension data for testing using faker utilities"""
        data = generate_dimension_data()

        # Remove None foreign key values that cause validation errors
        # The API will auto-populate organization_id and user_id from the authenticated user
        for key in ["status_id", "entity_type_id"]:
            if key in data and data[key] is None:
                del data[key]  # Remove rather than sending None

        return data

    def get_minimal_data(self) -> Dict[str, Any]:
        """Return minimal dimension data for creation using faker utilities"""
        return TestDataGenerator.generate_dimension_minimal()

    def get_update_data(self) -> Dict[str, Any]:
        """Return dimension update data using faker utilities"""
        return TestDataGenerator.generate_dimension_update_data()


# Standard entity tests - gets ALL tests from base classes
class TestDimensionStandardRoutes(DimensionTestMixin, BaseEntityRouteTests):
    """Complete standard dimension route tests using base classes"""
    pass


# Dimension-specific edge cases (if any)
@pytest.mark.unit
class TestDimensionSpecificEdgeCases(DimensionTestMixin, BaseEntityTests):
    """Dimension-specific edge cases beyond the standard ones"""

    def test_create_dimension_with_very_long_name(self, authenticated_client: TestClient):
        """Test creating dimension with very long name"""
        dimension_data = {
            "name": fake.text(max_nb_chars=500),  # Very long name
            "description": fake.text(max_nb_chars=100)
        }

        response = authenticated_client.post(self.endpoints.create, json=dimension_data)

        # Should either succeed or return validation error
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            status.HTTP_400_BAD_REQUEST
        ]

    def test_create_dimension_with_special_characters(self, authenticated_client: TestClient):
        """Test creating dimension with special characters"""
        dimension_data = {
            "name": f"Dimension with émoji 🧪 & spëcial chars! {fake.random_element(elements=['@', '#', '$', '%'])}",
            "description": fake.text(max_nb_chars=100)
        }

        response = authenticated_client.post(self.endpoints.create, json=dimension_data)

        # Should handle special characters gracefully
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]

        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            assert data["name"] == dimension_data["name"]

    def test_create_dimension_with_duplicate_name(self, authenticated_client: TestClient):
        """Test creating dimension with duplicate name (if name uniqueness is enforced)"""
        # Create first dimension
        dimension_data = {
            "name": "Test Duplicate Dimension",
            "description": "First dimension"
        }
        first_response = authenticated_client.post(self.endpoints.create, json=dimension_data)
        assert first_response.status_code == status.HTTP_200_OK

        # Try to create second dimension with same name
        duplicate_data = {
            "name": "Test Duplicate Dimension",
            "description": "Second dimension with same name"
        }
        duplicate_response = authenticated_client.post(self.endpoints.create, json=duplicate_data)

        # Should either allow duplicates or return conflict error
        assert duplicate_response.status_code in [
            status.HTTP_200_OK,  # If duplicates are allowed
            status.HTTP_409_CONFLICT,  # If uniqueness is enforced
            status.HTTP_400_BAD_REQUEST  # General validation error
        ]

    def test_list_dimensions_with_filter(self, authenticated_client: TestClient):
        """Test listing dimensions with OData filter parameter"""
        # Create a dimension
        created_dimension = self.create_entity(authenticated_client)

        # Test filtering by name (OData style filter)
        filter_query = f"name eq '{created_dimension['name']}'"
        response = authenticated_client.get(f"{self.endpoints.list}?$filter={filter_query}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        # The filter may or may not find our dimension depending on implementation

    def test_list_dimensions_with_sorting(self, authenticated_client: TestClient):
        """Test listing dimensions with various sorting options"""
        # Create multiple dimensions
        dimensions = self.create_multiple_entities(authenticated_client, 3)

        # Test sorting by name ascending
        response = authenticated_client.get(f"{self.endpoints.list}?sort_by=name&sort_order=asc")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)

        # Test sorting by created_at descending (default)
        response = authenticated_client.get(f"{self.endpoints.list}?sort_by=created_at&sort_order=desc")
        assert response.status_code == status.HTTP_200_OK

        # Clean up
        for dimension in dimensions:
            authenticated_client.delete(self.endpoints.remove(dimension["id"]))

    def test_update_dimension_partial_fields(self, authenticated_client: TestClient):
        """Test updating dimension with only some fields"""
        # Create dimension
        created_dimension = self.create_entity(authenticated_client)
        dimension_id = created_dimension["id"]

        # Update only description
        partial_update = {
            "description": "Updated description only"
        }

        response = authenticated_client.put(self.endpoints.put(dimension_id), json=partial_update)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["description"] == partial_update["description"]
        assert data["name"] == created_dimension["name"]  # Name should remain unchanged

    def test_dimension_with_null_description(self, authenticated_client: TestClient):
        """Test dimension creation and update with explicit null description"""
        # Create with null description
        dimension_data = {
            "name": fake.catch_phrase() + " Dimension",
            "description": None
        }

        response = authenticated_client.post(self.endpoints.create, json=dimension_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["description"] is None

        # Update to set description
        update_data = {
            "description": "Now with description"
        }

        update_response = authenticated_client.put(self.endpoints.put(data["id"]), json=update_data)
        assert update_response.status_code == status.HTTP_200_OK
        updated_data = update_response.json()
        assert updated_data["description"] == "Now with description"


@pytest.mark.integration
class TestDimensionRelationships(DimensionTestMixin, BaseEntityTests):
    """Test dimension relationships with other entities"""

    def test_dimension_relationships_preparation(self, authenticated_client: TestClient):
        """Test that dimension can be created for use in relationships"""
        # This test prepares dimensions for use by demographics
        dimension_data = {
            "name": "Age Group Dimension",
            "description": "Dimension for age-based demographics"
        }

        response = authenticated_client.post(self.endpoints.create, json=dimension_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == dimension_data["name"]
        assert "id" in data

        # Verify dimension can be retrieved for relationship usage
        get_response = authenticated_client.get(self.endpoints.get(data["id"]))
        assert get_response.status_code == status.HTTP_200_OK
        assert get_response.json()["id"] == data["id"]


@pytest.mark.slow
@pytest.mark.integration
class TestDimensionPerformance(DimensionTestMixin, BaseEntityTests):
    """Performance tests for dimension operations"""

    def test_bulk_dimension_creation_performance(self, authenticated_client: TestClient):
        """🐌 Test creating multiple dimensions for performance"""
        import time

        start_time = time.time()

        # Create 15 dimensions
        created_dimensions = []
        for i in range(15):
            dimension_data = {
                "name": f"Performance Test Dimension {i}",
                "description": f"Performance test dimension number {i}"
            }
            response = authenticated_client.post(self.endpoints.create, json=dimension_data)
            assert response.status_code == status.HTTP_200_OK
            created_dimensions.append(response.json())

        duration = time.time() - start_time

        # Should complete within reasonable time (15 seconds for 15 creates)
        assert duration < 15.0
        assert len(created_dimensions) == 15

        # Clean up - delete created dimensions
        for dimension in created_dimensions:
            authenticated_client.delete(self.endpoints.remove(dimension["id"]))

    def test_dimension_list_pagination_performance(self, authenticated_client: TestClient):
        """🐌 Test dimension list pagination with larger datasets"""
        import time

        # Create some dimensions first
        created_dimensions = self.create_multiple_entities(authenticated_client, 5)

        start_time = time.time()

        # Test various pagination scenarios
        test_scenarios = [
            {"skip": 0, "limit": 50},
            {"skip": 0, "limit": 100},
            {"skip": 10, "limit": 20},
        ]

        for scenario in test_scenarios:
            response = authenticated_client.get(
                f"{self.endpoints.list}?skip={scenario['skip']}&limit={scenario['limit']}"
            )
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert isinstance(data, list)
            assert len(data) <= scenario['limit']

        duration = time.time() - start_time

        # Should complete within reasonable time (5 seconds for pagination tests)
        assert duration < 5.0

        # Clean up
        for dimension in created_dimensions:
            authenticated_client.delete(self.endpoints.remove(dimension["id"]))


class TestDimensionHealthChecks(DimensionTestMixin, BaseEntityTests):
    """Health checks for dimension endpoints"""

    def test_dimension_endpoints_accessibility(self, authenticated_client: TestClient):
        """✅ Test that dimension endpoints are accessible"""
        # Test list endpoint
        response = authenticated_client.get(self.endpoints.list)
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert isinstance(data, list)

    def test_dimension_crud_cycle_health(self, authenticated_client: TestClient):
        """✅ Test complete dimension CRUD cycle"""
        # Create
        dimension_data = self.get_sample_data()
        create_response = authenticated_client.post(self.endpoints.create, json=dimension_data)
        assert create_response.status_code == status.HTTP_200_OK
        created = create_response.json()

        # Read
        read_response = authenticated_client.get(self.endpoints.get(created["id"]))
        assert read_response.status_code == status.HTTP_200_OK

        # Update
        update_data = {"name": "Updated Health Check Dimension"}
        update_response = authenticated_client.put(self.endpoints.put(created["id"]), json=update_data)
        assert update_response.status_code == status.HTTP_200_OK

        # Delete
        delete_response = authenticated_client.delete(self.endpoints.remove(created["id"]))
        assert delete_response.status_code == status.HTTP_200_OK

        # Verify deletion (soft delete returns 410 GONE)
        verify_response = authenticated_client.get(self.endpoints.get(created["id"]))
        assert verify_response.status_code == status.HTTP_410_GONE
