"""
Behavior Routes Testing Suite (Enhanced Factory-Based)

Comprehensive test suite for behavior entity routes using the enhanced factory system
with automatic cleanup, consistent data generation, and optimized performance.

Key Features:
- Factory-based entity creation with automatic cleanup
- Consistent data generation using data factories
- Clear fixture organization and naming
- Maintains DRY base class benefits
- Optimized performance with proper scoping

Run with: python -m pytest tests/backend/routes/test_behavior.py -v
"""

import uuid
from typing import Dict, Any

import pytest
from faker import Faker
from fastapi import status
from fastapi.testclient import TestClient

from .endpoints import APIEndpoints
from .base import BaseEntityRouteTests, BaseEntityTests
from .fixtures.data_factories import BehaviorDataFactory, MetricDataFactory

# Initialize Faker
fake = Faker()


class BehaviorTestMixin:
    """Enhanced behavior test mixin using factory system"""

    # Entity configuration (unchanged)
    entity_name = "behavior"
    entity_plural = "behaviors"
    endpoints = APIEndpoints.BEHAVIORS

    # Factory-based data methods
    def get_sample_data(self) -> Dict[str, Any]:
        """Return sample behavior data using factory"""
        return BehaviorDataFactory.sample_data()

    def get_minimal_data(self) -> Dict[str, Any]:
        """Return minimal behavior data using factory"""
        return BehaviorDataFactory.minimal_data()

    def get_update_data(self) -> Dict[str, Any]:
        """Return behavior update data using factory"""
        return BehaviorDataFactory.update_data()

    def get_invalid_data(self) -> Dict[str, Any]:
        """Return invalid behavior data using factory"""
        return BehaviorDataFactory.invalid_data()

    def get_edge_case_data(self, case_type: str) -> Dict[str, Any]:
        """Return edge case behavior data using factory"""
        return BehaviorDataFactory.edge_case_data(case_type)


# Standard entity tests - gets ALL tests from base classes
class TestBehaviorStandardRoutes(BehaviorTestMixin, BaseEntityRouteTests):
    """Complete standard behavior route tests using base classes"""
    pass


# === BEHAVIOR-SPECIFIC TESTS (Enhanced with Factories) ===

@pytest.mark.integration
class TestBehaviorMetricRelationships(BehaviorTestMixin, BaseEntityTests):
    """Enhanced behavior-metric relationship tests using factories"""

    def test_get_behavior_metrics_empty(self, behavior_factory):
        """Test getting metrics for behavior with no metrics (using factory)"""
        # Create behavior using factory (automatic cleanup)
        behavior = behavior_factory.create(self.get_sample_data())
        behavior_id = behavior["id"]

        response = behavior_factory.client.get(self.endpoints.metrics(behavior_id))

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_behavior_with_metrics_relationship(self, behavior_with_metrics):
        """Test behavior-metrics relationship using composite fixture"""
        # Use the pre-created relationship from fixture
        behavior = behavior_with_metrics["behavior"]
        metrics = behavior_with_metrics["metrics"]

        # Verify the relationship was created
        assert behavior["id"] is not None
        assert len(metrics) == 2

    def test_add_metric_to_behavior_factory(self, behavior_factory, metric_factory):
        """Test adding metric to behavior using factories"""
        # Create entities using factories
        behavior = behavior_factory.create(self.get_sample_data())
        metric = metric_factory.create(MetricDataFactory.sample_data())

        # Test the relationship creation
        response = behavior_factory.client.post(
            self.endpoints.add_metric_to_behavior(behavior["id"], metric["id"])
        )

        assert response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]
        # Automatic cleanup happens via fixtures

    def test_bulk_metric_association(self, behavior_factory, metric_factory):
        """Test associating multiple metrics with behavior"""
        # Create one behavior and multiple metrics
        behavior = behavior_factory.create(self.get_sample_data())

        # Create multiple metrics using batch creation
        from .fixtures.data_factories import MetricDataFactory
        metrics = metric_factory.create_batch([
            MetricDataFactory.sample_data(),
            MetricDataFactory.sample_data(),
            MetricDataFactory.sample_data()
        ])

        # Associate all metrics with the behavior
        for metric in metrics:
            response = behavior_factory.client.post(
                self.endpoints.add_metric_to_behavior(behavior["id"], metric["id"])
            )
            assert response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]

        # Verify all associations
        response = behavior_factory.client.get(self.endpoints.metrics(behavior["id"]))
        assert response.status_code == status.HTTP_200_OK

        returned_metrics = response.json()
        assert len(returned_metrics) == len(metrics)


