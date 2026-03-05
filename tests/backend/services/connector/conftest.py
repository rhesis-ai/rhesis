"""Fixtures for connector service tests."""

from typing import Any, Dict
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import WebSocket

from rhesis.backend.app.services.connector.schemas import (
    WebSocketConnectionContext,
)


@pytest.fixture(autouse=True)
def mock_redis():
    """Disable Redis for all connector tests."""
    with patch("rhesis.backend.app.services.connector.manager.redis_manager") as mock:
        mock.is_available = False
        yield mock


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket connection."""
    ws = Mock(spec=WebSocket)
    ws.send_json = AsyncMock()
    ws.receive_text = AsyncMock()
    ws.accept = AsyncMock()
    ws.close = AsyncMock()
    return ws


@pytest.fixture
def connection_context():
    """Create a WebSocketConnectionContext for testing."""
    return WebSocketConnectionContext(
        connection_id="conn-test-123",
        user_id="user-789",
        organization_id="org-456",
    )


@pytest.fixture
def sample_register_message() -> Dict[str, Any]:
    """Sample registration message from SDK."""
    return {
        "type": "register",
        "project_id": "test-project",
        "environment": "development",
        "sdk_version": "1.0.0",
        "functions": [
            {
                "name": "get_weather",
                "parameters": {
                    "location": {
                        "type": "string",
                        "description": "City name",
                    }
                },
                "return_type": "object",
                "metadata": {"description": "Get current weather for a location"},
            },
            {
                "name": "calculate_sum",
                "parameters": {
                    "a": {"type": "number"},
                    "b": {"type": "number"},
                },
                "return_type": "number",
                "metadata": {"description": "Calculate sum of two numbers"},
            },
        ],
    }


@pytest.fixture
def sample_test_result_message() -> Dict[str, Any]:
    """Sample test result message from SDK."""
    return {
        "type": "test_result",
        "test_run_id": "test_abc123",
        "status": "success",
        "output": {"temperature": 72, "conditions": "sunny"},
        "error": None,
        "duration_ms": 123.45,
    }


@pytest.fixture
def sample_test_result_error_message() -> Dict[str, Any]:
    """Sample test result error message from SDK."""
    return {
        "type": "test_result",
        "test_run_id": "test_xyz789",
        "status": "error",
        "output": None,
        "error": "Connection timeout",
        "duration_ms": 5000.0,
    }


@pytest.fixture
def sample_pong_message() -> Dict[str, Any]:
    """Sample pong message from SDK."""
    return {"type": "pong"}


@pytest.fixture
def project_context():
    """Sample project context for SDK connections."""
    return {
        "project_id": "test-project-123",
        "environment": "development",
        "organization_id": "org-456",
        "user_id": "user-789",
    }
