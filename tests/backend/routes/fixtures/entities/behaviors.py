"""
Behavior Fixtures

Fixtures for creating behavior entities.
"""

from typing import Any, Dict

import pytest
from faker import Faker
from fastapi import status
from fastapi.testclient import TestClient

from ...endpoints import APIEndpoints

fake = Faker()


@pytest.fixture
def sample_behavior(authenticated_client: TestClient) -> Dict[str, Any]:
    """
    Create a sample behavior for testing

    Useful for tests that need a valid behavior reference.
    """
    behavior_data = {
        "name": fake.word().title() + " Test Behavior",
        "description": fake.text(max_nb_chars=100),
    }

    response = authenticated_client.post(APIEndpoints.BEHAVIORS.create, json=behavior_data)
    assert response.status_code == status.HTTP_200_OK

    return response.json()
