"""
Authentication Tests

This module provides tests to ensure that entity routes properly require authentication
and handle unauthorized access correctly.
"""

import uuid

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from .core import BaseEntityTests


@pytest.mark.unit
@pytest.mark.critical
class BaseAuthenticationTests(BaseEntityTests):
    """Base class for authentication tests"""

    def test_entity_routes_require_authentication(self, client: TestClient):
        """Test that entity routes require authentication"""
        sample_data = self.get_sample_data()

        # Test POST
        response = client.post(self.endpoints.create, json=sample_data)
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

        # Test GET list
        response = client.get(self.endpoints.list)
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

        # Test GET by ID
        test_id = str(uuid.uuid4())
        response = client.get(self.endpoints.get(test_id))
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
