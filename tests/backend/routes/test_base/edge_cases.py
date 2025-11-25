"""
🏃‍♂️ Edge Case Tests

This module provides tests for edge cases including special characters,
very long names, null values, and other boundary conditions.
"""

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from .core import BaseEntityTests


@pytest.mark.unit
class BaseEdgeCaseTests(BaseEntityTests):
    """Base class for edge case tests"""

    def test_entity_with_very_long_name(self, authenticated_client: TestClient):
        """🏃‍♂️ Test entity creation with very long name"""
        long_data = self.get_long_name_data()

        response = authenticated_client.post(self.endpoints.create, json=long_data)

        # Should either succeed or return validation error
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            status.HTTP_400_BAD_REQUEST,
        ]

    def test_entity_with_special_characters(self, authenticated_client: TestClient):
        """🏃‍♂️ Test entity creation with special characters"""
        special_data = self.get_special_chars_data()

        response = authenticated_client.post(self.endpoints.create, json=special_data)

        # Should handle special characters gracefully
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_422_UNPROCESSABLE_ENTITY]

    def test_entity_with_null_description(self, authenticated_client: TestClient):
        """🏃‍♂️ Test entity creation with explicit null description"""
        null_data = self.get_null_description_data()

        response = authenticated_client.post(self.endpoints.create, json=null_data)

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data[self.description_field] is None
