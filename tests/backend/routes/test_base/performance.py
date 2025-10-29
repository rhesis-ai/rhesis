"""
🐌 Performance Tests

This module provides performance tests for entity operations including
bulk creation, large pagination, and timing validation.
"""

import time

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from .core import BaseEntityTests


@pytest.mark.slow
@pytest.mark.integration
class BasePerformanceTests(BaseEntityTests):
    """Base class for performance tests"""
    
    def test_create_multiple_entities_performance(self, authenticated_client: TestClient):
        """🐌 Test creating multiple entities for performance"""
        start_time = time.time()
        
        # Create 10 entities
        created_entities = self.create_multiple_entities(authenticated_client, 10)
        
        duration = time.time() - start_time
        
        # Should complete within reasonable time (20 seconds for 10 creates)
        # Increased from 10s to 20s to account for slower CI environments
        assert duration < 20.0, f"Creating 10 entities took {duration:.2f}s (expected < 20s)"
        assert len(created_entities) == 10
        
        # Clean up - delete created entities
        for entity in created_entities:
            authenticated_client.delete(self.endpoints.remove(entity[self.id_field]))

    def test_list_entities_with_large_pagination(self, authenticated_client: TestClient):
        """🐌 Test listing entities with large pagination parameters"""
        response = authenticated_client.get(f"{self.endpoints.list}?limit=100&skip=0")
        
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) <= 100
