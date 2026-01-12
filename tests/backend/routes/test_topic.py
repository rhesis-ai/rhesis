"""
🧪 Topic Routes Testing Suite (Enhanced Factory-Based)

Comprehensive test suite for topic entity routes using the enhanced factory system
with automatic cleanup, consistent data generation, and optimized performance.

Key Features:
- 🏭 Factory-based entity creation with automatic cleanup
- 📊 Consistent data generation using data factories
- 🎯 Clear fixture organization and naming
- 🔄 Maintains DRY base class benefits
- ⚡ Optimized performance with proper scoping
- 🌳 Topic-specific hierarchical functionality testing
- 🏗️ Self-referential parent-child relationships
- 🔍 Advanced filtering and topic categorization

Run with: python -m pytest tests/backend/routes/test_topic.py -v
"""

import uuid
from typing import Any, Dict

import pytest
from faker import Faker
from fastapi import status

from .base import BaseEntityRouteTests, BaseEntityTests
from .endpoints import APIEndpoints
from .fixtures.data_factories import TopicDataFactory

# Initialize Faker
fake = Faker()


class TopicTestMixin:
    """Enhanced topic test mixin using factory system"""

    # Entity configuration
    entity_name = "topic"
    entity_plural = "topics"
    endpoints = APIEndpoints.TOPICS

    # Field mappings for topics
    name_field = "name"
    description_field = "description"

    # Factory-based data methods
    def get_sample_data(self) -> Dict[str, Any]:
        """Return sample topic data using factory"""
        return TopicDataFactory.sample_data()

    def get_minimal_data(self) -> Dict[str, Any]:
        """Return minimal topic data using factory"""
        return TopicDataFactory.minimal_data()

    def get_update_data(self) -> Dict[str, Any]:
        """Return topic update data using factory"""
        return TopicDataFactory.update_data()

    def get_invalid_data(self) -> Dict[str, Any]:
        """Return invalid topic data using factory"""
        return TopicDataFactory.invalid_data()

    def get_null_description_data(self) -> Dict[str, Any]:
        """Return topic data with null description"""
        return TopicDataFactory.edge_case_data("null_description")


class TestTopicRoutes(TopicTestMixin, BaseEntityRouteTests):
    """
    🧪 Complete topic route test suite

    This class inherits from BaseEntityRouteTests to get comprehensive coverage:
    - ✅ Full CRUD operation testing
    - 👤 Automatic user relationship field testing
    - 🔗 List operations and filtering
    - 🛡️ Authentication validation
    - 🏃‍♂️ Edge case handling
    - 🐌 Performance validation
    - ✅ Health checks

    Plus topic-specific functionality tests.
    """

    # === TOPIC-SPECIFIC CRUD TESTS ===

    def test_create_topic_with_required_fields(self, authenticated_client):
        """Test topic creation with only required fields"""
        minimal_data = self.get_minimal_data()

        response = authenticated_client.post(self.endpoints.create, json=minimal_data)

        assert response.status_code == status.HTTP_200_OK
        created_topic = response.json()

        assert created_topic["name"] == minimal_data["name"]
        # Optional fields should be None/null when not provided
        assert created_topic.get("description") is None
        assert created_topic.get("parent_id") is None

    def test_create_topic_with_optional_fields(self, authenticated_client):
        """Test topic creation with optional fields"""
        topic_data = self.get_sample_data()

        response = authenticated_client.post(
            self.endpoints.create,
            json=topic_data,
        )

        assert response.status_code == status.HTTP_200_OK
        created_topic = response.json()

        assert created_topic["name"] == topic_data["name"]
        if topic_data.get("description"):
            assert created_topic["description"] == topic_data["description"]

    def test_create_hierarchical_topic(self, authenticated_client):
        """Test topic creation with hierarchical categorization"""
        hierarchical_topic_data = TopicDataFactory.edge_case_data("hierarchical_topics")

        response = authenticated_client.post(
            self.endpoints.create,
            json=hierarchical_topic_data,
        )

        assert response.status_code == status.HTTP_200_OK
        created_topic = response.json()

        assert created_topic["name"] == hierarchical_topic_data["name"]
        assert ":" in created_topic["name"]  # Should contain hierarchical separator
        assert created_topic["description"] == hierarchical_topic_data["description"]

    def test_create_specialized_domain_topic(self, authenticated_client):
        """Test topic creation with specialized domain focus"""
        domain_topic_data = TopicDataFactory.edge_case_data("specialized_domains")

        response = authenticated_client.post(
            self.endpoints.create,
            json=domain_topic_data,
        )

        assert response.status_code == status.HTTP_200_OK
        created_topic = response.json()

        assert created_topic["name"] == domain_topic_data["name"]
        assert " - " in created_topic["name"]  # Should contain domain separator
        assert "domain" in created_topic["description"].lower()
        assert created_topic["description"] == domain_topic_data["description"]

    def test_create_topic_with_empty_description(self, authenticated_client):
        """Test topic creation with empty string description"""
        empty_desc_data = TopicDataFactory.edge_case_data("empty_description")

        response = authenticated_client.post(
            self.endpoints.create,
            json=empty_desc_data,
        )

        assert response.status_code == status.HTTP_200_OK
        created_topic = response.json()

        assert created_topic["name"] == empty_desc_data["name"]
        assert created_topic["description"] == ""  # Should preserve empty string

    def test_create_topic_with_long_name(self, authenticated_client):
        """Test topic creation with very long name"""
        long_name_data = TopicDataFactory.edge_case_data("long_name")

        response = authenticated_client.post(
            self.endpoints.create,
            json=long_name_data,
        )

        assert response.status_code == status.HTTP_200_OK
        created_topic = response.json()

        assert created_topic["name"] == long_name_data["name"]
        assert len(created_topic["name"]) > 100  # Verify it's actually long
        assert created_topic["description"] == long_name_data["description"]


