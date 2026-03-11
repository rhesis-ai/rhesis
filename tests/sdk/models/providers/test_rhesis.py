import os
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import aiohttp
import pytest
from pydantic import BaseModel

from rhesis.sdk.models.providers.native import (
    DEFAULT_LANGUAGE_MODEL_NAME,
    RhesisLLM,
)


class Capital(BaseModel):
    name_of_capital: str
    population: int


class Continent(BaseModel):
    name_of_continent: str
    capitals: list[Capital]


def _mock_aiohttp_session(response_json=None, status=200, raise_for_status=None):
    """Build a mock aiohttp.ClientSession for use with ``async with``.

    aiohttp's session.post() returns a context manager synchronously,
    so we use MagicMock for the call and AsyncMock for __aenter__/__aexit__.
    """
    mock_response = MagicMock()
    mock_response.status = status
    mock_response.json = AsyncMock(return_value=response_json)
    if raise_for_status:
        mock_response.raise_for_status.side_effect = raise_for_status
    else:
        mock_response.raise_for_status = MagicMock()

    mock_post_ctx = MagicMock()
    mock_post_ctx.__aenter__ = AsyncMock(return_value=mock_response)
    mock_post_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=mock_post_ctx)

    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    return mock_session_ctx, mock_session, mock_response


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
        assert service.model_name == DEFAULT_LANGUAGE_MODEL_NAME

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

    @patch("aiohttp.ClientSession")
    def test_create_completion_success(self, mock_session_class, service):
        """Test successful completion creation."""
        session_ctx, mock_session, mock_response = _mock_aiohttp_session(
            response_json={"content": "Test response", "status": "success"},
        )
        mock_session_class.return_value = session_ctx

        service.load_model()
        result = service.generate(prompt="Test prompt", temperature=0.5, max_tokens=1000)

        assert result == {"content": "Test response", "status": "success"}

        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args
        assert call_args[0][0] == "https://test.example.com/services/generate/content"
        assert call_args[1]["json"]["prompt"] == "Test prompt"
        assert call_args[1]["json"]["temperature"] == 0.5
        assert call_args[1]["json"]["max_tokens"] == 1000

    @patch("aiohttp.ClientSession")
    def test_create_completion_http_error(self, mock_session_class, service):
        """Test completion creation with HTTP error."""
        session_ctx, _, _ = _mock_aiohttp_session(
            status=404,
            raise_for_status=aiohttp.ClientResponseError(
                request_info=MagicMock(),
                history=(),
                status=404,
                message="Not Found",
            ),
        )
        mock_session_class.return_value = session_ctx

        service.load_model()
        result = service.generate(prompt="Test prompt")
        assert result == "An error occurred while processing the request."

    @patch("aiohttp.ClientSession")
    def test_generate_with_schema_success(self, mock_session_class, service):
        """Test generate method with schema on success."""
        response_data = {
            "content": (
                '{"name_of_continent": "Europe", '
                '"capitals": [{"name_of_capital": "London", "population": 9000000}]}'
            ),
            "status": "success",
        }
        session_ctx, mock_session, _ = _mock_aiohttp_session(
            response_json=response_data,
        )
        mock_session_class.return_value = session_ctx

        service.load_model()
        result = service.generate(prompt="Test prompt", schema=Continent)

        assert result == response_data

        call_args = mock_session.post.call_args
        schema_data = call_args[1]["json"]["schema"]
        assert schema_data["type"] == "json_schema"
        assert schema_data["json_schema"]["name"] == "Continent"
        assert "properties" in schema_data["json_schema"]["schema"]

    @patch("aiohttp.ClientSession")
    def test_generate_with_schema_error(self, mock_session_class, service):
        """Test generate method with schema on error."""
        session_ctx, _, _ = _mock_aiohttp_session(
            status=500,
            raise_for_status=aiohttp.ClientResponseError(
                request_info=MagicMock(),
                history=(),
                status=500,
                message="Internal Server Error",
            ),
        )
        mock_session_class.return_value = session_ctx

        service.load_model()
        result = service.generate(prompt="Test prompt", schema=Continent)
        assert result == {"error": "An error occurred while processing the request."}

    def test_default_parameters(self, service, mock_client):
        """Test default parameter values."""
        assert service.model_name == DEFAULT_LANGUAGE_MODEL_NAME

    @patch("aiohttp.ClientSession")
    def test_create_completion_default_params(self, mock_session_class, service):
        """Test create_completion with default parameters."""
        session_ctx, mock_session, _ = _mock_aiohttp_session(
            response_json={"content": "Test"},
        )
        mock_session_class.return_value = session_ctx

        service.load_model()
        service.generate(prompt="Test")

        call_args = mock_session.post.call_args
        assert call_args[1]["json"]["temperature"] == 0.7
        assert call_args[1]["json"]["max_tokens"] == 4000
        assert call_args[1]["json"]["schema"] is None

    @patch("aiohttp.ClientSession")
    def test_create_completion_custom_params(self, mock_session_class, service):
        """Test create_completion with custom parameters."""
        session_ctx, mock_session, _ = _mock_aiohttp_session(
            response_json={"content": "Test"},
        )
        mock_session_class.return_value = session_ctx

        service.load_model()
        service.generate(
            prompt="Test",
            temperature=0.1,
            max_tokens=2000,
            custom_param="value",
        )

        call_args = mock_session.post.call_args
        assert call_args[1]["json"]["temperature"] == 0.1
        assert call_args[1]["json"]["max_tokens"] == 2000
        assert call_args[1]["json"]["custom_param"] == "value"

    @patch("aiohttp.ClientSession")
    def test_generate_without_schema_success(self, mock_session_class, service):
        """Test generate method without schema on success."""
        session_ctx, mock_session, _ = _mock_aiohttp_session(
            response_json={
                "content": "This is a test response without schema validation.",
                "status": "success",
            },
        )
        mock_session_class.return_value = session_ctx

        service.load_model()
        result = service.generate(prompt="Tell me a joke.")

        assert result == {
            "content": "This is a test response without schema validation.",
            "status": "success",
        }

        call_args = mock_session.post.call_args
        assert call_args[1]["json"]["schema"] is None
        assert call_args[1]["json"]["prompt"] == "Tell me a joke."

    @patch("aiohttp.ClientSession")
    def test_generate_without_schema_error(self, mock_session_class, service):
        """Test generate method without schema on error."""
        session_ctx, _, _ = _mock_aiohttp_session(
            status=500,
            raise_for_status=aiohttp.ClientResponseError(
                request_info=MagicMock(),
                history=(),
                status=500,
                message="Internal Server Error",
            ),
        )
        mock_session_class.return_value = session_ctx

        service.load_model()
        result = service.generate(prompt="Tell me a joke.")
        assert result == "An error occurred while processing the request."

    @patch("aiohttp.ClientSession")
    def test_generate_batch_concurrent(self, mock_session_class, service):
        """Test generate_batch runs prompts concurrently."""
        responses = {
            "Prompt A": {"response": "Prompt A"},
            "Prompt B": {"response": "Prompt B"},
            "Prompt C": {"response": "Prompt C"},
        }

        def mock_post(url, **kwargs):
            prompt = kwargs["json"]["prompt"]
            resp = MagicMock()
            resp.status = 200
            resp.raise_for_status = MagicMock()
            resp.json = AsyncMock(return_value=responses[prompt])

            ctx = MagicMock()
            ctx.__aenter__ = AsyncMock(return_value=resp)
            ctx.__aexit__ = AsyncMock(return_value=False)
            return ctx

        mock_session = MagicMock()
        mock_session.post = mock_post

        session_ctx = MagicMock()
        session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        session_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_class.return_value = session_ctx

        service.load_model()
        results = service.generate_batch(prompts=["Prompt A", "Prompt B", "Prompt C"])

        assert len(results) == 3
        assert results[0] == {"response": "Prompt A"}
        assert results[1] == {"response": "Prompt B"}
        assert results[2] == {"response": "Prompt C"}
