"""
Requirement Routes Testing Suite (Enhanced Factory-Based)

Comprehensive test suite for requirement entity routes using the enhanced factory system
with automatic cleanup, consistent data generation, and optimized performance.

Key Features:
- Factory-based entity creation with automatic cleanup
- Consistent data generation using data factories
- Clear fixture organization and naming
- Maintains DRY base class benefits
- Optimized performance with proper scoping

Run with: python -m pytest tests/backend/routes/test_requirement.py -v
"""

from typing import Any, Dict

import pytest
from faker import Faker
from fastapi import status

from .base import BaseEntityRouteTests, BaseEntityTests
from .endpoints import APIEndpoints
from .fixtures.data_factories import RequirementDataFactory, MetricDataFactory

# Initialize Faker
fake = Faker()


class RequirementTestMixin:
    """Enhanced requirement test mixin using factory system"""

    # Entity configuration (unchanged)
    entity_name = "requirement"
    entity_plural = "requirements"
    endpoints = APIEndpoints.REQUIREMENTS

    # Factory-based data methods
    def get_sample_data(self, client=None) -> Dict[str, Any]:
        """Return sample requirement data using factory"""
        return RequirementDataFactory.sample_data()

    def get_minimal_data(self, client=None) -> Dict[str, Any]:
        """Return minimal requirement data using factory"""
        return RequirementDataFactory.minimal_data()

    def get_update_data(self) -> Dict[str, Any]:
        """Return requirement update data using factory"""
        return RequirementDataFactory.update_data()

    def get_invalid_data(self) -> Dict[str, Any]:
        """Return invalid requirement data using factory"""
        return RequirementDataFactory.invalid_data()

    def get_edge_case_data(self, case_type: str) -> Dict[str, Any]:
        """Return edge case requirement data using factory"""
        return RequirementDataFactory.edge_case_data(case_type)


# Standard entity tests - gets ALL tests from base classes
class TestRequirementStandardRoutes(RequirementTestMixin, BaseEntityRouteTests):
    """Complete standard requirement route tests using base classes"""

    pass


# === REQUIREMENT-SPECIFIC TESTS (Enhanced with Factories) ===


@pytest.mark.integration
class TestRequirementMetricRelationships(RequirementTestMixin, BaseEntityTests):
    """Enhanced requirement-metric relationship tests using factories"""

    def test_get_requirement_metrics_empty(self, requirement_factory):
        """Test getting metrics for requirement with no metrics (using factory)"""
        # Create requirement using factory (automatic cleanup)
        requirement = requirement_factory.create(self.get_sample_data())
        requirement_id = requirement["id"]

        response = requirement_factory.client.get(self.endpoints.metrics(requirement_id))

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_requirement_with_metrics_relationship(self, requirement_with_metrics):
        """Test requirement-metrics relationship using composite fixture"""
        # Use the pre-created relationship from fixture
        requirement = requirement_with_metrics["requirement"]
        metrics = requirement_with_metrics["metrics"]

        # Verify the relationship was created
        assert requirement["id"] is not None
        assert len(metrics) == 2

    def test_add_metric_to_requirement_factory(self, requirement_factory, metric_factory):
        """Test adding metric to requirement using factories"""
        # Create entities using factories
        requirement = requirement_factory.create(self.get_sample_data())
        metric = metric_factory.create(MetricDataFactory.sample_data())

        # Test the relationship creation
        response = requirement_factory.client.post(
            self.endpoints.add_metric_to_requirement(requirement["id"], metric["id"])
        )

        assert response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]
        # Automatic cleanup happens via fixtures

    def test_bulk_metric_association(self, requirement_factory, metric_factory):
        """Test associating multiple metrics with requirement"""
        # Create one requirement and multiple metrics
        requirement = requirement_factory.create(self.get_sample_data())

        # Create multiple metrics using batch creation
        from .fixtures.data_factories import MetricDataFactory

        metrics = metric_factory.create_batch(
            [
                MetricDataFactory.sample_data(),
                MetricDataFactory.sample_data(),
                MetricDataFactory.sample_data(),
            ]
        )

        # Associate all metrics with the requirement
        for metric in metrics:
            response = requirement_factory.client.post(
                self.endpoints.add_metric_to_requirement(requirement["id"], metric["id"])
            )
            assert response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]

        # Verify all associations
        response = requirement_factory.client.get(self.endpoints.metrics(requirement["id"]))
        assert response.status_code == status.HTTP_200_OK

        returned_metrics = response.json()
        assert len(returned_metrics) == len(metrics)


# === TAG RELATIONSHIP TESTS ===


