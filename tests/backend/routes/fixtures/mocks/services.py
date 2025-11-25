"""
🎭 Service Mock Fixtures

Mock fixtures for internal services and business logic components.
"""

import pytest
from unittest.mock import Mock
from faker import Faker

fake = Faker()


@pytest.fixture
def mock_endpoint_service():
    """
    🎭 Create a mock endpoint service for testing

    This fixture provides a mock endpoint service that can be used
    to test endpoint invocation without making real API calls.
    """
    mock_service = Mock()
    mock_service.invoke_endpoint.return_value = {
        "result": "Mock response from endpoint",
        "timestamp": fake.iso8601(),
        "success": True,
    }
    mock_service.get_schema.return_value = {
        "input": {
            "type": "object",
            "properties": {"input": {"type": "string"}, "session_id": {"type": "string"}},
            "required": ["input"],
        },
        "output": {"type": "object", "properties": {"result": {"type": "string"}}},
    }

    return mock_service
