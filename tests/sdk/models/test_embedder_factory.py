from unittest.mock import Mock, patch

import pytest

from rhesis.sdk.models.base import BaseEmbedder
from rhesis.sdk.models.factory import (
    DEFAULT_EMBEDDER_PROVIDER,
    DEFAULT_EMBEDDING_MODELS,
    EmbedderConfig,
    get_embedder,
)


class TestEmbedderConfig:
    """Test the EmbedderConfig dataclass."""

    def test_embedder_config_defaults(self):
        """Test EmbedderConfig with default values."""
        config = EmbedderConfig()
        assert config.provider is None
        assert config.model_name is None
        assert config.api_key is None
        assert config.dimensions is None
        assert config.extra_params == {}

    def test_embedder_config_with_values(self):
        """Test EmbedderConfig with provided values."""
        config = EmbedderConfig(
            provider="openai",
            model_name="text-embedding-3-small",
            api_key="test-key",
            dimensions=512,
            extra_params={"timeout": 30},
        )
        assert config.provider == "openai"
        assert config.model_name == "text-embedding-3-small"
        assert config.api_key == "test-key"
        assert config.dimensions == 512
        assert config.extra_params == {"timeout": 30}


class TestGetEmbedder:
    """Test the get_embedder function with various configurations."""

    @patch("rhesis.sdk.models.providers.openai.OpenAIEmbedder")
    def test_get_embedder_minimal_defaults(self, mock_embedder_class):
        """Test get_embedder() with no parameters - uses all defaults."""
        mock_instance = Mock(spec=BaseEmbedder)
        mock_embedder_class.return_value = mock_instance

        result = get_embedder()

        # Should use default provider and model
        mock_embedder_class.assert_called_once_with(
            model_name=DEFAULT_EMBEDDING_MODELS[DEFAULT_EMBEDDER_PROVIDER],
            api_key=None,
            dimensions=None,
        )
        assert result == mock_instance

    @patch("rhesis.sdk.models.providers.openai.OpenAIEmbedder")
    def test_get_embedder_provider_only(self, mock_embedder_class):
        """Test get_embedder("openai") - uses default model for provider."""
        mock_instance = Mock(spec=BaseEmbedder)
        mock_embedder_class.return_value = mock_instance

        result = get_embedder("openai")

        mock_embedder_class.assert_called_once_with(
            model_name=DEFAULT_EMBEDDING_MODELS["openai"], api_key=None, dimensions=None
        )
        assert result == mock_instance

    @patch("rhesis.sdk.models.providers.openai.OpenAIEmbedder")
    def test_get_embedder_provider_and_model(self, mock_embedder_class):
        """Test get_embedder("openai", "text-embedding-3-large")."""
        mock_instance = Mock(spec=BaseEmbedder)
        mock_embedder_class.return_value = mock_instance

        result = get_embedder("openai", "text-embedding-3-large")

        mock_embedder_class.assert_called_once_with(
            model_name="text-embedding-3-large", api_key=None, dimensions=None
        )
        assert result == mock_instance

    @patch("rhesis.sdk.models.providers.openai.OpenAIEmbedder")
    def test_get_embedder_with_api_key(self, mock_embedder_class):
        """Test get_embedder with API key."""
        mock_instance = Mock(spec=BaseEmbedder)
        mock_embedder_class.return_value = mock_instance

        result = get_embedder("openai", "text-embedding-3-small", "test-api-key")

        mock_embedder_class.assert_called_once_with(
            model_name="text-embedding-3-small", api_key="test-api-key", dimensions=None
        )
        assert result == mock_instance

    @patch("rhesis.sdk.models.providers.openai.OpenAIEmbedder")
    def test_get_embedder_with_dimensions(self, mock_embedder_class):
        """Test get_embedder with custom dimensions."""
        mock_instance = Mock(spec=BaseEmbedder)
        mock_embedder_class.return_value = mock_instance

        result = get_embedder("openai", "text-embedding-3-small", dimensions=512)

        mock_embedder_class.assert_called_once_with(
            model_name="text-embedding-3-small", api_key=None, dimensions=512
        )
        assert result == mock_instance

    @patch("rhesis.sdk.models.providers.openai.OpenAIEmbedder")
    def test_get_embedder_shorthand_provider_model(self, mock_embedder_class):
        """Test get_embedder("openai/text-embedding-3-large") - shorthand notation."""
        mock_instance = Mock(spec=BaseEmbedder)
        mock_embedder_class.return_value = mock_instance

        result = get_embedder("openai/text-embedding-3-large")

        mock_embedder_class.assert_called_once_with(
            model_name="text-embedding-3-large", api_key=None, dimensions=None
        )
        assert result == mock_instance

    @patch("rhesis.sdk.models.providers.openai.OpenAIEmbedder")
    def test_get_embedder_with_config_object(self, mock_embedder_class):
        """Test get_embedder(config=EmbedderConfig(...))."""
        mock_instance = Mock(spec=BaseEmbedder)
        mock_embedder_class.return_value = mock_instance

        config = EmbedderConfig(
            provider="openai",
            model_name="text-embedding-ada-002",
            api_key="config-key",
            dimensions=1536,
        )

        result = get_embedder(config=config)

        mock_embedder_class.assert_called_once_with(
            model_name="text-embedding-ada-002", api_key="config-key", dimensions=1536
        )
        assert result == mock_instance

    @patch("rhesis.sdk.models.providers.gemini.GeminiEmbedder")
    def test_get_embedder_gemini(self, mock_embedder_class):
        """Test get_embedder with gemini provider."""
        mock_instance = Mock(spec=BaseEmbedder)
        mock_embedder_class.return_value = mock_instance

        result = get_embedder("gemini", "text-embedding-004")

        mock_embedder_class.assert_called_once_with(
            model_name="text-embedding-004", api_key=None, dimensions=None
        )
        assert result == mock_instance

    @patch("rhesis.sdk.models.providers.vertex_ai.VertexAIEmbedder")
    def test_get_embedder_vertex_ai(self, mock_embedder_class):
        """Test get_embedder with vertex_ai provider."""
        mock_instance = Mock(spec=BaseEmbedder)
        mock_embedder_class.return_value = mock_instance

        result = get_embedder("vertex_ai", "text-embedding-005")

        mock_embedder_class.assert_called_once_with(
            model_name="text-embedding-005",
            credentials=None,
            location=None,
            project=None,
            dimensions=None,
        )
        assert result == mock_instance

    def test_get_embedder_unsupported_provider(self):
        """Test get_embedder with unsupported provider raises ValueError."""
        with pytest.raises(ValueError, match="Embedder provider 'unsupported' not supported"):
            get_embedder("unsupported")

    @patch("rhesis.sdk.models.providers.openai.OpenAIEmbedder")
    def test_get_embedder_all_parameters(self, mock_embedder_class):
        """Test get_embedder with all parameters specified."""
        mock_instance = Mock(spec=BaseEmbedder)
        mock_embedder_class.return_value = mock_instance

        result = get_embedder(
            provider="openai",
            model_name="text-embedding-3-large",
            api_key="test-key",
            dimensions=256,
        )

        mock_embedder_class.assert_called_once_with(
            model_name="text-embedding-3-large", api_key="test-key", dimensions=256
        )
        assert result == mock_instance
