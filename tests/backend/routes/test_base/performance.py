"""
🐌 Performance Tests

This module provides performance tests for entity operations including
large pagination.
"""

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from .core import BaseEntityTests


@pytest.mark.slow
@pytest.mark.integration
class BasePerformanceTests(BaseEntityTests):
    """Base class for performance tests"""
    
    def test_list_entities_with_large_pagination(self, authenticated_client: TestClient):
        """🐌 Test listing entities with large pagination parameters"""
        response = authenticated_client.get(f"{self.endpoints.list}?limit=100&skip=0")
        
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) <= 100
