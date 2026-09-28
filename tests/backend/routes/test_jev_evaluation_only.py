"""Jev is a decision model: it may be saved as the evaluation default and on
categorical metrics, and nowhere else."""

import uuid

import pytest
from faker import Faker
from fastapi import status

from .endpoints import APIEndpoints
from .fixtures.data_factories import MetricDataFactory, find_or_create_type_lookup_id

fake = Faker()

SETTINGS = "/users/settings"


@pytest.fixture
def jev_model_id(authenticated_client):
    response = authenticated_client.post(
        APIEndpoints.MODELS.create,
        json={
            "name": f"Jev {uuid.uuid4().hex[:8]}",
            "model_name": "jev-latest",
            "model_type": "decision",
            "key": fake.uuid4(),
            "provider_type_id": find_or_create_type_lookup_id(
                authenticated_client, "ProviderType", "jev"
            ),
        },
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()["id"]


def _metric(score_type, model_id):
    return MetricDataFactory._add_required_fields(
        {
            "name": f"Metric {uuid.uuid4().hex[:8]}",
            "evaluation_prompt": "Is the reply polite?",
            "score_type": score_type,
            "model_id": model_id,
        }
    )


@pytest.mark.integration
class TestJevEvaluationOnly:
    @pytest.mark.parametrize("purpose", ["generation", "execution"])
    def test_cannot_be_the_default_for_other_purposes(
        self, authenticated_client, jev_model_id, purpose
    ):
        response = authenticated_client.patch(
            SETTINGS, json={"models": {purpose: {"model_id": jev_model_id}}}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert f"can't be used for {purpose}" in response.json()["detail"]

    def test_can_be_the_evaluation_default(self, authenticated_client, jev_model_id):
        response = authenticated_client.patch(
            SETTINGS, json={"models": {"evaluation": {"model_id": jev_model_id}}}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["models"]["evaluation"]["model_id"] == jev_model_id

    def test_cannot_judge_a_numeric_metric(self, authenticated_client, jev_model_id):
        response = authenticated_client.post(
            APIEndpoints.METRICS.create, json=_metric("numeric", jev_model_id)
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "only judge categorical metrics" in response.json()["detail"]

    def test_can_judge_a_categorical_metric(self, authenticated_client, jev_model_id):
        response = authenticated_client.post(
            APIEndpoints.METRICS.create, json=_metric("categorical", jev_model_id)
        )
        assert response.status_code == status.HTTP_200_OK, response.text

    def test_a_categorical_metric_on_jev_cannot_become_numeric(
        self, authenticated_client, jev_model_id
    ):
        created = authenticated_client.post(
            APIEndpoints.METRICS.create, json=_metric("categorical", jev_model_id)
        ).json()
        response = authenticated_client.put(
            APIEndpoints.METRICS.put(created["id"]),
            json={"score_type": "numeric", "min_score": 0, "max_score": 10, "threshold": 5},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
