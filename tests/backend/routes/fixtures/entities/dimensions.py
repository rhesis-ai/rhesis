"""
🏗️ Dimension Fixtures

Fixtures for creating dimension entities and collections.
"""

from typing import Any, Dict

import pytest
from faker import Faker
from fastapi import status
from fastapi.testclient import TestClient

from ...endpoints import APIEndpoints

fake = Faker()


@pytest.fixture
def sample_dimension(authenticated_client: TestClient) -> Dict[str, Any]:
    """
    🏗️ Create a sample dimension for testing

    This fixture creates a dimension that can be used as a foreign key
    in demographic tests or any other tests that need a valid dimension.

    Returns:
        Dict containing the created dimension data including its ID
    """
    dimension_data = {
        "name": fake.word().title() + " Test Dimension",
        "description": fake.text(max_nb_chars=100),
    }

    response = authenticated_client.post(APIEndpoints.DIMENSIONS.create, json=dimension_data)
    assert response.status_code == status.HTTP_200_OK

    return response.json()


@pytest.fixture
def sample_dimensions(authenticated_client: TestClient) -> list[Dict[str, Any]]:
    """
    🏗️ Create multiple sample dimensions for testing

    Useful for tests that need multiple dimensions or bulk operations.

    Returns:
        List of created dimension dictionaries
    """
    dimensions = []
    for i in range(3):
        dimension_data = {
            "name": f"{fake.word().title()} Dimension {i + 1}",
            "description": fake.text(max_nb_chars=100),
        }

        response = authenticated_client.post(APIEndpoints.DIMENSIONS.create, json=dimension_data)
        assert response.status_code == status.HTTP_200_OK
        dimensions.append(response.json())

    return dimensions
