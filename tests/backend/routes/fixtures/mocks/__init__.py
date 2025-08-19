"""
🎭 Mock Fixtures Package

This package provides mock fixtures for external services and dependencies.

Modules:
- services.py: Internal service mocks
- external_apis.py: Third-party API mocks
- infrastructure.py: Infrastructure component mocks
"""

from .services import *

__all__ = [
    # Service mocks
    "mock_endpoint_service"
]
