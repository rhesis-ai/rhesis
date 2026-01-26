"""Unit tests for the Endpoint entity class."""

import os
from unittest.mock import MagicMock, patch

import pytest

from rhesis.sdk.entities.endpoint import ConnectionType, Endpoint

os.environ["RHESIS_BASE_URL"] = "http://test:8000"


class TestEndpointFields:
    """Tests for Endpoint field definitions."""

    def test_endpoint_has_required_fields_defined(self):
        """Endpoint should define _push_required_fields."""
        assert hasattr(Endpoint, "_push_required_fields")
        assert "name" in Endpoint._push_required_fields
        assert "connection_type" in Endpoint._push_required_fields
        assert "project_id" in Endpoint._push_required_fields

    def test_endpoint_can_be_created_with_all_fields(self):
        """Endpoint should accept all documented fields."""
        endpoint = Endpoint(
            name="Test API",
            description="A test endpoint",
            connection_type=ConnectionType.REST,
            url="https://api.example.com",
            project_id="test-project-id",
            method="POST",
            endpoint_path="/v1/chat",
            request_headers={"Content-Type": "application/json"},
            query_params={"version": "v1"},
            request_mapping={"message": "{{ input }}"},
            response_mapping={"output": "response.text"},
            auth_token="test-token",
        )

        assert endpoint.name == "Test API"
        assert endpoint.description == "A test endpoint"
        assert endpoint.connection_type == ConnectionType.REST
        assert endpoint.url == "https://api.example.com"
        assert endpoint.project_id == "test-project-id"
        assert endpoint.method == "POST"
        assert endpoint.endpoint_path == "/v1/chat"
        assert endpoint.request_headers == {"Content-Type": "application/json"}
        assert endpoint.query_params == {"version": "v1"}
        assert endpoint.request_mapping == {"message": "{{ input }}"}
        assert endpoint.response_mapping == {"output": "response.text"}
        assert endpoint.auth_token == "test-token"

    def test_endpoint_fields_are_optional(self):
        """All fields except required ones should be optional."""
        endpoint = Endpoint()
        assert endpoint.name is None
        assert endpoint.description is None
        assert endpoint.connection_type is None
        assert endpoint.url is None
        assert endpoint.project_id is None
        assert endpoint.method is None
        assert endpoint.endpoint_path is None
        assert endpoint.request_headers is None
        assert endpoint.query_params is None
        assert endpoint.request_mapping is None
        assert endpoint.response_mapping is None
        assert endpoint.auth_token is None


class TestEndpointPushValidation:
    """Tests for Endpoint push validation."""

    def test_push_raises_error_when_name_missing(self):
        """push() should raise ValueError when name is missing."""
        endpoint = Endpoint(
            connection_type=ConnectionType.REST,
            project_id="test-project-id",
        )
        with pytest.raises(ValueError) as exc_info:
            endpoint.push()
        assert "name" in str(exc_info.value)

    def test_push_raises_error_when_connection_type_missing(self):
        """push() should raise ValueError when connection_type is missing."""
        endpoint = Endpoint(
            name="Test API",
            project_id="test-project-id",
        )
        with pytest.raises(ValueError) as exc_info:
            endpoint.push()
        assert "connection_type" in str(exc_info.value)

    def test_push_raises_error_when_project_id_missing(self):
        """push() should raise ValueError when project_id is missing."""
        endpoint = Endpoint(
            name="Test API",
            connection_type=ConnectionType.REST,
        )
        with pytest.raises(ValueError) as exc_info:
            endpoint.push()
        assert "project_id" in str(exc_info.value)

    def test_push_raises_error_with_all_missing_fields(self):
        """push() should list all missing required fields."""
        endpoint = Endpoint()
        with pytest.raises(ValueError) as exc_info:
            endpoint.push()
        error_message = str(exc_info.value)
        assert "name" in error_message
        assert "connection_type" in error_message
        assert "project_id" in error_message

    @patch("requests.request")
    def test_push_succeeds_with_required_fields(self, mock_request):
        """push() should succeed when all required fields are provided."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "new-endpoint-id"}
        mock_request.return_value = mock_response

        endpoint = Endpoint(
            name="Test API",
            connection_type=ConnectionType.REST,
            project_id="test-project-id",
        )
        result = endpoint.push()

        assert result is not None
        assert endpoint.id == "new-endpoint-id"
        mock_request.assert_called_once()


class TestConnectionType:
    """Tests for ConnectionType enum."""

    def test_connection_type_values(self):
        """ConnectionType should have expected values."""
        assert ConnectionType.REST.value == "REST"
        assert ConnectionType.WEBSOCKET.value == "WebSocket"
        assert ConnectionType.GRPC.value == "GRPC"
        assert ConnectionType.SDK.value == "SDK"

    def test_connection_type_is_string_enum(self):
        """ConnectionType should be a string enum."""
        assert isinstance(ConnectionType.REST, str)
        assert ConnectionType.REST == "REST"


class TestEndpointSerialization:
    """Tests for Endpoint serialization."""

    def test_to_dict_includes_all_fields(self):
        """to_dict() should include all set fields."""
        endpoint = Endpoint(
            name="Test API",
            connection_type=ConnectionType.REST,
            project_id="test-project-id",
            request_mapping={"message": "{{ input }}"},
            response_mapping={"output": "response.text"},
            auth_token="secret-token",
        )

        data = endpoint.to_dict()

        assert data["name"] == "Test API"
        assert data["connection_type"] == "REST"
        assert data["project_id"] == "test-project-id"
        assert data["request_mapping"] == {"message": "{{ input }}"}
        assert data["response_mapping"] == {"output": "response.text"}
        assert data["auth_token"] == "secret-token"

    def test_from_dict_creates_endpoint(self):
        """from_dict() should create an Endpoint from a dictionary."""
        data = {
            "name": "Test API",
            "connection_type": "REST",
            "project_id": "test-project-id",
            "request_mapping": {"message": "{{ input }}"},
        }

        endpoint = Endpoint.from_dict(data)

        assert endpoint.name == "Test API"
        assert endpoint.connection_type == ConnectionType.REST
        assert endpoint.project_id == "test-project-id"
        assert endpoint.request_mapping == {"message": "{{ input }}"}
