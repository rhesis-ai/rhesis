"""
🧪 Behavior Routes Testing Suite (DRY Implementation)

Comprehensive test suite for all behavior entity routes using the DRY approach
with base test classes. This ensures uniformity across all backend route implementations.

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
from .faker_utils import TestDataGenerator

# Initialize Faker
fake = Faker()


class BehaviorTestMixin:
    """Mixin providing behavior-specific test data and configuration"""
    
    # Entity configuration
    entity_name = "behavior"
    entity_plural = "behaviors"
    endpoints = APIEndpoints.BEHAVIORS
    
    def get_sample_data(self) -> Dict[str, Any]:
        """Return sample behavior data for testing"""
        return {
            "name": fake.catch_phrase(),
            "description": fake.text(max_nb_chars=200),
            "status_id": None,
            "user_id": None,
            "organization_id": None
        }
    
    def get_minimal_data(self) -> Dict[str, Any]:
        """Return minimal behavior data for creation"""
        return {
            "name": fake.word().title() + " " + fake.bs().title()
        }
    
    def get_update_data(self) -> Dict[str, Any]:
        """Return behavior update data"""
        return {
            "name": fake.sentence(nb_words=3).rstrip('.'),
            "description": fake.paragraph(nb_sentences=2)
        }


# Standard entity tests - gets ALL tests from base classes
class TestBehaviorStandardRoutes(BehaviorTestMixin, BaseEntityRouteTests):
    """Complete standard behavior route tests using base classes"""
    pass


# Behavior-specific tests for additional functionality
@pytest.mark.integration
class TestBehaviorMetricRelationships(BehaviorTestMixin, BaseEntityTests):
    """Behavior-specific tests for metric relationships"""
    
    # sample_metric fixture is automatically available from fixtures.py

    def test_get_behavior_metrics_empty(self, authenticated_client: TestClient):
        """🔗 Test getting metrics for behavior with no metrics"""
        behavior = self.create_entity(authenticated_client)
        behavior_id = behavior["id"]
        
        response = authenticated_client.get(self.endpoints.metrics(behavior_id))
        
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_get_behavior_metrics_not_found(self, authenticated_client: TestClient):
        """🔗 Test getting metrics for non-existent behavior"""
        non_existent_id = str(uuid.uuid4())
        
        response = authenticated_client.get(self.endpoints.metrics(non_existent_id))
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_add_metric_to_behavior_success(self, authenticated_client: TestClient, sample_metric):
        """🔗 Test successfully adding metric to behavior"""
        behavior = self.create_entity(authenticated_client)
        behavior_id = behavior["id"]
        metric_id = sample_metric["id"]
        
        response = authenticated_client.post(self.endpoints.add_metric_to_behavior(behavior_id, metric_id))
        
        # Should return success message or 200/201 status
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]
        
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            assert "status" in data
            assert data["status"] == "success"

    def test_add_metric_to_behavior_not_found(self, authenticated_client: TestClient, created_metric):
        """🔗 Test adding metric to non-existent behavior"""
        non_existent_behavior_id = str(uuid.uuid4())
        metric_id = sample_metric["id"]
        
        response = authenticated_client.post(self.endpoints.add_metric_to_behavior(non_existent_behavior_id, metric_id))
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_add_nonexistent_metric_to_behavior(self, authenticated_client: TestClient):
        """🔗 Test adding non-existent metric to behavior"""
        behavior = self.create_entity(authenticated_client)
        behavior_id = behavior["id"]
        non_existent_metric_id = str(uuid.uuid4())
        
        response = authenticated_client.post(self.endpoints.add_metric_to_behavior(behavior_id, non_existent_metric_id))
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_remove_metric_from_behavior_success(self, authenticated_client: TestClient, created_metric):
        """🔗 Test successfully removing metric from behavior"""
        behavior = self.create_entity(authenticated_client)
        behavior_id = behavior["id"]
        metric_id = sample_metric["id"]
        
        # First add the metric
        add_response = authenticated_client.post(self.endpoints.add_metric_to_behavior(behavior_id, metric_id))
        assert add_response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]
        
        # Then remove it
        response = authenticated_client.delete(self.endpoints.remove_metric_from_behavior(behavior_id, metric_id))
        
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert "status" in data
        assert data["status"] == "success"

    def test_remove_metric_from_behavior_not_found(self, authenticated_client: TestClient, created_metric):
        """🔗 Test removing metric from non-existent behavior"""
        non_existent_behavior_id = str(uuid.uuid4())
        metric_id = sample_metric["id"]
        
        response = authenticated_client.delete(self.endpoints.remove_metric_from_behavior(non_existent_behavior_id, metric_id))
        
        assert response.status_code == status.HTTP_404_NOT_FOUND


# Behavior-specific edge cases (if any)
@pytest.mark.unit
class TestBehaviorSpecificEdgeCases(BehaviorTestMixin, BaseEntityTests):
    """Behavior-specific edge cases beyond the standard ones"""
    
    def test_create_behavior_with_invalid_status(self, authenticated_client: TestClient):
        """🧩 Test creating behavior with non-existent status"""
        behavior_data = {
            "name": fake.catch_phrase(),
            "description": fake.text(max_nb_chars=100),
            "status_id": str(uuid.uuid4())  # Non-existent status
        }

        response = authenticated_client.post(self.endpoints.create, json=behavior_data)

        # API should handle foreign key constraint violations gracefully
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "invalid" in response.json()["detail"].lower() or "not found" in response.json()["detail"].lower()
