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
from .fixtures.data_factories import MetricDataFactory, RequirementDataFactory

# Initialize Faker
fake = Faker()


class MetricTestMixin:
    """Enhanced metric test mixin using factory system"""

    # Entity configuration
    entity_name = "metric"
    entity_plural = "metrics"
    endpoints = APIEndpoints.METRICS

    # Factory-based data methods
    def get_sample_data(self, client=None) -> Dict[str, Any]:
        """Return sample metric data using factory"""
        return MetricDataFactory.sample_data()

    def get_minimal_data(self, client=None) -> Dict[str, Any]:
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
class TestMetricRequirementRelationships(MetricTestMixin, BaseEntityTests):
    """Enhanced metric-requirement relationship tests using factories"""

    def test_get_metric_requirements_empty(self, metric_factory):
        """🔗 Test getting requirements for metric with no requirements (using factory)"""
        # Create metric using factory (automatic cleanup)
        metric = metric_factory.create(self.get_sample_data())
        metric_id = metric["id"]

        response = metric_factory.client.get(self.endpoints.requirements(metric_id))

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_add_requirement_to_metric_factory(self, metric_factory, requirement_factory):
        """🔗 Test adding requirement to metric using factories"""
        # Create entities using factories
        metric = metric_factory.create(self.get_sample_data())
        requirement = requirement_factory.create(RequirementDataFactory.sample_data())

        # Test the relationship creation
        response = metric_factory.client.post(
            self.endpoints.add_requirement_to_metric(metric["id"], requirement["id"])
        )

        assert response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]
        result = response.json()
        assert result["status"] == "success"
        assert "added" in result["message"].lower() or "associated" in result["message"].lower()

    def test_remove_requirement_from_metric_factory(self, metric_factory, requirement_factory):
        """🔗 Test removing requirement from metric using factories"""
        # Create entities using factories
        metric = metric_factory.create(self.get_sample_data())
        requirement = requirement_factory.create(RequirementDataFactory.sample_data())

        # First add the requirement to the metric
        add_response = metric_factory.client.post(
            self.endpoints.add_requirement_to_metric(metric["id"], requirement["id"])
        )
        assert add_response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]

        # Then remove it
        remove_response = metric_factory.client.delete(
            self.endpoints.remove_requirement_from_metric(metric["id"], requirement["id"])
        )

        assert remove_response.status_code == status.HTTP_200_OK
        result = remove_response.json()
        assert result["status"] == "success"
        assert (
            "removed" in result["message"].lower() or "not associated" in result["message"].lower()
        )

    def test_bulk_requirement_association(self, metric_factory, requirement_factory):
        """🔗 Test associating multiple requirements with metric"""
        # Create one metric and multiple requirements
        metric = metric_factory.create(self.get_sample_data())

        # Create multiple requirements using batch creation
        requirements = requirement_factory.create_batch(
            [
                RequirementDataFactory.sample_data(),
                RequirementDataFactory.sample_data(),
                RequirementDataFactory.sample_data(),
            ]
        )

        # Associate all requirements with the metric
        for requirement in requirements:
            response = metric_factory.client.post(
                self.endpoints.add_requirement_to_metric(metric["id"], requirement["id"])
            )
            assert response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]

        # Verify all associations
        response = metric_factory.client.get(self.endpoints.requirements(metric["id"]))
        assert response.status_code == status.HTTP_200_OK

        returned_requirements = response.json()
        assert len(returned_requirements) == len(requirements)

    def test_metric_requirement_relationship_error_handling(self, metric_factory):
        """🔗 Test error handling for metric-requirement relationships"""
        # Create a metric
        metric = metric_factory.create(self.get_sample_data())

        # Try to add a non-existent requirement
        fake_requirement_id = str(uuid.uuid4())
        response = metric_factory.client.post(
            self.endpoints.add_requirement_to_metric(metric["id"], fake_requirement_id)
        )

        # Should handle the error gracefully
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()


