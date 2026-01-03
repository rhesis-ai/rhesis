"""Fixtures for invoker tests."""

from datetime import datetime, timedelta
from unittest.mock import Mock
from uuid import UUID

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.app.models.enums import EndpointAuthType, EndpointConnectionType

# Default test project ID for fixtures
TEST_PROJECT_ID = UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture
def mock_db():
    """Mock database session."""
    return Mock(spec=Session)


@pytest.fixture
def sample_endpoint_rest():
    """Sample REST endpoint configuration."""
    return Endpoint(
        id="test-rest-endpoint",
        name="Test REST Endpoint",
        connection_type=EndpointConnectionType.REST.value,
        method="POST",
        url="https://api.example.com/chat",
        auth_type=EndpointAuthType.BEARER_TOKEN.value,
        auth_token="test-bearer-token",
        request_headers={"Content-Type": "application/json"},
        request_mapping='{"message": "{{ input }}"}',
        response_mapping={
            "output": "$.response.text",
            "tokens": "$.usage.total_tokens",
        },
        project_id=TEST_PROJECT_ID,
    )


@pytest.fixture
def sample_endpoint_websocket():
    """Sample WebSocket endpoint configuration."""
    return Endpoint(
        id="test-ws-endpoint",
        name="Test WebSocket Endpoint",
        connection_type=EndpointConnectionType.WEBSOCKET.value,
        url="wss://ws.example.com/chat",
        auth_type=EndpointAuthType.BEARER_TOKEN.value,
        auth_token="test-ws-token",
        request_mapping='{"query": "{{ input }}", "auth_token": "{{ auth_token }}"}',
        response_mapping={
            "output": "$.message",
            "conversation_id": "$.conversation_id",
        },
        project_id=TEST_PROJECT_ID,
    )


@pytest.fixture
def sample_endpoint_oauth():
    """Sample endpoint with OAuth client credentials."""
    endpoint = Endpoint(
        id="test-oauth-endpoint",
        name="Test OAuth Endpoint",
        connection_type=EndpointConnectionType.REST.value,
        method="POST",
        url="https://api.example.com/endpoint",
        auth_type=EndpointAuthType.CLIENT_CREDENTIALS.value,
        token_url="https://auth.example.com/oauth/token",
        client_id="test-client-id",
        client_secret="test-client-secret",
        audience="https://api.example.com",
        request_mapping='{"query": "{{ input }}"}',
        response_mapping={"output": "$.result"},
        project_id=TEST_PROJECT_ID,
    )
    # Set cached token
    endpoint.last_token = "cached-access-token"
    endpoint.last_token_expires_at = datetime.utcnow() + timedelta(hours=1)
    return endpoint


@pytest.fixture
def sample_endpoint_conversation():
    """Sample endpoint with conversation tracking."""
    return Endpoint(
        id="test-conv-endpoint",
        name="Test Conversation Endpoint",
        connection_type=EndpointConnectionType.REST.value,
        method="POST",
        url="https://api.example.com/chat",
        auth_type=EndpointAuthType.BEARER_TOKEN.value,
        auth_token="test-token",
        request_mapping=(
            '{"message": "{{ input }}", "conversation_id": {{ conversation_id | tojson }}}'
        ),
        response_mapping={
            "output": "$.message",
            "conversation_id": "$.conversation_id",
            "context": "$.context",
        },
        project_id=TEST_PROJECT_ID,
    )


@pytest.fixture
def sample_endpoint_sdk():
    """Sample SDK endpoint configuration."""
    return Endpoint(
        id="test-sdk-endpoint",
        name="Test SDK Endpoint",
        connection_type=EndpointConnectionType.SDK.value,
        url="",  # Empty for SDK endpoints
        environment="development",
        request_mapping='{"input": "{{ input }}"}',
        response_mapping={
            "output": "$.output",
            "status": "$.status",
        },
        endpoint_metadata={
            "sdk_connection": {
                "project_id": "test-project-id",
                "environment": "development",
                "function_name": "test_function",
            }
        },
        project_id=TEST_PROJECT_ID,
    )


@pytest.fixture
def sample_input_data():
    """Sample input data for invoker tests."""
    return {"input": "What is the capital of France?"}


@pytest.fixture
def sample_response_data():
    """Sample API response data."""
    return {
        "response": {"text": "Paris is the capital of France."},
        "usage": {"total_tokens": 42},
        "conversation_id": "conv-123",
        "context": "geography_query",
    }