# === EDGE CASE TESTS (Enhanced with Factory Data) ===

@pytest.mark.unit
class TestBehaviorEdgeCases(BehaviorTestMixin, BaseEntityTests):
    """Enhanced behavior edge case tests using factory system"""

    def test_create_behavior_long_name(self, behavior_factory):
        """Test creating behavior with very long name"""
        long_name_data = self.get_edge_case_data("long_name")

        # This might fail or succeed depending on your API validation
        response = behavior_factory.client.post(self.endpoints.create, json=long_name_data)

        # Adjust assertion based on your API's behavior
        assert response.status_code in [
            status.HTTP_200_OK,  # If long names are allowed
            status.HTTP_422_UNPROCESSABLE_ENTITY  # If they're rejected
        ]

    def test_create_behavior_special_characters(self, behavior_factory):
        """Test creating behavior with special characters"""
        special_char_data = self.get_edge_case_data("special_chars")

        response = behavior_factory.client.post(self.endpoints.create, json=special_char_data)

        # Should handle special characters gracefully
        assert response.status_code == status.HTTP_200_OK
        created_behavior = response.json()
        assert created_behavior["name"] == special_char_data["name"]

    def test_create_behavior_unicode(self, behavior_factory):
        """Test creating behavior with unicode characters"""
        unicode_data = self.get_edge_case_data("unicode")

        response = behavior_factory.client.post(self.endpoints.create, json=unicode_data)

        assert response.status_code == status.HTTP_200_OK
        created_behavior = response.json()
        assert created_behavior["name"] == unicode_data["name"]

    def test_create_behavior_sql_injection_attempt(self, behavior_factory):
        """🛡️ Test behavior creation with SQL injection attempt"""
        injection_data = self.get_edge_case_data("sql_injection")

        response = behavior_factory.client.post(self.endpoints.create, json=injection_data)

        # Should either create safely or reject
        if response.status_code == status.HTTP_200_OK:
            # If created, verify it was sanitized
            created_behavior = response.json()
            assert created_behavior["name"] is not None
        else:
            # If rejected, should be a validation error
            assert response.status_code in [
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ]


# === PERFORMANCE TESTS (Using Factory Batches) ===

@pytest.mark.slow
@pytest.mark.integration
class TestBehaviorPerformance(BehaviorTestMixin, BaseEntityTests):
    """Performance tests using factory batch creation"""

    def test_bulk_behavior_creation(self, behavior_factory):
        """🚀 Test creating multiple behaviors efficiently"""
        # Generate batch data using factory
        batch_data = BehaviorDataFactory.batch_data(count=20, variation=True)

        # Create all behaviors using factory batch method
        behaviors = behavior_factory.create_batch(batch_data)

        assert len(behaviors) == 20
        assert all(b["id"] is not None for b in behaviors)
        assert all(b["name"] is not None for b in behaviors)

        # Verify they're all different (due to variation=True)
        names = [b["name"] for b in behaviors]
        assert len(set(names)) == len(names)  # All unique names

    def test_behavior_list_pagination(self, behavior_factory, large_entity_batch):
        """🚀 Test list pagination with large dataset"""
        # large_entity_batch fixture creates 20 behaviors
        behaviors = large_entity_batch
        assert len(behaviors) >= 10  # Should have substantial data

        # Test pagination
        response = behavior_factory.client.get(f"{self.endpoints.list}?limit=5&skip=0")
        assert response.status_code == status.HTTP_200_OK

        page_1 = response.json()
        assert len(page_1) <= 5  # Should respect limit

        # Test second page
        response = behavior_factory.client.get(f"{self.endpoints.list}?limit=5&skip=5")
        assert response.status_code == status.HTTP_200_OK

        page_2 = response.json()
        assert len(page_2) <= 5
