"""
✅ Health Check Tests

This module provides basic health check tests to ensure entity routes
are accessible and returning expected response formats.
"""

from fastapi import status
from fastapi.testclient import TestClient

from .core import BaseEntityTests


class BaseHealthTests(BaseEntityTests):
    """Base class for basic health tests"""

    def test_entity_routes_basic_health(self, authenticated_client: TestClient):
        """✅ Basic health check for entity routes"""
        # Test that the entity endpoint is accessible
        response = authenticated_client.get(self.endpoints.list)

        # Should return 200 (even if empty list)
        assert response.status_code == status.HTTP_200_OK

        # Should return a list
        data = response.json()
        assert isinstance(data, list)
