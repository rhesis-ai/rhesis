"""
🌳 Hierarchical Relationship Fixtures

Fixtures for creating parent-child hierarchical relationships.
"""

import pytest
from typing import Dict, Any
from fastapi import status
from fastapi.testclient import TestClient
from faker import Faker

from ...endpoints import APIEndpoints

fake = Faker()


@pytest.fixture
def topic_with_children(
    authenticated_client: TestClient, parent_topic: Dict[str, Any]
) -> Dict[str, Any]:
    """
    🌳📚 Create a topic with child topics

    This fixture creates a complete topic hierarchy for integration testing.

    Returns:
        Dict containing:
        - parent: The parent topic data
        - children: List of child topic data associated with the parent
    """
    children = []

    # Create 3 child topics associated with the parent
    for i in range(3):
        child_data = {
            "name": f"Child Topic {i + 1} of {parent_topic['name']}",
            "description": fake.text(max_nb_chars=100),
            "parent_id": parent_topic["id"],
        }

        response = authenticated_client.post(APIEndpoints.TOPICS.create, json=child_data)
        assert response.status_code == status.HTTP_200_OK
        children.append(response.json())

    return {"parent": parent_topic, "children": children}