# === TOPIC HIERARCHICAL RELATIONSHIPS TESTS ===


@pytest.mark.integration
class TestTopicHierarchy(TopicTestMixin, BaseEntityTests):
    """Enhanced topic hierarchical relationship tests"""

    def test_create_child_topic(self, authenticated_client):
        """Test creating a child topic with parent relationship"""
        # Create parent topic first
        parent_data = self.get_sample_data()
        parent_response = authenticated_client.post(
            self.endpoints.create,
            json=parent_data,
        )
        assert parent_response.status_code == status.HTTP_200_OK
        parent_topic = parent_response.json()

        # Create child topic
        child_data = {
            "name": f"Child of {parent_data['name']}",
            "description": fake.text(max_nb_chars=120),
            "parent_id": parent_topic["id"],
        }

        child_response = authenticated_client.post(
            self.endpoints.create,
            json=child_data,
        )

        assert child_response.status_code == status.HTTP_200_OK
        child_topic = child_response.json()

        assert child_topic["name"] == child_data["name"]
        assert child_topic["parent_id"] == parent_topic["id"]

    def test_create_topic_with_invalid_parent(self, authenticated_client):
        """Test creating topic with non-existent parent"""
        fake_parent_id = str(uuid.uuid4())

        child_data = {"name": "Orphaned Topic", "parent_id": fake_parent_id}

        response = authenticated_client.post(
            self.endpoints.create,
            json=child_data,
        )

        # API should handle foreign key constraint violations gracefully
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            status.HTTP_500_INTERNAL_SERVER_ERROR,  # Database constraint violation
        ]

        if response.status_code == status.HTTP_400_BAD_REQUEST:
            assert "invalid parent" in response.json()["detail"].lower()


# === TOPIC PERFORMANCE TESTS ===


@pytest.mark.performance
class TestTopicPerformance(TopicTestMixin, BaseEntityTests):
    """Topic performance tests"""

    def test_create_multiple_topics_performance(self, authenticated_client):
        """Test creating multiple topics for performance"""
        topics_count = 20
        topics_data = TopicDataFactory.batch_data(topics_count, variation=True)

        created_topics = []
        for topic_data in topics_data:
            response = authenticated_client.post(
                self.endpoints.create,
                json=topic_data,
            )
            assert response.status_code == status.HTTP_200_OK
            created_topics.append(response.json())

        assert len(created_topics) == topics_count

        # Test bulk retrieval performance
        response = authenticated_client.get(
            f"{self.endpoints.list}?limit={topics_count}",
        )

        assert response.status_code == status.HTTP_200_OK
        topics = response.json()
        assert len(topics) >= topics_count
