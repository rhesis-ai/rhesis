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


def _post_model(client, provider, model_name, model_type=None):
    body = {
        "name": f"{provider} {uuid.uuid4().hex[:8]}",
        "model_name": model_name,
        "key": fake.uuid4(),
        "provider_type_id": find_or_create_type_lookup_id(client, "ProviderType", provider),
    }
    if model_type:
        body["model_type"] = model_type
    return client.post(APIEndpoints.MODELS.create, json=body)


def _create_model(client, provider, model_name, model_type=None):
    response = _post_model(client, provider, model_name, model_type)
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()["id"]


@pytest.fixture
def jev_model_id(authenticated_client):
    return _create_model(authenticated_client, "jev", "jev-latest", "decision")


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
    def test_is_saved_as_a_decision_model_without_being_told(self, authenticated_client):
        response = _post_model(authenticated_client, "jev", "jev-latest")
        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["model_type"] == "decision"

    def test_cannot_be_saved_as_a_language_model(self, authenticated_client):
        response = _post_model(authenticated_client, "jev", "jev-latest", "language")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "has no language models" in response.json()["detail"]

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

    @pytest.mark.parametrize("purpose", ["generation", "evaluation", "execution"])
    def test_an_embedding_model_is_no_default_for_any_purpose(self, authenticated_client, purpose):
        embedder_id = _create_model(
            authenticated_client, "openai", "text-embedding-3-small", "embedding"
        )
        response = authenticated_client.patch(
            SETTINGS, json={"models": {purpose: {"model_id": embedder_id}}}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert f"embedding model, which can't be used for {purpose}" in response.json()["detail"]

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
