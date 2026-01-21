import os
from unittest.mock import Mock, patch

import pytest
import requests
from pydantic import BaseModel

from rhesis.sdk.models.providers.native import (
    DEFAULT_MODEL_NAME,
    RhesisLLM,
)


class Capital(BaseModel):
    name_of_capital: str
    population: int


class Continent(BaseModel):
    name_of_continent: str
    capitals: list[Capital]


class TestRhesisLLM:
    """Test class for RhesisLLM."""

    @pytest.fixture
    def mock_env_vars(self):
        """Mock environment variables."""
        with patch.dict(
            os.environ,
            {
                "RHESIS_API_KEY": "test_api_key",
                "RHESIS_BASE_URL": "https://test.example.com",
            },
        ):
            yield

    @pytest.fixture
    def mock_client(self):
        """Mock APIClient class."""
        with patch("rhesis.sdk.models.providers.native.APIClient") as mock_client_class:
            mock_client = Mock()
            mock_client.api_key = "test_api_key"
            mock_client.get_url.return_value = "https://test.example.com/services/generate/content"
            mock_client_class.return_value = mock_client
            yield mock_client_class

    @pytest.fixture
    def service(self, mock_env_vars, mock_client):
        """Create a service instance with mocked dependencies."""
        return RhesisLLM()

    def test_init_with_env_vars(self, mock_env_vars, mock_client):
        """Test initialization with environment variables."""
        service = RhesisLLM()
        assert service.api_key == "test_api_key"
        assert service.base_url == "https://test.example.com"
        assert service.model_name == DEFAULT_MODEL_NAME

    def test_init_with_explicit_params(self, mock_client):
        """Test initialization with explicit parameters."""
        service = RhesisLLM(
            model_name="custom-model",
            api_key="custom_key",
            base_url="https://custom.example.com",
        )
        assert service.api_key == "custom_key"
        assert service.base_url == "https://custom.example.com"
        assert service.model_name == "custom-model"

    def test_init_missing_api_key(self):
        """Test initialization fails without API key."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="RHESIS_API_KEY is not set"):
                RhesisLLM()

    def test_load_model(self, service, mock_client):
        """Test load_model method."""
        result = service.load_model()

        assert result == service
        assert hasattr(service, "client")
        assert hasattr(service, "headers")
        assert service.headers["Authorization"] == "Bearer test_api_key"
        assert service.headers["Content-Type"] == "application/json"

    @patch("requests.post")
    def test_create_completion_success(self, mock_post, service, mock_client):
        """Test successful completion creation."""
        # Mock the response
        mock_response = Mock()
        mock_response.json.return_value = {
            "content": "Test response",
            "status": "success",
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        # Load model to set up client and headers
        service.load_model()

        result = service.create_completion(
            prompt="Test prompt", temperature=0.5, max_tokens=1000, schema="test_schema"
        )

        assert result == {"content": "Test response", "status": "success"}

        # Verify the request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "https://test.example.com/services/generate/content"
        assert call_args[1]["headers"]["Authorization"] == "Bearer test_api_key"
        assert call_args[1]["json"]["prompt"] == "Test prompt"
        assert call_args[1]["json"]["temperature"] == 0.5
        assert call_args[1]["json"]["max_tokens"] == 1000
        assert call_args[1]["json"]["schema"] == "test_schema"

    @patch("requests.post")
    def test_create_completion_http_error(self, mock_post, service, mock_client):
        """Test completion creation with HTTP error."""
        # Mock HTTP error
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Not Found")
        mock_post.return_value = mock_response

        service.load_model()

        with pytest.raises(requests.exceptions.HTTPError):
            service.create_completion(prompt="Test prompt")

    @patch("requests.post")
    def test_generate_with_schema_success(self, mock_post, service, mock_client):
        """Test generate method with schema on success."""
        # Mock the response
        mock_response = Mock()
        mock_response.json.return_value = {
            "content": '{"name_of_continent": "Europe", "capitals": [{"name_of_capital": "London", "population": 9000000}]}',
            "status": "success",
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        service.load_model()

        result = service.generate(prompt="Test prompt", schema=Continent)

        assert result == mock_response.json.return_value

        # Verify schema was converted to JSON schema format
        call_args = mock_post.call_args
        schema_data = call_args[1]["json"]["schema"]
        assert schema_data["type"] == "json_schema"
        assert schema_data["json_schema"]["name"] == "Continent"
        assert "properties" in schema_data["json_schema"]["schema"]

    @patch("requests.post")
    def test_generate_with_schema_error(self, mock_post, service, mock_client):
        """Test generate method with schema on error."""
        # Mock HTTP error
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "500 Internal Error"
        )
        mock_post.return_value = mock_response

        service.load_model()

        result = service.generate(prompt="Test prompt", schema=Continent)

        assert result == {"error": "An error occurred while processing the request."}

    def test_default_parameters(self, service, mock_client):
        """Test default parameter values."""
        assert service.model_name == DEFAULT_MODEL_NAME

    @patch("requests.post")
    def test_create_completion_default_params(self, mock_post, service, mock_client):
        """Test create_completion with default parameters."""
        mock_response = Mock()
        mock_response.json.return_value = {"content": "Test"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        service.load_model()

        result = service.create_completion(prompt="Test")

        # Verify default values were used
        call_args = mock_post.call_args
        assert call_args[1]["json"]["temperature"] == 0.7
        assert call_args[1]["json"]["max_tokens"] == 4000
        assert call_args[1]["json"]["schema"] is None

    @patch("requests.post")
    def test_create_completion_custom_params(self, mock_post, service, mock_client):
        """Test create_completion with custom parameters."""
        mock_response = Mock()
        mock_response.json.return_value = {"content": "Test"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        service.load_model()

        result = service.create_completion(
            prompt="Test",
            temperature=0.1,
            max_tokens=2000,
            schema="custom_schema",
            custom_param="value",
        )

        # Verify custom values were used
        call_args = mock_post.call_args
        assert call_args[1]["json"]["temperature"] == 0.1
        assert call_args[1]["json"]["max_tokens"] == 2000
        assert call_args[1]["json"]["schema"] == "custom_schema"
        assert call_args[1]["json"]["custom_param"] == "value"

    @patch("requests.post")
    def test_generate_without_schema_success(self, mock_post, service, mock_client):
        """Test generate method without schema on success."""
        # Mock the response
        mock_response = Mock()
        mock_response.json.return_value = {
            "content": "This is a test response without schema validation.",
            "status": "success",
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        service.load_model()

        result = service.generate(prompt="Tell me a joke.")

        assert result == mock_response.json.return_value

        # Verify no schema was passed
        call_args = mock_post.call_args
        assert call_args[1]["json"]["schema"] is None
        assert call_args[1]["json"]["prompt"] == "Tell me a joke."

    @patch("requests.post")
    def test_generate_without_schema_error(self, mock_post, service, mock_client):
        """Test generate method without schema on error."""
        # Mock HTTP error
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "500 Internal Error"
        )
        mock_post.return_value = mock_response

        service.load_model()

        result = service.generate(prompt="Tell me a joke.")

        # Should return a string error message when no schema is provided
        assert result == "An error occurred while processing the request."
