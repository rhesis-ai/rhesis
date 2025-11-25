"""
Metric Fixtures

Fixtures for creating metric entities.
"""

import pytest
import uuid
from typing import Dict, Any
from fastapi import status
from fastapi.testclient import TestClient
from faker import Faker

from ...endpoints import APIEndpoints

fake = Faker()


@pytest.fixture
def sample_metric(authenticated_client: TestClient) -> Dict[str, Any]:
    """
    Create a sample metric for testing

    This fixture creates a metric that can be used in behavior-metric
    relationship tests or any other tests that need a valid metric.

    Returns:
        Dict containing the created metric data including its ID
    """
    score_type = fake.random_element(elements=("numeric", "categorical"))
    metric_data = {
        "name": fake.word().title() + " " + fake.word().title(),
        "description": fake.text(max_nb_chars=150),
        "evaluation_prompt": fake.sentence(nb_words=8),
        "score_type": score_type,
    }

    # Add required fields for categorical metrics
    if score_type == "categorical":
        metric_data["categories"] = ["pass", "fail", "partial"]
        metric_data["passing_categories"] = ["pass"]

    response = authenticated_client.post(APIEndpoints.METRICS.create, json=metric_data)
    if response.status_code not in [status.HTTP_200_OK, status.HTTP_201_CREATED]:
        # If metrics endpoint doesn't exist or fails, create a mock metric ID
        return {"id": str(uuid.uuid4())}
    return response.json()
