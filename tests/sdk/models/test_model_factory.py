from unittest.mock import Mock, patch

import pytest

from rhesis.sdk.models.base import BaseEmbedder, BaseLLM
from rhesis.sdk.models.defaults import DEFAULT_LANGUAGE_MODEL, model_name_from_id
from rhesis.sdk.models.factory import (
    EmbeddingModelConfig,
    LanguageModelConfig,
    ModelType,
    get_embedding_model,
    get_model,
)


class TestLanguageModelConfig:
    """Test the LanguageModelConfig dataclass."""

    def test_language_model_config_defaults(self):
        """Test LanguageModelConfig with default values."""
        config = LanguageModelConfig()
        assert config.provider is None
        assert config.model_name is None
        assert config.api_key is None
        assert config.extra_params == {}

    def test_language_model_config_with_values(self):
        """Test LanguageModelConfig with provided values."""
        config = LanguageModelConfig(
            provider="test-provider",
            model_name="test-model",
            api_key="test-key",
            extra_params={"temperature": 0.5},
        )
        assert config.provider == "test-provider"
        assert config.model_name == "test-model"
        assert config.api_key == "test-key"
        assert config.extra_params == {"temperature": 0.5}


class TestEmbeddingModelConfig:
    """Test the EmbeddingModelConfig dataclass."""

    def test_embedding_model_config_defaults(self):
        """Test EmbeddingModelConfig with default values."""
        config = EmbeddingModelConfig()
        assert config.provider is None
        assert config.model_name is None
        assert config.api_key is None
        assert config.dimensions is None
        assert config.extra_params == {}

    def test_embedding_model_config_with_values(self):
        """Test EmbeddingModelConfig with provided values."""
        config = EmbeddingModelConfig(
            provider="openai",
            model_name="text-embedding-3-small",
            api_key="test-key",
            dimensions=512,
        )
        assert config.provider == "openai"
        assert config.model_name == "text-embedding-3-small"
        assert config.api_key == "test-key"
        assert config.dimensions == 512