@pytest.mark.integration
class TestRequirementTags(RequirementTestMixin, BaseEntityTests):
    """Verify the polymorphic tags relationship surfaces on requirement responses."""

    def test_requirement_response_includes_empty_tags_by_default(self, requirement_factory):
        """A newly created requirement has an empty `tags` list in the response."""
        requirement = requirement_factory.create(self.get_sample_data())

        # The factory returns the create response body; verify the field is present
        assert "tags" in requirement
        assert requirement["tags"] == []

    def test_requirement_list_includes_tags_field(self, requirement_factory):
        """`GET /requirements/` exposes `tags` (empty list when none assigned)."""
        requirement_factory.create(self.get_sample_data())

        response = requirement_factory.client.get(self.endpoints.list)

        assert response.status_code == status.HTTP_200_OK
        requirements = response.json()
        assert len(requirements) >= 1
        for entry in requirements:
            assert "tags" in entry
            assert isinstance(entry["tags"], list)

    def test_assigning_tag_to_requirement_updates_read_response(self, requirement_factory):
        """Assigning a tag via /tags/Requirement/{id} reflects in the requirement read."""
        requirement = requirement_factory.create(self.get_sample_data())
        requirement_id = requirement["id"]

        tag_payload = {"name": f"marketing-{fake.uuid4()}"}
        assign_response = requirement_factory.client.post(
            f"/tags/Requirement/{requirement_id}",
            json=tag_payload,
        )
        assert assign_response.status_code == status.HTTP_200_OK

        # Fetch the requirement and confirm the tag is now attached.
        get_response = requirement_factory.client.get(self.endpoints.get(requirement_id))
        assert get_response.status_code == status.HTTP_200_OK
        body = get_response.json()
        assert "tags" in body
        tag_names = [tag["name"] for tag in body["tags"]]
        assert tag_payload["name"] in tag_names

    def test_removing_tag_from_requirement_updates_read_response(self, requirement_factory):
        """Removing a tag clears it from the requirement's `tags` list."""
        requirement = requirement_factory.create(self.get_sample_data())
        requirement_id = requirement["id"]

        tag_payload = {"name": f"legal-{fake.uuid4()}"}
        assign_response = requirement_factory.client.post(
            f"/tags/Requirement/{requirement_id}",
            json=tag_payload,
        )
        assert assign_response.status_code == status.HTTP_200_OK
        tag_id = assign_response.json()["id"]

        remove_response = requirement_factory.client.delete(f"/tags/Requirement/{requirement_id}/{tag_id}")
        assert remove_response.status_code == status.HTTP_200_OK

        get_response = requirement_factory.client.get(self.endpoints.get(requirement_id))
        assert get_response.status_code == status.HTTP_200_OK
        body = get_response.json()
        assert tag_payload["name"] not in [tag["name"] for tag in body["tags"]]


# === EDGE CASE TESTS (Enhanced with Factory Data) ===


@pytest.mark.unit
class TestRequirementEdgeCases(RequirementTestMixin, BaseEntityTests):
    """Enhanced requirement edge case tests using factory system"""

    def test_create_requirement_long_name(self, requirement_factory):
        """Test creating requirement with very long name"""
        long_name_data = self.get_edge_case_data("long_name")

        # This might fail or succeed depending on your API validation
        response = requirement_factory.client.post(self.endpoints.create, json=long_name_data)

        # Adjust assertion based on your API's requirement
        assert response.status_code in [
            status.HTTP_200_OK,  # If long names are allowed
            status.HTTP_422_UNPROCESSABLE_ENTITY,  # If they're rejected
        ]

    def test_create_requirement_special_characters(self, requirement_factory):
        """Test creating requirement with special characters"""
        special_char_data = self.get_edge_case_data("special_chars")

        response = requirement_factory.client.post(self.endpoints.create, json=special_char_data)

        # Should handle special characters gracefully
        assert response.status_code == status.HTTP_200_OK
        created_requirement = response.json()
        assert created_requirement["name"] == special_char_data["name"]

    def test_create_requirement_unicode(self, requirement_factory):
        """Test creating requirement with unicode characters"""
        unicode_data = self.get_edge_case_data("unicode")

        response = requirement_factory.client.post(self.endpoints.create, json=unicode_data)

        assert response.status_code == status.HTTP_200_OK
        created_requirement = response.json()
        assert created_requirement["name"] == unicode_data["name"]

    def test_create_requirement_sql_injection_attempt(self, requirement_factory):
        """🛡️ Test requirement creation with SQL injection attempt"""
        injection_data = self.get_edge_case_data("sql_injection")

        response = requirement_factory.client.post(self.endpoints.create, json=injection_data)

        # Should either create safely or reject
        if response.status_code == status.HTTP_200_OK:
            # If created, verify it was sanitized
            created_requirement = response.json()
            assert created_requirement["name"] is not None
        else:
            # If rejected, should be a validation error
            assert response.status_code in [
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            ]


# === PERFORMANCE TESTS (Using Factory Batches) ===


@pytest.mark.slow
@pytest.mark.integration
class TestRequirementPerformance(RequirementTestMixin, BaseEntityTests):
    """Performance tests using factory batch creation"""

    def test_bulk_requirement_creation(self, requirement_factory):
        """🚀 Test creating multiple requirements efficiently"""
        # Generate batch data using factory
        batch_data = RequirementDataFactory.batch_data(count=20, variation=True)

        # Create all requirements using factory batch method
        requirements = requirement_factory.create_batch(batch_data)

        assert len(requirements) == 20
        assert all(b["id"] is not None for b in requirements)
        assert all(b["name"] is not None for b in requirements)

        # Verify they're all different (due to variation=True)
        names = [b["name"] for b in requirements]
        assert len(set(names)) == len(names)  # All unique names

    def test_requirement_list_pagination(self, requirement_factory, large_entity_batch):
        """🚀 Test list pagination with large dataset"""
        # large_entity_batch fixture creates 20 requirements
        requirements = large_entity_batch
        assert len(requirements) >= 10  # Should have substantial data

        # Test pagination
        response = requirement_factory.client.get(f"{self.endpoints.list}?limit=5&skip=0")
        assert response.status_code == status.HTTP_200_OK

        page_1 = response.json()
        assert len(page_1) <= 5  # Should respect limit

        # Test second page
        response = requirement_factory.client.get(f"{self.endpoints.list}?limit=5&skip=5")
        assert response.status_code == status.HTTP_200_OK

        page_2 = response.json()
        assert len(page_2) <= 5
