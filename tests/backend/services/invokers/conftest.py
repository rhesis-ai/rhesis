"""Fixtures for invoker tests."""

from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.app.models.enums import EndpointAuthType, EndpointProtocol


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
        protocol=EndpointProtocol.REST.value,
        method="POST",
        url="https://api.example.com/chat",
        auth_type=EndpointAuthType.BEARER_TOKEN.value,
        auth_token="test-bearer-token",
        request_headers={"Content-Type": "application/json"},
        request_body_template='{"message": "{{ input }}"}',
        response_mappings={
            "output": "$.response.text",
            "tokens": "$.usage.total_tokens",
        },
    )


@pytest.fixture
def sample_endpoint_websocket():
    """Sample WebSocket endpoint configuration."""
    return Endpoint(
        id="test-ws-endpoint",
        name="Test WebSocket Endpoint",
        protocol=EndpointProtocol.WEBSOCKET.value,
        url="wss://ws.example.com/chat",
        auth_type=EndpointAuthType.BEARER_TOKEN.value,
        auth_token="test-ws-token",
        request_body_template='{"query": "{{ input }}", "auth_token": "{{ auth_token }}"}',
        response_mappings={
            "output": "$.message",
            "conversation_id": "$.conversation_id",
        },
    )


@pytest.fixture
def sample_endpoint_oauth():
    """Sample endpoint with OAuth client credentials."""
    endpoint = Endpoint(
        id="test-oauth-endpoint",
        name="Test OAuth Endpoint",
        protocol=EndpointProtocol.REST.value,
        method="POST",
        url="https://api.example.com/endpoint",
        auth_type=EndpointAuthType.CLIENT_CREDENTIALS.value,
        token_url="https://auth.example.com/oauth/token",
        client_id="test-client-id",
        client_secret="test-client-secret",
        audience="https://api.example.com",
        request_body_template='{"query": "{{ input }}"}',
        response_mappings={"output": "$.result"},
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
        protocol=EndpointProtocol.REST.value,
        method="POST",
        url="https://api.example.com/chat",
        auth_type=EndpointAuthType.BEARER_TOKEN.value,
        auth_token="test-token",
        request_body_template='{"message": "{{ input }}", "conversation_id": {{ conversation_id | tojson }}}',
        response_mappings={
            "output": "$.message",
            "conversation_id": "$.conversation_id",
            "context": "$.context",
        },
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