class TestUnifiedGetModel:
    """Test the unified get_model() function with auto-detection."""

    # =============================================================================
    # Language Model Tests
    # =============================================================================

    @patch("rhesis.sdk.models.providers.native.RhesisLLM")
    def test_language_model_auto_detect_rhesis(self, mock_llm_class):
        """Test auto-detection of Rhesis language model."""
        mock_instance = Mock(spec=BaseLLM)
        mock_llm_class.return_value = mock_instance

        result = get_model("rhesis/rhesis-default")

        assert isinstance(result, BaseLLM)
        mock_llm_class.assert_called_once()

    @patch("rhesis.sdk.models.providers.openai.OpenAILLM")
    def test_language_model_auto_detect_openai(self, mock_llm_class):
        """Test auto-detection of OpenAI language model."""
        mock_instance = Mock(spec=BaseLLM)
        mock_llm_class.return_value = mock_instance

        result = get_model("openai/gpt-4o")

        assert isinstance(result, BaseLLM)
        mock_llm_class.assert_called_once()

    @patch("rhesis.sdk.models.providers.openai.OpenAILLM")
    def test_language_model_explicit_type(self, mock_llm_class):
        """Test explicit language model_type parameter."""
        mock_instance = Mock(spec=BaseLLM)
        mock_llm_class.return_value = mock_instance

        result = get_model("openai", "gpt-4o", model_type="language")

        assert isinstance(result, BaseLLM)
        mock_llm_class.assert_called_once_with(model_name="gpt-4o", api_key=None)

    @patch("rhesis.sdk.models.providers.native.RhesisLLM")
    def test_language_model_with_defaults(self, mock_llm_class):
        """Test language model creation with defaults."""
        mock_instance = Mock(spec=BaseLLM)
        mock_llm_class.return_value = mock_instance

        result = get_model()

        mock_llm_class.assert_called_once_with(
            model_name=model_name_from_id(DEFAULT_LANGUAGE_MODEL), api_key=None
        )
        assert result == mock_instance

    @patch("rhesis.sdk.models.providers.openai.OpenAILLM")
    def test_language_model_with_api_key(self, mock_llm_class):
        """Test language model with API key."""
        mock_instance = Mock(spec=BaseLLM)
        mock_llm_class.return_value = mock_instance

        result = get_model("openai", "gpt-4o", api_key="test-key")

        mock_llm_class.assert_called_once_with(model_name="gpt-4o", api_key="test-key")
        assert result == mock_instance

    # =============================================================================
    # Embedding Model Tests
    # =============================================================================

    @patch("rhesis.sdk.models.providers.openai.OpenAIEmbedder")
    def test_embedding_model_auto_detect(self, mock_embedder_class):
        """Test auto-detection of embedding model from name."""
        mock_instance = Mock(spec=BaseEmbedder)
        mock_embedder_class.return_value = mock_instance

        result = get_model("openai/text-embedding-3-small")

        assert isinstance(result, BaseEmbedder)
        mock_embedder_class.assert_called_once()

    @patch("rhesis.sdk.models.providers.openai.OpenAIEmbedder")
    def test_embedding_model_explicit_type(self, mock_embedder_class):
        """Test explicit embedding model_type parameter."""
        mock_instance = Mock(spec=BaseEmbedder)
        mock_embedder_class.return_value = mock_instance

        result = get_model("openai", "custom-model", model_type="embedding")

        assert isinstance(result, BaseEmbedder)
        mock_embedder_class.assert_called_once()

    @patch("rhesis.sdk.models.providers.openai.OpenAIEmbedder")
    def test_embedding_model_with_dimensions(self, mock_embedder_class):
        """Test embedding model with dimensions parameter."""
        mock_instance = Mock(spec=BaseEmbedder)
        mock_embedder_class.return_value = mock_instance

        result = get_model("openai/text-embedding-3-small", dimensions=512)

        mock_embedder_class.assert_called_once_with(
            model_name="text-embedding-3-small", api_key=None, dimensions=512
        )
        assert result == mock_instance

    @patch("rhesis.sdk.models.providers.gemini.GeminiEmbedder")
    def test_embedding_model_gemini(self, mock_embedder_class):
        """Test Gemini embedding model."""
        mock_instance = Mock(spec=BaseEmbedder)
        mock_embedder_class.return_value = mock_instance

        result = get_model("gemini/gemini-embedding-001")

        assert isinstance(result, BaseEmbedder)
        mock_embedder_class.assert_called_once()

    # =============================================================================
    # Error Cases
    # =============================================================================

    def test_unsupported_provider(self):
        """Test error when provider doesn't exist."""
        with pytest.raises(ValueError, match="Provider 'invalid-provider' not supported"):
            get_model("invalid-provider/some-model")

    def test_unsupported_type_for_provider(self):
        """Test error when provider doesn't support model type."""
        # Anthropic doesn't support embedding models
        with pytest.raises(ValueError, match="does not support model type 'embedding'"):
            get_model("anthropic", "text-embedding-3-small", model_type="embedding")

    # =============================================================================
    # Shorthand Notation Tests
    # =============================================================================

    @patch("rhesis.sdk.models.providers.openai.OpenAILLM")
    def test_shorthand_notation(self, mock_llm_class):
        """Test provider/model shorthand notation."""
        mock_instance = Mock(spec=BaseLLM)
        mock_llm_class.return_value = mock_instance

        result = get_model("openai/gpt-4o")

        mock_llm_class.assert_called_once_with(model_name="gpt-4o", api_key=None)
        assert result == mock_instance

    @patch("rhesis.sdk.models.providers.openai.OpenAIEmbedder")
    def test_shorthand_notation_embedding(self, mock_embedder_class):
        """Test shorthand notation for embeddings."""
        mock_instance = Mock(spec=BaseEmbedder)
        mock_embedder_class.return_value = mock_instance

        result = get_model("openai/text-embedding-3-small")

        mock_embedder_class.assert_called_once()
        assert result == mock_instance

    # =============================================================================
    # Configuration Object Tests
    # =============================================================================

    @patch("rhesis.sdk.models.providers.openai.OpenAILLM")
    def test_language_config_object(self, mock_llm_class):
        """Test using LanguageModelConfig object."""
        mock_instance = Mock(spec=BaseLLM)
        mock_llm_class.return_value = mock_instance

        config = LanguageModelConfig(
            provider="openai",
            model_name="gpt-4o",
            api_key="test-key",
        )
        result = get_model(config=config, model_type="language")

        mock_llm_class.assert_called_once()
        assert result == mock_instance

    @patch("rhesis.sdk.models.providers.openai.OpenAIEmbedder")
    def test_embedding_config_object(self, mock_embedder_class):
        """Test using EmbeddingModelConfig object."""
        mock_instance = Mock(spec=BaseEmbedder)
        mock_embedder_class.return_value = mock_instance

        config = EmbeddingModelConfig(
            provider="openai",
            model_name="text-embedding-3-small",
            api_key="test-key",
            dimensions=256,
        )
        result = get_model(config=config, model_type="embedding")

        mock_embedder_class.assert_called_once()
        assert result == mock_instance

    # =============================================================================
    # Optional model_type and shorthand notation (user-facing cases)
    # =============================================================================

    @patch("rhesis.sdk.models.providers.openai.OpenAIEmbedder")
    def test_embedding_shorthand_without_model_type(self, mock_embedder_class):
        """get_model('openai/text-embedding-3-small') works without model_type (auto-detect)."""
        mock_instance = Mock(spec=BaseEmbedder)
        mock_embedder_class.return_value = mock_instance

        embedder = get_model("openai/text-embedding-3-small")

        assert isinstance(embedder, BaseEmbedder)
        mock_embedder_class.assert_called_once_with(
            model_name="text-embedding-3-small", api_key=None, dimensions=None
        )

    @patch("rhesis.sdk.models.providers.openai.OpenAILLM")
    def test_language_shorthand_without_model_type(self, mock_llm_class):
        """get_model('openai/gpt-4o') works without model_type (auto-detect)."""
        mock_instance = Mock(spec=BaseLLM)
        mock_llm_class.return_value = mock_instance

        llm = get_model("openai/gpt-4o")

        assert isinstance(llm, BaseLLM)
        mock_llm_class.assert_called_once_with(model_name="gpt-4o", api_key=None)

    @patch("rhesis.sdk.models.providers.openai.OpenAIEmbedder")
    def test_embedding_config_without_model_type_auto_detected(self, mock_embedder_class):
        """get_model(config=EmbeddingModelConfig(...)) without model_type auto-detects embedding."""
        mock_instance = Mock(spec=BaseEmbedder)
        mock_embedder_class.return_value = mock_instance

        config = EmbeddingModelConfig(
            provider="openai",
            model_name="text-embedding-3-small",
        )
        result = get_model(config=config)

        assert isinstance(result, BaseEmbedder)
        mock_embedder_class.assert_called_once()

    def test_bare_model_name_without_provider_raises(self):
        """get_model('text-embedding-3-small') without provider raises (provider required)."""
        with pytest.raises(ValueError, match="Provider 'text-embedding-3-small' not supported"):
            get_model("text-embedding-3-small")

    @patch("rhesis.sdk.models.providers.openai.OpenAIEmbedder")
    def test_get_embedding_model_shorthand(self, mock_embedder_class):
        """get_embedding_model('openai/text-embedding-3-small') works (typed helper)."""
        mock_instance = Mock(spec=BaseEmbedder)
        mock_embedder_class.return_value = mock_instance

        embedder = get_embedding_model("openai/text-embedding-3-small")

        assert isinstance(embedder, BaseEmbedder)
        mock_embedder_class.assert_called_once()


