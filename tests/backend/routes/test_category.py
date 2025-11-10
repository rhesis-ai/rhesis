"""
🧪 Category Routes Testing Suite (DRY Implementation)

Comprehensive test suite for all category entity routes using the DRY approach
with base test classes. This ensures uniformity across all backend route implementations.

Run with: python -m pytest tests/backend/routes/test_category.py -v
"""

import uuid
from typing import Dict, Any

import pytest
from faker import Faker
from fastapi import status
from fastapi.testclient import TestClient

from .endpoints import APIEndpoints
from .base import BaseEntityRouteTests, BaseEntityTests
from .faker_utils import TestDataGenerator, generate_category_data

# Initialize Faker
fake = Faker()


class CategoryTestMixin:
    """Mixin providing category-specific test data and configuration"""

    # Entity configuration
    entity_name = "category"
    entity_plural = "categories"
    endpoints = APIEndpoints.CATEGORIES

    def get_sample_data(self) -> Dict[str, Any]:
        """Return sample category data for testing using faker utilities"""
        data = generate_category_data()

        # Remove None foreign key values that cause validation errors
        # The API will auto-populate organization_id and user_id from the authenticated user
        for key in ["status_id", "entity_type_id"]:
            if key in data and data[key] is None:
                del data[key]  # Remove rather than sending None

        return data

    def get_minimal_data(self) -> Dict[str, Any]:
        """Return minimal category data for creation using faker utilities"""
        return TestDataGenerator.generate_category_minimal()

    def get_update_data(self) -> Dict[str, Any]:
        """Return category update data using faker utilities"""
        return TestDataGenerator.generate_category_update_data()


# Standard entity tests - gets ALL tests from base classes
class TestCategoryStandardRoutes(CategoryTestMixin, BaseEntityRouteTests):
    """Complete standard category route tests using base classes"""
    pass


# Category-specific edge cases (if any)
@pytest.mark.unit
class TestCategorySpecificEdgeCases(CategoryTestMixin, BaseEntityTests):
    """Category-specific edge cases beyond the standard ones"""

    def test_create_category_with_parent_id(self, authenticated_client: TestClient):
        """Test creating categories with parent relationship"""
        # Create a parent category first
        parent_category = self.create_entity(authenticated_client)

        # Create a child category
        child_data = {
            "name": fake.word().title() + " Child Category",
            "description": fake.text(max_nb_chars=100),
            "parent_id": parent_category["id"]
        }

        response = authenticated_client.post(self.endpoints.create, json=child_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["parent_id"] == parent_category["id"]

    def test_create_category_with_invalid_parent_id(self, authenticated_client: TestClient):
        """Test creating category with non-existent parent"""
        child_data = {
            "name": fake.word().title() + " Orphaned Category",
            "parent_id": str(uuid.uuid4())  # Non-existent parent
        }

        response = authenticated_client.post(self.endpoints.create, json=child_data)

        # API should handle foreign key constraint violations gracefully
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "invalid parent category reference" in response.json()["detail"].lower()

    def test_list_categories_with_entity_type_filter(self, authenticated_client: TestClient):
        """Test listing categories with entity type filter parameter"""
        # Create a category
        created_category = self.create_entity(authenticated_client)

        # Test filtering by entity type (this tests the query parameter handling)
        response = authenticated_client.get(f"{self.endpoints.list}?entity_type=behavior")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        # The filter may or may not find our category depending on implementation
