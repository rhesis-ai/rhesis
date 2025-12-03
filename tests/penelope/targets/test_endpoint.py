"""Tests for EndpointTarget."""

from unittest.mock import Mock, patch

import pytest

from rhesis.penelope.targets.base import TargetResponse
from rhesis.penelope.targets.endpoint import EndpointTarget


@pytest.fixture
def mock_endpoint():
    """Create a mock Endpoint instance."""
    endpoint = Mock()
    endpoint.id = "endpoint-123"
    endpoint.name = "Test Endpoint"
    endpoint.url = "https://test.example.com/chat"
    endpoint.description = "Test endpoint description"
    endpoint.connection_type = "REST"
    endpoint.fields = {
        "name": "Test Endpoint",
        "url": "https://test.example.com/chat",
        "description": "Test endpoint description",
        "connection_type": "REST",
    }
    endpoint.invoke.return_value = {
        "output": "Test response",
        "conversation_id": "conv-123",
        "metadata": {"test": "metadata"},
    }
    return endpoint


def test_endpoint_target_initialization_with_endpoint(mock_endpoint):
    """Test EndpointTarget initialization with endpoint instance."""
    target = EndpointTarget(endpoint=mock_endpoint)

    assert target.endpoint == mock_endpoint
    assert target.endpoint_id == "endpoint-123"
    assert target.target_type == "endpoint"
    assert target.target_id == "endpoint-123"


def test_endpoint_target_initialization_requires_parameter():
    """Test EndpointTarget requires either endpoint_id or endpoint."""
    with pytest.raises(ValueError, match="Must provide either endpoint_id or endpoint"):
        EndpointTarget()


def test_endpoint_target_initialization_rejects_both_parameters(mock_endpoint):
    """Test EndpointTarget rejects both endpoint_id and endpoint."""
    with pytest.raises(ValueError, match="Provide only endpoint_id OR endpoint, not both"):
        EndpointTarget(endpoint_id="endpoint-123", endpoint=mock_endpoint)


@patch("rhesis.penelope.targets.endpoint.Endpoint")
def test_endpoint_target_initialization_with_endpoint_id(mock_endpoint_class):
    """Test EndpointTarget initialization with endpoint_id."""
    mock_endpoint = Mock()
    mock_endpoint.id = "endpoint-123"
    mock_endpoint.fields = {"name": "Test", "url": "https://test.com"}
    mock_endpoint.pull.return_value = None  # pull() doesn't return anything
    mock_endpoint_class.return_value = mock_endpoint

    target = EndpointTarget(endpoint_id="endpoint-123")

    mock_endpoint_class.assert_called_once_with(id="endpoint-123")
    mock_endpoint.pull.assert_called_once()
    assert target.endpoint_id == "endpoint-123"
    assert target.endpoint == mock_endpoint


@patch("rhesis.penelope.targets.endpoint.Endpoint")
def test_endpoint_target_initialization_with_invalid_id(mock_endpoint_class):
    """Test EndpointTarget raises error for invalid endpoint_id."""
    mock_endpoint = Mock()
    mock_endpoint.pull.side_effect = Exception("Endpoint not found")
    mock_endpoint_class.return_value = mock_endpoint

    with pytest.raises(ValueError, match="Endpoint not found or failed to load"):
        EndpointTarget(endpoint_id="invalid-id")


def test_endpoint_target_description(mock_endpoint):
    """Test EndpointTarget description property."""
    target = EndpointTarget(endpoint=mock_endpoint)

    description = target.description
    assert "Test Endpoint" in description
    assert "https://test.example.com/chat" in description


def test_endpoint_target_validate_configuration(mock_endpoint):
    """Test EndpointTarget validate_configuration."""
    target = EndpointTarget(endpoint=mock_endpoint)

    is_valid, error = target.validate_configuration()
    assert is_valid is True
    assert error is None


def test_endpoint_target_validate_configuration_missing_id():
    """Test EndpointTarget validation fails without endpoint id."""
    mock_endpoint = Mock()
    mock_endpoint.id = None
    mock_endpoint.fields = {}

    with pytest.raises(ValueError, match="Invalid endpoint configuration"):
        EndpointTarget(endpoint=mock_endpoint)