class TestModelTypeClassification:
    """Test ModelType enum and classification logic."""

    def test_model_type_enum_values(self):
        """Test ModelType enum has expected values."""
        assert ModelType.LANGUAGE == "language"
        assert ModelType.EMBEDDING == "embedding"
        assert ModelType.IMAGE == "image"

    @patch("rhesis.sdk.models.providers.openai.OpenAIEmbedder")
    def test_classification_by_name_embedding(self, mock_embedder_class):
        """Test classification detects 'embedding' in name."""
        mock_instance = Mock(spec=BaseEmbedder)
        mock_embedder_class.return_value = mock_instance

        # Should auto-detect as embedding
        result = get_model("openai", "my-custom-embedding-model")

        assert isinstance(result, BaseEmbedder)

    @patch("rhesis.sdk.models.providers.openai.OpenAILLM")
    def test_classification_default_to_language(self, mock_llm_class):
        """Test classification defaults to language model."""
        mock_instance = Mock(spec=BaseLLM)
        mock_llm_class.return_value = mock_instance

        # Should default to language model
        result = get_model("openai", "some-unknown-model")

        assert isinstance(result, BaseLLM)


class TestAvailableModels:
    """Test get_available_language_models and get_available_embedding_models functions."""

    def test_get_available_language_models_invalid_provider(self):
        """Test error for invalid provider."""
        with pytest.raises(ValueError, match="Provider 'invalid' not supported"):
            from rhesis.sdk.models.factory import get_available_language_models

            get_available_language_models("invalid")

    def test_get_available_embedding_models_invalid_provider(self):
        """Test error for invalid provider."""
        with pytest.raises(ValueError, match="Embedding provider 'invalid' not supported"):
            from rhesis.sdk.models.factory import get_available_embedding_models

            get_available_embedding_models("invalid")

    def test_get_available_embedding_models_no_support(self):
        """Test error when provider doesn't support embeddings."""
        with pytest.raises(ValueError, match="does not support embedding models"):
            from rhesis.sdk.models.factory import get_available_embedding_models

            get_available_embedding_models("anthropic")
