"""
Dependency injection functions for FastAPI.
"""
from functools import lru_cache
from typing import Optional

from fastapi import Depends

from rhesis.backend.app.services.endpoint import EndpointService


@lru_cache()
def get_endpoint_service() -> EndpointService:
    """
    Get or create an EndpointService instance.
    Uses lru_cache to maintain a single instance per process while still allowing
    for proper dependency injection and testing.
    
    Returns:
        EndpointService: The endpoint service instance
    """
    return EndpointService() 