def test_endpoint_target_send_message(mock_endpoint):
    """Test EndpointTarget send_message."""
    target = EndpointTarget(endpoint=mock_endpoint)

    response = target.send_message("Hello")

    mock_endpoint.invoke.assert_called_once_with(input="Hello", session_id=None)
    assert isinstance(response, TargetResponse)
    assert response.success is True
    assert response.content == "Test response"
    assert response.conversation_id == "conv-123"


def test_endpoint_target_send_message_with_session(mock_endpoint):
    """Test EndpointTarget send_message with conversation_id."""
    target = EndpointTarget(endpoint=mock_endpoint)

    response = target.send_message("Hello", conversation_id="my-conv")

    mock_endpoint.invoke.assert_called_once_with(input="Hello", session_id="my-conv")
    assert response.success is True


def test_endpoint_target_send_message_empty_message(mock_endpoint):
    """Test EndpointTarget send_message with empty message."""
    target = EndpointTarget(endpoint=mock_endpoint)

    response = target.send_message("")

    assert response.success is False
    assert "cannot be empty" in response.error


def test_endpoint_target_send_message_whitespace_message(mock_endpoint):
    """Test EndpointTarget send_message with whitespace-only message."""
    target = EndpointTarget(endpoint=mock_endpoint)

    response = target.send_message("   ")

    assert response.success is False
    assert "cannot be empty" in response.error


def test_endpoint_target_send_message_too_long(mock_endpoint):
    """Test EndpointTarget send_message with message too long."""
    target = EndpointTarget(endpoint=mock_endpoint)

    long_message = "a" * 10001

    response = target.send_message(long_message)

    assert response.success is False
    assert "too long" in response.error


def test_endpoint_target_send_message_none_response(mock_endpoint):
    """Test EndpointTarget handles None response from invoke."""
    target = EndpointTarget(endpoint=mock_endpoint)
    mock_endpoint.invoke.return_value = None

    response = target.send_message("Hello")

    assert response.success is False
    assert "returned None" in response.error


def test_endpoint_target_send_message_with_metadata(mock_endpoint):
    """Test EndpointTarget preserves metadata from response."""
    target = EndpointTarget(endpoint=mock_endpoint)
    mock_endpoint.invoke.return_value = {
        "output": "Response",
        "conversation_id": "conv-123",
        "metadata": {"key": "value"},
        "context": ["context1", "context2"],
    }

    response = target.send_message("Hello")

    assert response.success is True
    assert "endpoint_metadata" in response.metadata
    assert response.metadata["endpoint_metadata"] == {"key": "value"}
    assert "context" in response.metadata
    assert response.metadata["context"] == ["context1", "context2"]


def test_endpoint_target_send_message_value_error(mock_endpoint):
    """Test EndpointTarget handles ValueError from invoke."""
    target = EndpointTarget(endpoint=mock_endpoint)
    mock_endpoint.invoke.side_effect = ValueError("Invalid input")

    response = target.send_message("Hello")

    assert response.success is False
    assert "Invalid request" in response.error


def test_endpoint_target_send_message_unexpected_error(mock_endpoint):
    """Test EndpointTarget handles unexpected errors."""
    target = EndpointTarget(endpoint=mock_endpoint)
    mock_endpoint.invoke.side_effect = RuntimeError("Unexpected error")

    response = target.send_message("Hello")

    assert response.success is False
    assert "Unexpected error" in response.error


def test_endpoint_target_get_tool_documentation(mock_endpoint):
    """Test EndpointTarget get_tool_documentation."""
    target = EndpointTarget(endpoint=mock_endpoint)

    doc = target.get_tool_documentation()

    assert "Rhesis Endpoint" in doc
    assert "Test Endpoint" in doc
    assert "endpoint-123" in doc
    assert "REST" in doc
    assert "https://test.example.com/chat" in doc
    assert "Test endpoint description" in doc
    assert "send_message_to_target" in doc
