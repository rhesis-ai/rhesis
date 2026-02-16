from unittest.mock import Mock, patch

import pytest

from rhesis.sdk.models.base import BaseEmbedder
from rhesis.sdk.models.factory import (
    DEFAULT_EMBEDDING_MODEL_PROVIDER,
    DEFAULT_EMBEDDING_MODELS,
    EmbeddingModelConfig,
    get_embedding_model,
)


class TestEmbeddingModelConfig:
    """Test the EmbeddingModelConfig dataclass."""

    def test_embedder_config_defaults(self):
        """Test EmbeddingModelConfig with default values."""
        config = EmbeddingModelConfig()
        assert config.provider is None
        assert config.model_name is None
        assert config.api_key is None
        assert config.dimensions is None
        assert config.extra_params == {}

    def test_embedder_config_with_values(self):
        """Test EmbeddingModelConfig with provided values."""
        config = EmbeddingModelConfig(
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


class TestGetEmbeddingModel:
    """Test the get_embedding_model function with various configurations."""

    @patch("rhesis.sdk.models.providers.openai.OpenAIEmbedder")
    def test_get_embedding_model_minimal_defaults(self, mock_embedder_class):
        """Test get_embedding_model() with no parameters - uses all defaults."""
        mock_instance = Mock(spec=BaseEmbedder)
        mock_embedder_class.return_value = mock_instance

        result = get_embedding_model()

        # Should use default provider and embedding model
        mock_embedder_class.assert_called_once_with(
            model_name=DEFAULT_EMBEDDING_MODELS[DEFAULT_EMBEDDING_MODEL_PROVIDER],
            api_key=None,
            dimensions=None,
        )
        assert result == mock_instance

    @patch("rhesis.sdk.models.providers.openai.OpenAIEmbedder")
    def test_get_embedding_model_provider_only(self, mock_embedder_class):
        """Test get_embedding_model("openai") - uses default model for provider."""
        mock_instance = Mock(spec=BaseEmbedder)
        mock_embedder_class.return_value = mock_instance

        result = get_embedding_model("openai")

        mock_embedder_class.assert_called_once_with(
            model_name=DEFAULT_EMBEDDING_MODELS["openai"], api_key=None, dimensions=None
        )
        assert result == mock_instance

    @patch("rhesis.sdk.models.providers.openai.OpenAIEmbedder")
    def test_get_embedding_model_provider_and_model(self, mock_embedder_class):
        """Test get_embedding_model("openai", "text-embedding-3-large")."""
        mock_instance = Mock(spec=BaseEmbedder)
        mock_embedder_class.return_value = mock_instance

        result = get_embedding_model("openai", "text-embedding-3-large")

        mock_embedder_class.assert_called_once_with(
            model_name="text-embedding-3-large", api_key=None, dimensions=None
        )
        assert result == mock_instance

    @patch("rhesis.sdk.models.providers.openai.OpenAIEmbedder")
    def test_get_embedding_model_with_api_key(self, mock_embedder_class):
        """Test get_embedding_model with API key."""
        mock_instance = Mock(spec=BaseEmbedder)
        mock_embedder_class.return_value = mock_instance

        result = get_embedding_model("openai", "text-embedding-3-small", "test-api-key")

        mock_embedder_class.assert_called_once_with(
            model_name="text-embedding-3-small", api_key="test-api-key", dimensions=None
        )
        assert result == mock_instance

    @patch("rhesis.sdk.models.providers.openai.OpenAIEmbedder")
    def test_get_embedding_model_with_dimensions(self, mock_embedder_class):
        """Test get_embedding_model with custom dimensions."""
        mock_instance = Mock(spec=BaseEmbedder)
        mock_embedder_class.return_value = mock_instance

        result = get_embedding_model("openai", "text-embedding-3-small", dimensions=512)

        mock_embedder_class.assert_called_once_with(
            model_name="text-embedding-3-small", api_key=None, dimensions=512
        )
        assert result == mock_instance

    @patch("rhesis.sdk.models.providers.openai.OpenAIEmbedder")
    def test_get_embedding_model_shorthand_provider_model(self, mock_embedder_class):
        """Test get_embedding_model("openai/text-embedding-3-large") - shorthand notation."""
        mock_instance = Mock(spec=BaseEmbedder)
        mock_embedder_class.return_value = mock_instance

        result = get_embedding_model("openai/text-embedding-3-large")

        mock_embedder_class.assert_called_once_with(
            model_name="text-embedding-3-large", api_key=None, dimensions=None
        )
        assert result == mock_instance

    @patch("rhesis.sdk.models.providers.openai.OpenAIEmbedder")
    def test_get_embedding_model_with_config_object(self, mock_embedder_class):
        """Test get_embedding_model(config=EmbeddingModelConfig(...))."""
        mock_instance = Mock(spec=BaseEmbedder)
        mock_embedder_class.return_value = mock_instance

        config = EmbeddingModelConfig(
            provider="openai",
            model_name="text-embedding-ada-002",
            api_key="config-key",
            dimensions=1536,
        )

        result = get_embedding_model(config=config)

        mock_embedder_class.assert_called_once_with(
            model_name="text-embedding-ada-002", api_key="config-key", dimensions=1536
        )
        assert result == mock_instance

    @patch("rhesis.sdk.models.providers.gemini.GeminiEmbedder")
    def test_get_embedding_model_gemini(self, mock_embedder_class):
        """Test get_embedding_model with gemini provider."""
        mock_instance = Mock(spec=BaseEmbedder)
        mock_embedder_class.return_value = mock_instance

        result = get_embedding_model("gemini", "text-embedding-004")

        mock_embedder_class.assert_called_once_with(
            model_name="text-embedding-004", api_key=None, dimensions=None
        )
        assert result == mock_instance

    @patch("rhesis.sdk.models.providers.vertex_ai.VertexAIEmbedder")
    def test_get_embedding_model_vertex_ai(self, mock_embedder_class):
        """Test get_embedding_model with vertex_ai provider."""
        mock_instance = Mock(spec=BaseEmbedder)
        mock_embedder_class.return_value = mock_instance

        result = get_embedding_model("vertex_ai", "text-embedding-005")

        mock_embedder_class.assert_called_once_with(
            model_name="text-embedding-005",
            credentials=None,
            location=None,
            project=None,
            dimensions=None,
        )
        assert result == mock_instance

    def test_get_embedding_model_unsupported_provider(self):
        """Test get_embedding_model with unsupported provider raises ValueError."""
        with pytest.raises(
            ValueError, match="Embedding model provider 'unsupported' not supported"
        ):
            get_embedding_model("unsupported")

    @patch("rhesis.sdk.models.providers.openai.OpenAIEmbedder")
    def test_get_embedding_model_all_parameters(self, mock_embedder_class):
        """Test get_embedding_model with all parameters specified."""
        mock_instance = Mock(spec=BaseEmbedder)
        mock_embedder_class.return_value = mock_instance

        result = get_embedding_model(
            provider="openai",
            model_name="text-embedding-3-large",
            api_key="test-key",
            dimensions=256,
        )

        mock_embedder_class.assert_called_once_with(
            model_name="text-embedding-3-large", api_key="test-key", dimensions=256
        )
        assert result == mock_instance
