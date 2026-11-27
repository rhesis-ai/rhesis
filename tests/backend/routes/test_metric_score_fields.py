"""Metric routes apply the score-field rules to what they save."""

from unittest.mock import patch

import pytest
from fastapi import status

from .fixtures.data_factories import MetricDataFactory

NUMERIC = {"score_type": "numeric", "min_score": 0, "max_score": 10, "threshold": 5}


def _numeric_metric(metric_factory) -> dict:
    return metric_factory.create({**MetricDataFactory.sample_data(), **NUMERIC})


@pytest.mark.integration
class TestUpdateChecksTheStoredFields:
    def test_a_threshold_sent_alone_must_fit_the_stored_range(self, metric_factory):
        metric = _numeric_metric(metric_factory)

        response = metric_factory.client.put(f"/metrics/{metric['id']}", json={"threshold": 15})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "threshold must lie between" in response.json()["detail"]

    def test_a_threshold_inside_the_stored_range_saves(self, metric_factory):
        metric = _numeric_metric(metric_factory)

        response = metric_factory.client.put(f"/metrics/{metric['id']}", json={"threshold": 7})

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["threshold"] == 7

    def test_an_update_without_score_fields_is_not_checked(self, metric_factory):
        metric = _numeric_metric(metric_factory)

        response = metric_factory.client.put(
            f"/metrics/{metric['id']}", json={"description": "Clearer wording"}
        )

        assert response.status_code == status.HTTP_200_OK


@pytest.mark.integration
class TestGenerateRejection:
    @patch("rhesis.sdk.metrics.synthesizer.MetricSynthesizer.generate")
    def test_a_metric_the_model_got_wrong_twice_is_a_422_with_the_reason(
        self, mock_generate, metric_factory
    ):
        from rhesis.sdk.metrics.synthesizer import GeneratedMetricRejected

        mock_generate.side_effect = GeneratedMetricRejected("- metric: max_score required")

        response = metric_factory.client.post(
            "/metrics/generate", json={"prompt": "Fail on legal advice"}
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "max_score required" in response.json()["detail"]
