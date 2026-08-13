"""
Requirement Fixtures

Fixtures for creating requirement entities.
"""

from typing import Any, Dict

import pytest
from faker import Faker
from fastapi import status
from fastapi.testclient import TestClient

from ...endpoints import APIEndpoints

fake = Faker()


@pytest.fixture
def sample_requirement(authenticated_client: TestClient) -> Dict[str, Any]:
    """
    Create a sample requirement for testing

    Useful for tests that need a valid requirement reference.
    """
    requirement_data = {
        "name": fake.word().title() + " Test Requirement",
        "description": fake.text(max_nb_chars=100),
    }

    response = authenticated_client.post(APIEndpoints.REQUIREMENTS.create, json=requirement_data)
    assert response.status_code == status.HTTP_200_OK

    return response.json()
