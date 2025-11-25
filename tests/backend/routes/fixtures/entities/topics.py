"""
📚 Topic Fixtures

Fixtures for creating topic entities including hierarchical relationships.
"""

import pytest
from typing import Dict, Any
from fastapi import status
from fastapi.testclient import TestClient
from faker import Faker

from ...endpoints import APIEndpoints

fake = Faker()


@pytest.fixture
def sample_topic(authenticated_client: TestClient) -> Dict[str, Any]:
    """
    📚 Create a sample topic for testing

    Useful for tests that need a valid topic reference.
    """
    topic_data = {
        "name": fake.word().title() + " Test Topic",
        "description": fake.text(max_nb_chars=100),
    }

    response = authenticated_client.post(APIEndpoints.TOPICS.create, json=topic_data)
    assert response.status_code == status.HTTP_200_OK

    return response.json()


@pytest.fixture
def parent_topic(authenticated_client: TestClient) -> Dict[str, Any]:
    """
    🌳 Create a parent topic for hierarchical testing

    This fixture creates a topic that can be used as a parent
    in hierarchical topic tests.

    Returns:
        Dict containing the created parent topic data including its ID
    """
    parent_data = {
        "name": fake.sentence(nb_words=2).rstrip(".") + " Parent Topic",
        "description": fake.text(max_nb_chars=100),
    }

    response = authenticated_client.post(APIEndpoints.TOPICS.create, json=parent_data)
    assert response.status_code == status.HTTP_200_OK

    return response.json()
