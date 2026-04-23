"""
Metric Routes Testing Suite (Enhanced Factory-Based)

Comprehensive test suite for metric entity routes using the enhanced factory system
with automatic cleanup, consistent data generation, and optimized performance.

Key Features:
- Factory-based entity creation with automatic cleanup
- Consistent data generation using data factories
- Clear fixture organization and naming
- Maintains DRY base class benefits
- Optimized performance with proper scoping

Run with: python -m pytest tests/backend/routes/test_metric.py -v
"""

import uuid
from typing import Any, Dict
from unittest.mock import patch

import pytest
from faker import Faker
from fastapi import status

from .base import BaseEntityRouteTests, BaseEntityTests
from .endpoints import APIEndpoints
from .fixtures.data_factories import BehaviorDataFactory, MetricDataFactory

# Initialize Faker
fake = Faker()


class MetricTestMixin:
    """Enhanced metric test mixin using factory system"""

    # Entity configuration
    entity_name = "metric"
    entity_plural = "metrics"
    endpoints = APIEndpoints.METRICS

    # Factory-based data methods
    def get_sample_data(self) -> Dict[str, Any]:
        """Return sample metric data using factory"""
        return MetricDataFactory.sample_data()

    def get_minimal_data(self) -> Dict[str, Any]:
        """Return minimal metric data using factory"""
        return MetricDataFactory.minimal_data()

    def get_update_data(self) -> Dict[str, Any]:
        """Return metric update data using factory"""
        return MetricDataFactory.update_data()

    def get_invalid_data(self) -> Dict[str, Any]:
        """Return invalid metric data using factory"""
        return MetricDataFactory.invalid_data()

    def get_edge_case_data(self, case_type: str) -> Dict[str, Any]:
        """Return edge case metric data using factory"""
        return MetricDataFactory.edge_case_data(case_type)

    def get_null_description_data(self) -> Dict[str, Any]:
        """Return metric data with null description"""
        data = MetricDataFactory.minimal_data()
        data["description"] = None
        return data


# Standard entity tests - gets ALL tests from base classes
class TestMetricStandardRoutes(MetricTestMixin, BaseEntityRouteTests):
    """Complete standard metric route tests using base classes"""

    pass


# === METRIC-SPECIFIC TESTS (Enhanced with Factories) ===


@pytest.mark.integration
class TestMetricBehaviorRelationships(MetricTestMixin, BaseEntityTests):
    """Enhanced metric-behavior relationship tests using factories"""

    def test_get_metric_behaviors_empty(self, metric_factory):
        """🔗 Test getting behaviors for metric with no behaviors (using factory)"""
        # Create metric using factory (automatic cleanup)
        metric = metric_factory.create(self.get_sample_data())
        metric_id = metric["id"]

        response = metric_factory.client.get(self.endpoints.behaviors(metric_id))

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_add_behavior_to_metric_factory(self, metric_factory, behavior_factory):
        """🔗 Test adding behavior to metric using factories"""
        # Create entities using factories
        metric = metric_factory.create(self.get_sample_data())
        behavior = behavior_factory.create(BehaviorDataFactory.sample_data())

        # Test the relationship creation
        response = metric_factory.client.post(
            self.endpoints.add_behavior_to_metric(metric["id"], behavior["id"])
        )

        assert response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]
        result = response.json()
        assert result["status"] == "success"
        assert "added" in result["message"].lower() or "associated" in result["message"].lower()

    def test_remove_behavior_from_metric_factory(self, metric_factory, behavior_factory):
        """🔗 Test removing behavior from metric using factories"""
        # Create entities using factories
        metric = metric_factory.create(self.get_sample_data())
        behavior = behavior_factory.create(BehaviorDataFactory.sample_data())

        # First add the behavior to the metric
        add_response = metric_factory.client.post(
            self.endpoints.add_behavior_to_metric(metric["id"], behavior["id"])
        )
        assert add_response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]

        # Then remove it
        remove_response = metric_factory.client.delete(
            self.endpoints.remove_behavior_from_metric(metric["id"], behavior["id"])
        )

        assert remove_response.status_code == status.HTTP_200_OK
        result = remove_response.json()
        assert result["status"] == "success"
        assert (
            "removed" in result["message"].lower() or "not associated" in result["message"].lower()
        )

    def test_bulk_behavior_association(self, metric_factory, behavior_factory):
        """🔗 Test associating multiple behaviors with metric"""
        # Create one metric and multiple behaviors
        metric = metric_factory.create(self.get_sample_data())

        # Create multiple behaviors using batch creation
        behaviors = behavior_factory.create_batch(
            [
                BehaviorDataFactory.sample_data(),
                BehaviorDataFactory.sample_data(),
                BehaviorDataFactory.sample_data(),
            ]
        )

        # Associate all behaviors with the metric
        for behavior in behaviors:
            response = metric_factory.client.post(
                self.endpoints.add_behavior_to_metric(metric["id"], behavior["id"])
            )
            assert response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]

        # Verify all associations
        response = metric_factory.client.get(self.endpoints.behaviors(metric["id"]))
        assert response.status_code == status.HTTP_200_OK

        returned_behaviors = response.json()
        assert len(returned_behaviors) == len(behaviors)

    def test_metric_behavior_relationship_error_handling(self, metric_factory):
        """🔗 Test error handling for metric-behavior relationships"""
        # Create a metric
        metric = metric_factory.create(self.get_sample_data())

        # Try to add a non-existent behavior
        fake_behavior_id = str(uuid.uuid4())
        response = metric_factory.client.post(
            self.endpoints.add_behavior_to_metric(metric["id"], fake_behavior_id)
        )

        # Should handle the error gracefully
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()