@pytest.mark.integration
class TestMetricSoftDeleteContract(MetricTestMixin, BaseEntityTests):
    """A soft-deleted metric must surface 410 GONE everywhere, including through
    @handle_database_exceptions-wrapped routes -- not just the plain GET."""

    def test_update_deleted_metric_returns_410(self, metric_factory):
        metric = metric_factory.create(self.get_sample_data())
        metric_id = metric["id"]

        delete_response = metric_factory.client.delete(self.endpoints.remove(metric_id))
        assert delete_response.status_code == status.HTTP_200_OK

        response = metric_factory.client.put(
            self.endpoints.put(metric_id), json=self.get_update_data()
        )

        assert response.status_code == status.HTTP_410_GONE

    def test_improve_deleted_metric_returns_410(self, metric_factory):
        metric = metric_factory.create(self.get_sample_data())
        metric_id = metric["id"]

        delete_response = metric_factory.client.delete(self.endpoints.remove(metric_id))
        assert delete_response.status_code == status.HTTP_200_OK

        response = metric_factory.client.post(
            self.endpoints.improve(metric_id), json={"prompt": "make it stricter"}
        )

        assert response.status_code == status.HTTP_410_GONE


# === FRAMEWORK METRIC ACCESS TESTS ===


@pytest.mark.integration
class TestMetricDetailAccessRestriction(MetricTestMixin, BaseEntityTests):
    """Every metric can be read; a framework metric's definition can't be edited."""

    @pytest.mark.parametrize("backend", ["deepeval", "garak", "ragas"])
    def test_get_framework_metric_returns_200(self, backend, metric_factory):
        """GET /metrics/{id} serves a metric owned by an evaluation framework."""
        data = self.get_sample_data()
        data["backend_type"] = backend
        metric = metric_factory.create(data)

        get_resp = metric_factory.client.get(self.endpoints.get(metric["id"]))
        assert get_resp.status_code == status.HTTP_200_OK
        assert get_resp.json()["backend_type"]["type_value"] == backend

    @pytest.mark.parametrize("backend", ["deepeval", "garak", "ragas"])
    def test_update_framework_metric_returns_403(self, backend, metric_factory):
        """PUT /metrics/{id} refuses a framework metric and leaves it unchanged."""
        data = self.get_sample_data()
        data["backend_type"] = backend
        metric = metric_factory.create(data)

        put_resp = metric_factory.client.put(
            self.endpoints.put(metric["id"]), json={"threshold": 0.9}
        )
        assert put_resp.status_code == status.HTTP_403_FORBIDDEN
        assert "read-only" in put_resp.json()["detail"]

        get_resp = metric_factory.client.get(self.endpoints.get(metric["id"]))
        assert get_resp.json()["threshold"] == metric["threshold"]

    @pytest.mark.parametrize("backend", ["deepeval", "garak", "ragas"])
    def test_framework_metric_target_can_change(self, backend, metric_factory):
        """The target says where a framework metric is applied, so it stays editable."""
        data = self.get_sample_data()
        data["backend_type"] = backend
        metric = metric_factory.create(data)
        current = metric["config"]["target"]["on"]
        other = next(t for t in metric["supported_targets"] if t != current)

        put_resp = metric_factory.client.put(
            self.endpoints.put(metric["id"]), json={"config": {"target": {"on": other}}}
        )

        assert put_resp.status_code == status.HTTP_200_OK, put_resp.text
        assert put_resp.json()["config"]["target"]["on"] == other

    @pytest.mark.parametrize(
        "body",
        [
            {"config": {"target": {"on": "run"}}, "threshold": 0.9},
            {"config": {"target": {"on": "run"}, "strict_mode": True}},
        ],
        ids=["with another field", "with another setting"],
    )
    def test_framework_metric_target_change_cant_carry_more(self, body, metric_factory):
        """Only the target changes: anything else in the same update is refused."""
        data = self.get_sample_data()
        data["backend_type"] = "deepeval"
        metric = metric_factory.create(data)

        put_resp = metric_factory.client.put(self.endpoints.put(metric["id"]), json=body)

        assert put_resp.status_code == status.HTTP_403_FORBIDDEN
        assert "except their target" in put_resp.json()["detail"]
        get_resp = metric_factory.client.get(self.endpoints.get(metric["id"]))
        assert get_resp.json()["config"] == metric["config"]

    @pytest.mark.parametrize("backend", ["deepeval", "garak", "ragas"])
    def test_improve_framework_metric_returns_403(self, backend, metric_factory):
        """POST /metrics/{id}/improve refuses a framework metric before any generation."""
        data = self.get_sample_data()
        data["backend_type"] = backend
        metric = metric_factory.create(data)

        response = metric_factory.client.post(
            self.endpoints.improve(metric["id"]), json={"prompt": "make it stricter"}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "read-only" in response.json()["detail"]

    @pytest.mark.parametrize("backend", ["custom", None])
    def test_update_own_metric_still_allowed(self, backend, metric_factory):
        """PUT /metrics/{id} still edits custom metrics and ones with no backend type."""
        data = self.get_sample_data()
        if backend:
            data["backend_type"] = backend
        metric = metric_factory.create(data)

        put_resp = metric_factory.client.put(
            self.endpoints.put(metric["id"]), json={"threshold": 0.9}
        )
        assert put_resp.status_code == status.HTTP_200_OK
        assert put_resp.json()["threshold"] == 0.9

    def test_get_custom_metric_returns_200(self, metric_factory):
        """GET /metrics/{id} returns 200 for a custom metric.

        The organization owns a custom metric's evaluation prompt, the metrics grid
        links to it, and metric tuning runs on nothing else -- so the detail route
        has to serve it.
        """
        data = self.get_sample_data()
        data["backend_type"] = "custom"
        metric = metric_factory.create(data)

        get_resp = metric_factory.client.get(self.endpoints.get(metric["id"]))
        assert get_resp.status_code == status.HTTP_200_OK
        assert get_resp.json()["backend_type"]["type_value"] == "custom"

    def test_get_rhesis_metric_returns_200(self, metric_factory):
        """GET /metrics/{id} returns 200 for a standard (no backend_type) metric."""
        metric = metric_factory.create(self.get_sample_data())
        metric_id = metric["id"]

        get_resp = metric_factory.client.get(self.endpoints.get(metric_id))
        assert get_resp.status_code == status.HTTP_200_OK

    def test_list_metrics_unaffected(self, metric_factory):
        """GET /metrics (list) still returns all metrics regardless of backend_type."""
        metric_factory.create(self.get_sample_data())

        response = metric_factory.client.get(self.endpoints.list)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) >= 1


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

    def test_create_metric_stores_and_returns_its_default_target(self, metric_factory):
        response = metric_factory.client.post(self.endpoints.create, json=self.get_minimal_data())

        assert response.status_code == status.HTTP_200_OK
        created = response.json()
        assert created["config"]["target"] == {"on": "turn"}
        assert "metric_scope" not in created
        assert "conversation" in created["supported_targets"]

    def test_create_metric_refuses_a_scope(self, metric_factory):
        """metric_scope is gone; an old client sending one is told what replaced it."""
        data = self.get_minimal_data()
        data["metric_scope"] = ["Multi-Turn"]

        response = metric_factory.client.post(self.endpoints.create, json=data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "replaced by the target" in response.text

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

    def test_metric_list_with_target_filter(self, metric_factory):
        """The target filter keeps matching metrics and the X-Total-Count override."""
        whole = self.get_sample_data()
        whole["config"] = {"target": {"on": "conversation"}}
        conversation_id = metric_factory.create(whole)["id"]
        turn_id = metric_factory.create(self.get_sample_data())["id"]

        response = metric_factory.client.get(f"{self.endpoints.list}?target=conversation&limit=100")

        assert response.status_code == status.HTTP_200_OK
        ids = {m["id"] for m in response.json()}
        assert conversation_id in ids and turn_id not in ids
        assert all(m["config"]["target"]["on"] == "conversation" for m in response.json())
        assert int(response.headers["X-Total-Count"]) == len(response.json())

    def test_metric_targets_lists_the_registry(self, metric_factory):
        from rhesis.sdk.metrics.targets import TARGETS

        response = metric_factory.client.get(f"{self.endpoints.list}targets")

        assert response.status_code == status.HTTP_200_OK
        choices = response.json()["targets"]
        assert [c["on"] for c in choices] == [kind.value for kind in TARGETS]
        assert choices[0] == {
            "on": "turn",
            "label": "Each turn",
            "description": TARGETS["turn"].description,
            "per_span": False,
            "span_kind": None,
        }
        tool_call = next(c for c in choices if c["on"] == "tool_call")
        assert tool_call["per_span"] is True
        assert tool_call["span_kind"] == "tool.invoke"

    def test_metric_targets_lists_the_parts_of_a_condition(self, metric_factory):
        from rhesis.sdk.metrics.conditions import CONDITION_OPS, SPECIAL_FIELDS

        response = metric_factory.client.get(f"{self.endpoints.list}targets")

        body = response.json()
        operators = {o["op"]: o for o in body["operators"]}
        assert list(operators) == [op.value for op in CONDITION_OPS]
        assert operators["exists"] == {"op": "exists", "takes_value": False, "value_type": "none"}
        assert operators["<="]["value_type"] == "number"
        assert operators["not_in"]["value_type"] == "list"
        assert operators["matches"]["value_type"] == "pattern"
        assert operators["contains"] == {
            "op": "contains",
            "takes_value": True,
            "value_type": "text",
        }
        assert body["special_fields"] == [
            {"field": field.value, "label": label} for field, label in SPECIAL_FIELDS.items()
        ]
        assert body["special_fields"][3] == {"field": "duration_ms", "label": "Duration (ms)"}

    def test_metric_targets_lists_what_read_may_name(self, metric_factory):
        from rhesis.sdk.metrics.targets import EVENT_READER, READERS

        response = metric_factory.client.get(f"{self.endpoints.list}targets")

        body = response.json()
        assert [r["reader"] for r in body["readers"]] == [reader.value for reader in READERS]
        assert all(r["label"] for r in body["readers"])
        assert body["readers"][0] == {"reader": "input", "label": "Its own input"}
        assert body["event_prefix"] == EVENT_READER == "event:"

    def test_a_metric_says_what_it_judges_in_words(self, metric_factory):
        data = self.get_sample_data()
        data["config"] = {
            "target": {"on": "tool_call", "name": "issue_refund", "within": "billing_agent"}
        }

        created = metric_factory.create(data)
        fetched = metric_factory.client.get(f"{self.endpoints.list}{created['id']}").json()
        listed = metric_factory.client.get(f"{self.endpoints.list}?limit=100").json()

        long = "each tool call named `issue_refund` inside `billing_agent`"
        for metric in (created, fetched, next(m for m in listed if m["id"] == created["id"])):
            assert metric["target_summary"] == long
            assert metric["target_summary_short"] == long

    def test_a_long_target_has_a_short_summary(self, metric_factory):
        data = self.get_sample_data()
        where = [
            {"field": "kind", "op": "==", "value": "tool.invoke"},
            {"field": "app.tier", "op": "==", "value": "gold"},
            {"field": "duration_ms", "op": ">", "value": 500},
        ]
        data["config"] = {"target": {"on": "span", "where": where}}

        metric = metric_factory.create(data)

        assert metric["target_summary"] == (
            "each tool call where `app.tier` is `gold` and `duration_ms` is over `500`"
        )
        assert metric["target_summary_short"] == (
            "each tool call where `app.tier` is `gold`, and 1 more condition"
        )

    def test_a_metric_without_a_target_is_summarised_by_its_default(self, metric_factory):
        metric = metric_factory.create(self.get_sample_data())

        assert metric["target_summary"] == "each turn"


@pytest.mark.unit
class TestTargetSummaries:
    """The summary never fails a response, whatever is stored."""

    def test_a_broken_stored_target_gives_no_summary(self):
        from rhesis.backend.app.schemas.metric import target_summaries

        broken = {"target": {"on": "tool_call", "where": [{"field": "x", "op": "~"}]}}

        assert target_summaries(broken, None) == (None, None)
        assert target_summaries({"target": {"on": "trajectory"}}, None) == (None, None)
        assert target_summaries({"target": "nonsense"}, None) == (None, None)

    def test_no_target_and_no_default_gives_no_summary(self):
        from rhesis.backend.app.schemas.metric import target_summaries

        assert target_summaries(None, None) == (None, None)

    def test_a_response_with_a_broken_stored_target_still_serialises(self):
        import uuid

        from rhesis.backend.app.schemas.metric import Metric

        metric = Metric(
            id=uuid.uuid4(),
            name="m",
            evaluation_prompt="p",
            score_type="numeric",
            config={"target": {"on": "trajectory"}},
        )

        assert metric.target_summary is None
        assert metric.target_summary_short is None


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
        """Generated metric is persisted and readable back (custom backend_type)."""
        mock_generate.return_value = dict(_NUMERIC_SYNTHESIZED)

        create_resp = metric_factory.client.post(
            self.endpoints.generate,
            json={"prompt": "accuracy metric"},
        )
        assert create_resp.status_code == status.HTTP_200_OK
        metric_id = create_resp.json()["id"]

        get_resp = metric_factory.client.get(self.endpoints.get(metric_id))
        assert get_resp.status_code == status.HTTP_200_OK
        assert get_resp.json()["id"] == metric_id

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


# === METRIC SETTINGS (config) ===


@pytest.mark.integration
class TestMetricConfig(MetricTestMixin):
    """Settings are checked against the metric's class on every write, and never on reads."""

    def _trajectory(self, metric_factory):
        data = {
            **MetricDataFactory.sample_data(),
            "class_name": "ToolCallTrajectory",
            "backend_type": "rhesis",
            "config": {"match": "superset"},
        }
        return metric_factory.create(data)

    def test_valid_settings_are_stored(self, metric_factory):
        metric = self._trajectory(metric_factory)

        assert metric["config"] == {"match": "superset", "target": {"on": "run"}}

    def test_an_update_without_class_name_is_checked_against_the_stored_class(self, metric_factory):
        metric = self._trajectory(metric_factory)

        response = metric_factory.client.put(
            self.endpoints.put(metric["id"]), json={"config": {"match": "sometimes"}}
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert metric_factory.client.get(self.endpoints.get(metric["id"])).status_code == 200

    def test_an_update_with_valid_settings_is_saved(self, metric_factory):
        metric = self._trajectory(metric_factory)

        response = metric_factory.client.put(
            self.endpoints.put(metric["id"]), json={"config": {"match": "exact"}}
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["config"] == {"match": "exact", "target": {"on": "run"}}

    def test_an_update_without_config_keeps_the_stored_one(self, metric_factory):
        metric = self._trajectory(metric_factory)

        response = metric_factory.client.put(
            self.endpoints.put(metric["id"]), json={"description": "Checks the refund flow."}
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["config"] == {"match": "superset", "target": {"on": "run"}}

    def test_a_target_the_stored_class_cannot_take_is_refused(self, metric_factory):
        metric = self._trajectory(metric_factory)

        response = metric_factory.client.put(
            self.endpoints.put(metric["id"]), json={"config": {"target": {"on": "tool_call"}}}
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "can't judge 'tool_call'" in response.json()["detail"]

    def test_a_target_is_saved_with_the_settings(self, metric_factory):
        metric = self._trajectory(metric_factory)
        config = {"match": "superset", "target": {"on": "run"}}

        response = metric_factory.client.put(
            self.endpoints.put(metric["id"]), json={"config": config}
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["config"] == config


class TestRuleMetrics(MetricTestMixin):
    """Rules are metrics with no model: their settings and target are checked on write."""

    def _rule(self, class_name: str, config: Dict[str, Any], **fields: Any) -> Dict[str, Any]:
        return {
            **MetricDataFactory.sample_data(),
            "class_name": class_name,
            "metric_type": "rule",
            "backend_type": "rhesis",
            "score_type": "numeric",
            "threshold": 1,
            "threshold_operator": ">=",
            "evaluation_prompt": "a readable rule",
            "config": config,
            **fields,
        }

    def _create(self, metric_factory, data):
        return metric_factory.client.post(self.endpoints.create, json=data)

    def test_a_field_rule_is_stored_as_a_rule_judging_each_turn(self, metric_factory):
        response = self._create(
            metric_factory,
            self._rule("FieldRule", {"field": "duration_ms", "op": "<=", "value": 5000}),
        )

        assert response.status_code == status.HTTP_200_OK, response.text
        created = response.json()
        assert created["metric_type"]["type_value"] == "rule"
        assert created["config"] == {
            "field": "duration_ms",
            "op": "<=",
            "value": 5000,
            "target": {"on": "turn"},
        }

    def test_a_field_rule_can_take_every_target(self, metric_factory):
        response = self._create(
            metric_factory,
            self._rule(
                "FieldRule",
                {"field": "error_count", "op": "==", "value": 0, "target": {"on": "tool_call"}},
            ),
        )

        assert response.status_code == status.HTTP_200_OK, response.text
        supported = set(response.json()["supported_targets"])
        assert {"turn", "conversation", "run", "tool_call", "retrieval"} <= supported

    @pytest.mark.parametrize(
        "config",
        [
            {"field": "duration_ms", "op": "about", "value": 5000},
            {"field": "mood", "op": "==", "value": "happy"},
            {"field": "duration_ms", "op": "<="},
            {"field": "duration_ms", "op": "<=", "value": 5000, "colour": "red"},
        ],
        ids=["unknown operator", "unknown field", "missing value", "unknown setting"],
    )
    def test_a_field_rule_with_bad_settings_is_refused(self, metric_factory, config):
        response = self._create(metric_factory, self._rule("FieldRule", config))

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_a_pattern_that_differs_in_postgres_is_refused_on_create(self, metric_factory):
        config = {"field": "output", "op": "matches", "value": r"\brefund\b"}

        response = self._create(metric_factory, self._rule("FieldRule", config))

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "word boundary" in response.text

    def test_a_pattern_that_differs_in_postgres_is_refused_on_update(self, metric_factory):
        config = {"field": "output", "op": "matches", "value": "refund"}
        created = self._create(metric_factory, self._rule("FieldRule", config)).json()

        response = metric_factory.client.put(
            self.endpoints.put(created["id"]),
            json={"config": {**config, "value": r"\brefund\b"}},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "word boundary" in response.text

    def test_a_response_rule_judges_turns_but_not_spans_or_the_conversation(self, metric_factory):
        response = self._create(
            metric_factory,
            self._rule("ResponseRule", {"match": "exact"}, ground_truth_required=True),
        )

        assert response.status_code == status.HTTP_200_OK, response.text
        created = response.json()
        assert created["config"]["target"] == {"on": "turn"}
        supported = set(created["supported_targets"])
        assert "turn" in supported
        assert not supported & {"conversation", "tool_call", "retrieval", "model_call"}

    def test_a_response_rule_cannot_take_a_span_target(self, metric_factory):
        response = self._create(
            metric_factory,
            self._rule("ResponseRule", {"match": "exact", "target": {"on": "tool_call"}}),
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_a_similar_response_rule_needs_a_minimum(self, metric_factory):
        response = self._create(metric_factory, self._rule("ResponseRule", {"match": "similar"}))

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_tool_call_trajectory_takes_what_it_took_before(self, metric_factory):
        response = self._create(
            metric_factory, self._rule("ToolCallTrajectory", {"match": "in_order"})
        )

        assert response.status_code == status.HTTP_200_OK, response.text
        created = response.json()
        assert created["config"]["target"] == {"on": "run"}
        assert "tool_call" not in created["supported_targets"]


TIER = "app.customer_tier"


def _condition(field: str, op: str, value: Any = None) -> Dict[str, Any]:
    return {"field": field, "op": op, "value": value}


def _span_target(*conditions: Dict[str, Any]) -> Dict[str, Any]:
    from rhesis.sdk.metrics.targets import TargetKind

    return {"target": {"on": TargetKind.SPAN.value, "where": list(conditions)}}


@pytest.fixture
def catalogue_calls(monkeypatch):
    """Counts the catalogue queries a metric write makes."""
    from rhesis.backend.app.services.telemetry import span_attributes

    calls = []
    real = span_attributes.get_attribute_catalogue

    def counting(*args, **kwargs):
        calls.append(args)
        return real(*args, **kwargs)

    monkeypatch.setattr(span_attributes, "get_attribute_catalogue", counting)
    return calls


@pytest.fixture
def tool_spans(authenticated_client, db_project):
    """Four recent tool spans in the project, two of them with a customer tier."""
    from datetime import datetime, timedelta, timezone

    from rhesis.telemetry import AIAttributes

    from .fixtures.data_factories import TraceDataFactory

    project_id = str(db_project.id)
    spans = []
    for i in range(4):
        span = TraceDataFactory.minimal_data(project_id=project_id)
        start = datetime.now(timezone.utc) - timedelta(minutes=i)
        attributes = {
            AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_TOOL_INVOKE,
            AIAttributes.TOOL_NAME: "issue_refund",
        }
        if i < 2:
            attributes[TIER] = "gold"
        span.update(
            attributes=attributes,
            start_time=start.isoformat(),
            end_time=(start + timedelta(seconds=1)).isoformat(),
        )
        spans.append(span)
    response = authenticated_client.post("/telemetry/traces", json={"spans": spans})
    assert response.status_code == status.HTTP_200_OK, response.text
    return project_id


@pytest.fixture
def in_project(test_db, test_org_id, authenticated_user_id, tool_spans, monkeypatch):
    """Requests run scoped to the project with the tool spans, so metrics are stamped with it.

    Route tests bypass the dependency that reads X-Project-Id; the request session copies
    its scope from ``test_db.info`` instead.
    """
    from rhesis.backend.app.scope import RequestScope

    scope = RequestScope(
        organization_id=str(test_org_id), user_id=str(authenticated_user_id), project_id=tool_spans
    )
    monkeypatch.setitem(test_db.info, "_scope", scope)
    return tool_spans


@pytest.mark.integration
class TestWhereKeyWarnings(MetricTestMixin):
    """A where key no recent span carries is saved with a warning, never refused."""

    def _create(self, client, config):
        data = {**MetricDataFactory.sample_data(), "config": config}
        response = client.post(self.endpoints.create, json=data)
        assert response.status_code == status.HTTP_200_OK, response.text
        return response.json()

    def test_an_unknown_key_is_warned_about_with_the_nearest_one(
        self, authenticated_client, in_project
    ):
        metric = self._create(
            authenticated_client, _span_target(_condition("app.tier", "==", "gold"))
        )

        assert metric["warnings"] == [
            f"No recent span carries app.tier; {TIER} is set on 50% of tool.invoke spans"
        ]
        assert metric["config"]["target"]["where"][0]["field"] == "app.tier"

    def test_an_unknown_key_with_nothing_near_it_is_named_alone(
        self, authenticated_client, in_project
    ):
        metric = self._create(authenticated_client, _span_target(_condition("zzz", "exists")))

        assert metric["warnings"] == ["No recent span carries zzz"]

    def test_a_known_key_gives_no_warning(self, authenticated_client, in_project):
        metric = self._create(authenticated_client, _span_target(_condition(TIER, "==", "gold")))

        assert metric["warnings"] == []

    def test_a_known_key_read_as_an_attribute_gives_no_warning(
        self, authenticated_client, in_project
    ):
        from rhesis.sdk.metrics.conditions import ATTRIBUTE_PREFIX

        target = _span_target(_condition(f"{ATTRIBUTE_PREFIX}{TIER}", "exists"))

        assert self._create(authenticated_client, target)["warnings"] == []

    def test_special_fields_are_not_checked(
        self, authenticated_client, in_project, catalogue_calls
    ):
        from rhesis.sdk.metrics.conditions import SpecialField

        target = _span_target(
            _condition(SpecialField.KIND.value, "==", "tool_call"),
            _condition(SpecialField.DURATION_MS.value, ">", 10),
            _condition(SpecialField.STATUS.value, "==", "ok"),
        )

        assert self._create(authenticated_client, target)["warnings"] == []
        assert catalogue_calls == []

    def test_a_target_without_attribute_conditions_reads_no_catalogue(
        self, authenticated_client, in_project, catalogue_calls
    ):
        config = {"target": {"on": "tool_call", "name": "issue_refund"}}

        assert self._create(authenticated_client, config)["warnings"] == []
        assert catalogue_calls == []

    def test_a_metric_without_a_project_is_not_checked(
        self, authenticated_client, tool_spans, catalogue_calls
    ):
        metric = self._create(authenticated_client, _span_target(_condition("app.tier", "exists")))

        assert metric["warnings"] == []
        assert catalogue_calls == []

    def test_one_catalogue_query_for_several_keys(
        self, authenticated_client, in_project, catalogue_calls
    ):
        target = _span_target(_condition("app.tier", "exists"), _condition("zzz", "exists"))

        metric = self._create(authenticated_client, target)

        assert len(metric["warnings"]) == 2
        assert len(catalogue_calls) == 1

    def test_an_update_is_warned_about_too(self, authenticated_client, in_project):
        metric = self._create(authenticated_client, _span_target(_condition(TIER, "exists")))

        response = authenticated_client.put(
            self.endpoints.put(metric["id"]),
            json={"config": _span_target(_condition("app.customer_teir", "exists"))},
        )

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["warnings"] == [
            f"No recent span carries app.customer_teir; {TIER} is set on 50% of tool.invoke spans"
        ]

    def test_an_update_without_a_config_is_not_checked(
        self, authenticated_client, in_project, catalogue_calls
    ):
        metric = self._create(authenticated_client, _span_target(_condition("app.tier", "exists")))
        catalogue_calls.clear()

        response = authenticated_client.put(
            self.endpoints.put(metric["id"]),
            json={"description": "Checks gold customers."},
        )

        assert response.json()["warnings"] == []
        assert catalogue_calls == []

    def test_an_invalid_target_reaches_mcp_with_the_message_intact(
        self, authenticated_client, in_project
    ):
        import json

        from rhesis.backend.app.mcp_server.server import format_error
        from rhesis.sdk.metrics.conditions import CONDITION_OPS

        metric = self._create(authenticated_client, _span_target(_condition(TIER, "exists")))
        response = authenticated_client.put(
            self.endpoints.put(metric["id"]),
            json={"config": _span_target(_condition(TIER, "~", "gold"))},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        detail = json.loads(format_error(response))["detail"]
        message = detail if isinstance(detail, str) else json.dumps(detail)
        assert "Invalid target:" in message
        assert ", ".join(op.value for op in CONDITION_OPS) in message


@pytest.mark.unit
class TestUnknownKeyWarnings:
    """The warning text, from a catalogue alone."""

    def _catalogue(self, kinds):
        from datetime import datetime, timezone

        from rhesis.backend.app.schemas.telemetry import (
            AttributeValueType,
            SpanAttributeCatalogue,
            SpanAttributeSummary,
            SpanKindAttributes,
        )

        return SpanAttributeCatalogue(
            kinds={
                kind: SpanKindAttributes(
                    spans=10,
                    attributes=[
                        SpanAttributeSummary(
                            key=key,
                            coverage=coverage,
                            type=AttributeValueType.STRING,
                            top_values=[],
                            distinct=1,
                            unique=False,
                        )
                        for key, coverage in keys.items()
                    ],
                )
                for kind, keys in kinds.items()
            },
            sampled_spans=10 * len(kinds),
            since=datetime.now(timezone.utc),
        )

    def test_the_suggestion_names_the_kind_that_carries_it_most(self):
        from rhesis.backend.app.services.telemetry.span_attributes import unknown_key_warnings

        catalogue = self._catalogue({"llm.invoke": {TIER: 0.1}, "tool.invoke": {TIER: 0.92}})

        assert unknown_key_warnings(["app.tier", TIER], catalogue) == [
            f"No recent span carries app.tier; {TIER} is set on 92% of tool.invoke spans"
        ]

    def test_an_empty_catalogue_warns_without_a_suggestion(self):
        from rhesis.backend.app.services.telemetry.span_attributes import unknown_key_warnings

        assert unknown_key_warnings(["app.tier"], self._catalogue({})) == [
            "No recent span carries app.tier"
        ]

    def test_only_attribute_keys_are_checked(self):
        from rhesis.backend.app.services.telemetry.span_attributes import where_attribute_keys
        from rhesis.sdk.metrics.conditions import ATTRIBUTE_PREFIX, SpecialField
        from rhesis.sdk.metrics.targets import Target

        target = Target.coerce(
            {
                "on": "tool_call",
                "where": [
                    _condition(SpecialField.NAME.value, "==", "x"),
                    _condition(f"{ATTRIBUTE_PREFIX}status", "exists"),
                    _condition(TIER, "exists"),
                    _condition(TIER, "!=", "free"),
                ],
            }
        )

        assert where_attribute_keys(target) == ["status", TIER]
