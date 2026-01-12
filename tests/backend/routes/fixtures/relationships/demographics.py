"""
🏗️📊 Demographic Relationship Fixtures

Fixtures for creating dimension-demographic relationships.
"""

from typing import Any, Dict

import pytest
from faker import Faker
from fastapi import status
from fastapi.testclient import TestClient

from ...endpoints import APIEndpoints

fake = Faker()


@pytest.fixture
def dimension_with_demographics(
    authenticated_client: TestClient, sample_dimension: Dict[str, Any]
) -> Dict[str, Any]:
    """
    🏗️📊 Create a dimension with associated demographics

    This fixture creates a complete dimension-demographic relationship
    for integration testing.

    Returns:
        Dict containing:
        - dimension: The dimension data
        - demographics: List of demographic data associated with the dimension
    """
    demographics = []

    # Create 3 demographics associated with the dimension
    for i in range(3):
        demographic_data = {
            "name": f"Demographic {i + 1} for {sample_dimension['name']}",
            "description": fake.text(max_nb_chars=100),
            "dimension_id": sample_dimension["id"],
        }

        response = authenticated_client.post(
            APIEndpoints.DEMOGRAPHICS.create, json=demographic_data
        )
        assert response.status_code == status.HTTP_200_OK
        demographics.append(response.json())

    return {"dimension": sample_dimension, "demographics": demographics}
