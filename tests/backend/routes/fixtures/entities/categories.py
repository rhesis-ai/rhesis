"""
Category Fixtures

Fixtures for creating category entities including hierarchical relationships.
"""

import pytest
from typing import Dict, Any
from fastapi import status
from fastapi.testclient import TestClient
from faker import Faker

from ...endpoints import APIEndpoints

fake = Faker()


@pytest.fixture
def sample_category(authenticated_client: TestClient) -> Dict[str, Any]:
    """
    Create a sample category for testing

    Useful for tests that need a valid category reference.
    """
    category_data = {
        "name": fake.word().title() + " Test Category",
        "description": fake.text(max_nb_chars=100),
    }

    response = authenticated_client.post(APIEndpoints.CATEGORIES.create, json=category_data)
    assert response.status_code == status.HTTP_200_OK

    return response.json()


@pytest.fixture
def parent_category(authenticated_client: TestClient) -> Dict[str, Any]:
    """
    Create a parent category for hierarchical testing

    This fixture creates a category that can be used as a parent
    in hierarchical category tests.

    Returns:
        Dict containing the created parent category data including its ID
    """
    parent_data = {
        "name": fake.sentence(nb_words=2).rstrip(".") + " Parent Category",
        "description": fake.text(max_nb_chars=100),
    }

    response = authenticated_client.post(APIEndpoints.CATEGORIES.create, json=parent_data)
    assert response.status_code == status.HTTP_200_OK

    return response.json()