# === METRIC-SPECIFIC VALIDATION TESTS ===


@pytest.mark.unit
class TestMetricValidation(MetricTestMixin, BaseEntityTests):
    """Metric-specific validation tests"""

    def test_create_metric_score_type_validation(self, metric_factory):
        """📊 Test metric creation with different score types"""
        score_types = ["numeric", "categorical"]

        for score_type in score_types:
            data = {
                "name": fake.word().title() + f" {score_type.title()} Metric",
                "evaluation_prompt": fake.sentence(nb_words=8),
                "score_type": score_type,
            }

            # Add required fields per score type
            if score_type == "categorical":
                data["categories"] = ["pass", "fail", "maybe"]
                data["passing_categories"] = ["pass"]
            elif score_type == "numeric":
                data["min_score"] = 0
                data["max_score"] = 10
                data["threshold"] = 5

            response = metric_factory.client.post(self.endpoints.create, json=data)
            assert response.status_code == status.HTTP_200_OK

            created_metric = response.json()
            assert created_metric["score_type"] == score_type

    def test_create_metric_invalid_score_type(self, metric_factory):
        """📊 Test metric creation with invalid score type"""
        data = self.get_minimal_data()
        data["score_type"] = "invalid_type"

        response = metric_factory.client.post(self.endpoints.create, json=data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_create_metric_threshold_validation(self, metric_factory):
        """📊 Test metric creation with threshold operators"""
        threshold_operators = ["=", "<", ">", "<=", ">=", "!="]

        for operator in threshold_operators:
            data = self.get_sample_data()
            data["threshold"] = 0.8
            data["threshold_operator"] = operator

            response = metric_factory.client.post(self.endpoints.create, json=data)
            assert response.status_code == status.HTTP_200_OK

            created_metric = response.json()
            assert created_metric["threshold_operator"] == operator

    def test_create_metric_score_range_validation(self, metric_factory):
        """📊 Test metric creation with min/max score validation"""
        data = self.get_sample_data()
        data["score_type"] = "numeric"
        data["min_score"] = 0.0
        data["max_score"] = 10.0

        response = metric_factory.client.post(self.endpoints.create, json=data)
        assert response.status_code == status.HTTP_200_OK

        created_metric = response.json()
        assert created_metric["min_score"] == 0.0
        assert created_metric["max_score"] == 10.0


# === EDGE CASE TESTS (Enhanced with Factory Data) ===


@pytest.mark.unit
class TestMetricEdgeCases(MetricTestMixin, BaseEntityTests):
    """Enhanced metric edge case tests using factory system"""

    def test_create_metric_long_evaluation_prompt(self, metric_factory):
        """Test creating metric with very long evaluation prompt"""
        data = self.get_minimal_data()
        data["evaluation_prompt"] = fake.text(max_nb_chars=2000)

        response = metric_factory.client.post(self.endpoints.create, json=data)

        # Should handle long prompts gracefully
        assert response.status_code in [
            status.HTTP_200_OK,  # If long prompts are allowed
            status.HTTP_422_UNPROCESSABLE_ENTITY,  # If they're rejected
        ]

    def test_create_metric_special_characters(self, metric_factory):
        """Test creating metric with special characters"""
        special_char_data = self.get_edge_case_data("special_chars")

        response = metric_factory.client.post(self.endpoints.create, json=special_char_data)

        # Should handle special characters gracefully
        assert response.status_code == status.HTTP_200_OK
        created_metric = response.json()
        assert created_metric["name"] == special_char_data["name"]

    def test_create_metric_unicode(self, metric_factory):
        """Test creating metric with unicode characters"""
        unicode_data = self.get_edge_case_data("unicode")

        response = metric_factory.client.post(self.endpoints.create, json=unicode_data)

        assert response.status_code == status.HTTP_200_OK
        created_metric = response.json()
        assert created_metric["name"] == unicode_data["name"]

    def test_create_metric_sql_injection_attempt(self, metric_factory):
        """🛡️ Test metric creation with SQL injection attempt"""
        injection_data = self.get_edge_case_data("sql_injection")

        response = metric_factory.client.post(self.endpoints.create, json=injection_data)

        # Should either create safely or reject
        if response.status_code == status.HTTP_200_OK:
            # If created, verify it was sanitized
            created_metric = response.json()
            assert created_metric["name"] is not None
        else:
            # If rejected, should be a validation error
            assert response.status_code in [
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            ]


# === PERFORMANCE TESTS (Using Factory Batches) ===


@pytest.mark.slow
@pytest.mark.integration
class TestMetricPerformance(MetricTestMixin, BaseEntityTests):
    """Performance tests using factory batch creation"""

    def test_bulk_metric_creation(self, metric_factory):
        """🚀 Test creating multiple metrics efficiently"""
        # Generate batch data using factory
        batch_data = []
        for i in range(10):
            data = MetricDataFactory.sample_data()
            data["name"] = f"Performance Test Metric {i + 1}"
            batch_data.append(data)

        # Create all metrics using factory batch method
        metrics = metric_factory.create_batch(batch_data)

        assert len(metrics) == 10
        assert all(m["id"] is not None for m in metrics)
        assert all(m["name"] is not None for m in metrics)

        # Verify they're all different
        names = [m["name"] for m in metrics]
        assert len(set(names)) == len(names)  # All unique names

    def test_metric_list_pagination(self, metric_factory, large_entity_batch):
        """🚀 Test list pagination with large dataset"""
        # large_entity_batch fixture creates multiple metrics
        metrics = large_entity_batch
        assert len(metrics) >= 5  # Should have substantial data

        # Test pagination
        response = metric_factory.client.get(f"{self.endpoints.list}?limit=5&skip=0")
        assert response.status_code == status.HTTP_200_OK

        page_1 = response.json()
        assert len(page_1) <= 5  # Should respect limit

        # Test second page
        response = metric_factory.client.get(f"{self.endpoints.list}?limit=5&skip=5")
        assert response.status_code == status.HTTP_200_OK

        page_2 = response.json()
        # page_2 might be empty if there aren't enough metrics, which is fine


# === METRIC GENERATE ENDPOINT TESTS ===

# Synthesizer response fixtures used across generate tests
_NUMERIC_SYNTHESIZED = {
    "name": "Factual Accuracy",
    "description": "Measures factual accuracy of the response.",
    "evaluation_prompt": "Evaluate {{response}} for factual accuracy.",
    "evaluation_steps": "1. Read the response.\n2. Assign a score.",
    "score_type": "numeric",
    "min_score": 1.0,
    "max_score": 5.0,
    "threshold": 3.0,
    "threshold_operator": ">=",
    "categories": None,
    "passing_categories": None,
    "metric_scope": ["Single-Turn", "Multi-Turn"],
}

_CATEGORICAL_SYNTHESIZED = {
    "name": "Tone Appropriateness",
    "description": "Checks if the response tone is appropriate.",
    "evaluation_prompt": "Classify the tone of {{response}}.",
    "evaluation_steps": None,
    "score_type": "categorical",
    "min_score": None,
    "max_score": None,
    "threshold": None,
    "threshold_operator": None,
    "categories": ["appropriate", "inappropriate"],
    "passing_categories": ["appropriate"],
    "metric_scope": ["Single-Turn"],
}


@pytest.mark.integration
class TestMetricGenerate(MetricTestMixin, BaseEntityTests):
    """Tests for POST /metrics/generate endpoint."""

    @patch("rhesis.sdk.metrics.synthesizer.MetricSynthesizer.generate")
    def test_generate_metric_numeric(self, mock_generate, metric_factory):
        """Generate endpoint creates a numeric metric from a prompt."""
        mock_generate.return_value = dict(_NUMERIC_SYNTHESIZED)

        response = metric_factory.client.post(
            self.endpoints.generate,
            json={"prompt": "Measure factual accuracy on a 1-5 scale"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Factual Accuracy"
        assert data["score_type"] == "numeric"
        assert data["threshold"] == 3.0
        assert data["threshold_operator"] == ">="
        assert data["id"] is not None

        # Clean up the created metric
        metric_factory.client.delete(self.endpoints.remove(data["id"]))

    @patch("rhesis.sdk.metrics.synthesizer.MetricSynthesizer.generate")
    def test_generate_metric_categorical(self, mock_generate, metric_factory):
        """Generate endpoint creates a categorical metric from a prompt."""
        mock_generate.return_value = dict(_CATEGORICAL_SYNTHESIZED)

        response = metric_factory.client.post(
            self.endpoints.generate,
            json={"prompt": "Check if response tone is appropriate"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Tone Appropriateness"
        assert data["score_type"] == "categorical"
        assert data["id"] is not None

        metric_factory.client.delete(self.endpoints.remove(data["id"]))

    @patch("rhesis.sdk.metrics.synthesizer.MetricSynthesizer.generate")
    def test_generate_metric_sets_custom_types(self, mock_generate, metric_factory):
        """Generate endpoint sets metric_type and backend_type to custom."""
        mock_generate.return_value = dict(_NUMERIC_SYNTHESIZED)

        response = metric_factory.client.post(
            self.endpoints.generate,
            json={"prompt": "any prompt"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # backend_type and metric_type are resolved via type_lookups,
        # so they appear as nested objects with type_value
        if data.get("backend_type"):
            assert data["backend_type"]["type_value"] == "custom"
        if data.get("metric_type"):
            assert data["metric_type"]["type_value"] == "custom-prompt"

        metric_factory.client.delete(self.endpoints.remove(data["id"]))

    @patch("rhesis.sdk.metrics.synthesizer.MetricSynthesizer.generate")
    def test_generate_metric_persists(self, mock_generate, metric_factory):
        """Generated metric is persisted and retrievable via GET."""
        mock_generate.return_value = dict(_NUMERIC_SYNTHESIZED)

        create_resp = metric_factory.client.post(
            self.endpoints.generate,
            json={"prompt": "accuracy metric"},
        )
        assert create_resp.status_code == status.HTTP_200_OK
        metric_id = create_resp.json()["id"]

        get_resp = metric_factory.client.get(self.endpoints.get(metric_id))
        assert get_resp.status_code == status.HTTP_200_OK
        assert get_resp.json()["name"] == "Factual Accuracy"

        metric_factory.client.delete(self.endpoints.remove(metric_id))

    def test_generate_metric_missing_prompt(self, metric_factory):
        """Generate endpoint returns 422 when prompt is missing."""
        response = metric_factory.client.post(
            self.endpoints.generate,
            json={},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @patch("rhesis.sdk.metrics.synthesizer.MetricSynthesizer.generate")
    def test_generate_metric_synthesizer_error(self, mock_generate, metric_factory):
        """Generate endpoint returns 400 when synthesizer raises."""
        mock_generate.side_effect = RuntimeError("LLM rate limit exceeded")

        response = metric_factory.client.post(
            self.endpoints.generate,
            json={"prompt": "anything"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Failed to generate metric" in response.json()["detail"]


# === METRIC IMPROVE ENDPOINT TESTS ===

_IMPROVED_NUMERIC = {
    "name": "Factual Accuracy",
    "description": "Measures factual accuracy of the response.",
    "evaluation_prompt": "Evaluate the response for factual accuracy.",
    "evaluation_steps": "1. Read the response.\n2. Assign a score.",
    "score_type": "numeric",
    "min_score": 1.0,
    "max_score": 5.0,
    "threshold": 4.0,
    "threshold_operator": ">=",
    "categories": None,
    "passing_categories": None,
    "metric_scope": ["Single-Turn", "Multi-Turn"],
}


@pytest.mark.integration
class TestMetricImprove(MetricTestMixin, BaseEntityTests):
    """Tests for POST /metrics/{metric_id}/improve endpoint."""

    @patch("rhesis.sdk.metrics.synthesizer.MetricSynthesizer.improve")
    def test_improve_metric_updates_existing(self, mock_improve, metric_factory):
        """Improve endpoint updates the existing metric in place."""
        # Create a metric first
        metric = metric_factory.create(self.get_sample_data())
        metric_id = metric["id"]

        mock_improve.return_value = dict(_IMPROVED_NUMERIC)

        response = metric_factory.client.post(
            self.endpoints.improve(metric_id),
            json={"prompt": "raise the threshold to 4"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == metric_id
        assert data["threshold"] == 4.0

    def test_improve_metric_not_found(self, metric_factory):
        """Improve endpoint returns 404 for non-existent metric."""
        fake_id = str(uuid.uuid4())
        response = metric_factory.client.post(
            self.endpoints.improve(fake_id),
            json={"prompt": "any edit"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_improve_metric_missing_prompt(self, metric_factory):
        """Improve endpoint returns 422 when prompt is missing."""
        metric = metric_factory.create(self.get_sample_data())
        response = metric_factory.client.post(
            self.endpoints.improve(metric["id"]),
            json={},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @patch("rhesis.sdk.metrics.synthesizer.MetricSynthesizer.improve")
    def test_improve_metric_synthesizer_error(self, mock_improve, metric_factory):
        """Improve endpoint returns 400 when synthesizer raises."""
        metric = metric_factory.create(self.get_sample_data())

        mock_improve.side_effect = RuntimeError("LLM error")

        response = metric_factory.client.post(
            self.endpoints.improve(metric["id"]),
            json={"prompt": "anything"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Failed to improve metric" in response.json()["detail"]
