from unittest.mock import Mock, patch

import pytest

from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.models.factory import (
    DEFAULT_MODELS,
    DEFAULT_PROVIDER,
    ModelConfig,
    get_available_embedding_models,
    get_available_llm_models,
    get_model,
)


class TestModelConfig:
    """Test the ModelConfig dataclass."""

    def test_model_config_defaults(self):
        """Test ModelConfig with default values."""
        config = ModelConfig()
        assert config.provider is None
        assert config.model_name is None
        assert config.api_key is None
        assert config.extra_params == {}

    def test_model_config_with_values(self):
        """Test ModelConfig with provided values."""
        config = ModelConfig(
            provider="test-provider",
            model_name="test-model",
            api_key="test-key",
            extra_params={"temperature": 0.5},
        )
        assert config.provider == "test-provider"
        assert config.model_name == "test-model"
        assert config.api_key == "test-key"
        assert config.extra_params == {"temperature": 0.5}

    def test_model_config_extra_params_default_factory(self):
        """Test that extra_params uses default_factory correctly."""
        config1 = ModelConfig()
        config2 = ModelConfig()

        # Modify one config's extra_params
        config1.extra_params["test"] = "value"

        # The other should remain unchanged
        assert config2.extra_params == {}


class TestGetModel:
    """Test the get_model function with various configurations."""

    @patch("rhesis.sdk.models.providers.native.RhesisLLM")
    def test_get_model_minimal_defaults(self, mock_rhesis_class):
        """Test get_model() with no parameters - uses all defaults."""
        mock_instance = Mock(spec=BaseLLM)
        mock_rhesis_class.return_value = mock_instance

        result = get_model()

        # Should use default provider and model
        mock_rhesis_class.assert_called_once_with(
            model_name=DEFAULT_MODELS[DEFAULT_PROVIDER], api_key=None
        )
        assert result == mock_instance

    @patch("rhesis.sdk.models.providers.native.RhesisLLM")
    def test_get_model_provider_only(self, mock_rhesis_class):
        """Test get_model("rhesis") - uses default model for provider."""
        mock_instance = Mock(spec=BaseLLM)
        mock_rhesis_class.return_value = mock_instance

        result = get_model("rhesis")

        mock_rhesis_class.assert_called_once_with(model_name=DEFAULT_MODELS["rhesis"], api_key=None)
        assert result == mock_instance

    @patch("rhesis.sdk.models.providers.native.RhesisLLM")
    def test_get_model_provider_and_model(self, mock_rhesis_class):
        """Test get_model("rhesis", "custom-model") - specific provider and model."""
        mock_instance = Mock(spec=BaseLLM)
        mock_rhesis_class.return_value = mock_instance

        result = get_model("rhesis", "custom-model")

        mock_rhesis_class.assert_called_once_with(model_name="custom-model", api_key=None)
        assert result == mock_instance

    @patch("rhesis.sdk.models.providers.native.RhesisLLM")
    def test_get_model_with_api_key(self, mock_rhesis_class):
        """Test get_model with API key."""
        mock_instance = Mock(spec=BaseLLM)
        mock_rhesis_class.return_value = mock_instance

        result = get_model("rhesis", "test-model", "test-api-key")

        mock_rhesis_class.assert_called_once_with(model_name="test-model", api_key="test-api-key")
        assert result == mock_instance

    @patch("rhesis.sdk.models.providers.native.RhesisLLM")
    def test_get_model_shorthand_provider_model(self, mock_rhesis_class):
        """Test get_model("rhesis/custom-model") - shorthand notation."""
        mock_instance = Mock(spec=BaseLLM)
        mock_rhesis_class.return_value = mock_instance

        result = get_model("rhesis/custom-model")

        mock_rhesis_class.assert_called_once_with(model_name="custom-model", api_key=None)
        assert result == mock_instance

    @patch("rhesis.sdk.models.providers.native.RhesisLLM")
    def test_get_model_with_config_object(self, mock_rhesis_class):
        """Test get_model(config=ModelConfig(...))."""
        mock_instance = Mock(spec=BaseLLM)
        mock_rhesis_class.return_value = mock_instance

        config = ModelConfig(provider="rhesis", model_name="config-model", api_key="config-key")

        result = get_model(config=config)

        mock_rhesis_class.assert_called_once_with(model_name="config-model", api_key="config-key")
        assert result == mock_instance

    @patch("rhesis.sdk.models.providers.native.RhesisLLM")
    def test_get_model_config_with_kwargs_override(self, mock_rhesis_class):
        """Test that kwargs override config values."""
        mock_instance = Mock(spec=BaseLLM)
        mock_rhesis_class.return_value = mock_instance

        config = ModelConfig(provider="rhesis", model_name="config-model", api_key="config-key")

        result = get_model(config=config, model_name="override-model")

        mock_rhesis_class.assert_called_once_with(model_name="override-model", api_key="config-key")
        assert result == mock_instance

    @patch("rhesis.sdk.models.providers.gemini.GeminiLLM")
    def test_get_model_gemini(self, mock_gemini_class):
        """Test get_model with gemini provider."""
        mock_instance = Mock(spec=BaseLLM)
        mock_gemini_class.return_value = mock_instance

        result = get_model("gemini", "gemini-model")

        mock_gemini_class.assert_called_once_with(model_name="gemini-model", api_key=None)
        assert result == mock_instance

    @patch("rhesis.sdk.models.providers.gemini.GeminiLLM")
    def test_get_model_gemini_with_default(self, mock_gemini_class):
        """Test get_model with gemini provider using default model."""
        mock_instance = Mock(spec=BaseLLM)
        mock_gemini_class.return_value = mock_instance

        result = get_model("gemini")

        mock_gemini_class.assert_called_once_with(model_name=DEFAULT_MODELS["gemini"], api_key=None)
        assert result == mock_instance

    @patch("rhesis.sdk.models.providers.openrouter.OpenRouterLLM")
    def test_get_model_openrouter(self, mock_openrouter_class):
        """Test get_model with openrouter provider."""
        mock_instance = Mock(spec=BaseLLM)
        mock_openrouter_class.return_value = mock_instance

        result = get_model("openrouter", "anthropic/claude-3.5-sonnet")

        mock_openrouter_class.assert_called_once_with(
            model_name="anthropic/claude-3.5-sonnet", api_key=None
        )
        assert result == mock_instance

    @patch("rhesis.sdk.models.providers.openrouter.OpenRouterLLM")
    def test_get_model_openrouter_with_default(self, mock_openrouter_class):
        """Test get_model with openrouter provider using default model."""
        mock_instance = Mock(spec=BaseLLM)
        mock_openrouter_class.return_value = mock_instance

        result = get_model("openrouter")

        mock_openrouter_class.assert_called_once_with(
            model_name=DEFAULT_MODELS["openrouter"], api_key=None
        )
        assert result == mock_instance

    @patch("rhesis.sdk.models.providers.openrouter.OpenRouterLLM")
    def test_get_model_openrouter_shorthand(self, mock_openrouter_class):
        """Test get_model with openrouter shorthand syntax."""
        mock_instance = Mock(spec=BaseLLM)
        mock_openrouter_class.return_value = mock_instance

        result = get_model("openrouter/meta-llama/llama-3.1-8b-instruct")

        mock_openrouter_class.assert_called_once_with(
            model_name="meta-llama/llama-3.1-8b-instruct", api_key=None
        )
        assert result == mock_instance

    @patch("rhesis.sdk.models.providers.vertex_ai.VertexAILLM")
    def test_get_model_vertex_ai(self, mock_vertex_ai_class):
        """Test get_model with vertex_ai provider."""
        mock_instance = Mock(spec=BaseLLM)
        mock_vertex_ai_class.return_value = mock_instance

        result = get_model("vertex_ai", "gemini-2.5-flash")

        mock_vertex_ai_class.assert_called_once_with(model_name="gemini-2.5-flash")
        assert result == mock_instance

    @patch("rhesis.sdk.models.providers.vertex_ai.VertexAILLM")
    def test_get_model_vertex_ai_with_default(self, mock_vertex_ai_class):
        """Test get_model with vertex_ai provider using default model."""
        mock_instance = Mock(spec=BaseLLM)
        mock_vertex_ai_class.return_value = mock_instance

        result = get_model("vertex_ai")

        mock_vertex_ai_class.assert_called_once_with(model_name=DEFAULT_MODELS["vertex_ai"])
        assert result == mock_instance

    @patch("rhesis.sdk.models.providers.vertex_ai.VertexAILLM")
    def test_get_model_vertex_ai_shorthand(self, mock_vertex_ai_class):
        """Test get_model with vertex_ai shorthand syntax."""
        mock_instance = Mock(spec=BaseLLM)
        mock_vertex_ai_class.return_value = mock_instance

        result = get_model("vertex_ai/gemini-2.0-flash")

        mock_vertex_ai_class.assert_called_once_with(model_name="gemini-2.0-flash")
        assert result == mock_instance

    def test_get_model_unsupported_provider(self):
        """Test get_model with unsupported provider raises ValueError."""
        with pytest.raises(ValueError, match="Provider unsupported-provider not supported"):
            get_model("unsupported-provider")

    def test_get_model_unsupported_provider_from_config(self):
        """Test get_model with unsupported provider from config raises ValueError."""
        config = ModelConfig(provider="unsupported-provider")

        with pytest.raises(ValueError, match="Provider unsupported-provider not supported"):
            get_model(config=config)

    @patch("rhesis.sdk.models.providers.native.RhesisLLM")
    def test_get_model_priority_order(self, mock_rhesis_class):
        """Test that parameter priority is correct: kwargs > config > defaults."""
        mock_instance = Mock(spec=BaseLLM)
        mock_rhesis_class.return_value = mock_instance

        config = ModelConfig(provider="rhesis", model_name="config-model", api_key="config-key")

        # kwargs should override config
        result = get_model(
            config=config,
            provider="rhesis",
            model_name="kwargs-model",
            api_key="kwargs-key",
        )

        mock_rhesis_class.assert_called_once_with(model_name="kwargs-model", api_key="kwargs-key")
        assert result == mock_instance

    @patch("rhesis.sdk.models.providers.native.RhesisLLM")
    def test_get_model_none_values_use_defaults(self, mock_rhesis_class):
        """Test that None values fall back to defaults."""
        mock_instance = Mock(spec=BaseLLM)
        mock_rhesis_class.return_value = mock_instance

        result = get_model(None, None, None)

        mock_rhesis_class.assert_called_once_with(
            model_name=DEFAULT_MODELS[DEFAULT_PROVIDER], api_key=None
        )
        assert result == mock_instance

    @patch("rhesis.sdk.models.providers.native.RhesisLLM")
    def test_get_model_empty_string_provider(self, mock_rhesis_class):
        """Test get_model with empty string provider - should use default."""
        mock_instance = Mock(spec=BaseLLM)
        mock_rhesis_class.return_value = mock_instance

        result = get_model("", "test-model")

        mock_rhesis_class.assert_called_once_with(model_name="test-model", api_key=None)
        assert result == mock_instance

    @patch("rhesis.sdk.models.providers.native.RhesisLLM")
    def test_get_model_extra_params_passed_through(self, mock_rhesis_class):
        """Test that extra parameters are passed through to the provider."""
        mock_instance = Mock(spec=BaseLLM)
        mock_rhesis_class.return_value = mock_instance

        # Note: The current implementation doesn't pass extra_params to providers
        # This test documents the current behavior
        result = get_model("rhesis", "test-model", extra_params={"temperature": 0.5})

        mock_rhesis_class.assert_called_once_with(
            model_name="test-model", api_key=None, extra_params={"temperature": 0.5}
        )
        assert result == mock_instance


class TestModelFactoryIntegration:
    """Integration tests for the model factory."""

    @patch("rhesis.sdk.models.providers.native.RhesisLLM")
    def test_rhesis_integration(self, mock_rhesis_class):
        """Test full integration with rhesis provider."""
        mock_instance = Mock(spec=BaseLLM)
        mock_rhesis_class.return_value = mock_instance

        # Test all creation methods for rhesis
        models = [
            get_model(),  # defaults
            get_model("rhesis"),  # provider only
            get_model("rhesis", "custom-model"),  # provider + model
            get_model("rhesis/custom-model"),  # shorthand
            get_model(config=ModelConfig(provider="rhesis", model_name="custom-model")),  # config
        ]

        assert all(isinstance(model, Mock) for model in models)
        assert mock_rhesis_class.call_count == 5

    @patch("rhesis.sdk.models.providers.gemini.GeminiLLM")
    def test_gemini_integration(self, mock_gemini_class):
        """Test full integration with gemini provider."""
        mock_instance = Mock(spec=BaseLLM)
        mock_gemini_class.return_value = mock_instance

        # Test all creation methods for gemini
        models = [
            get_model("gemini"),  # provider only
            get_model("gemini", "custom-model"),  # provider + model
            get_model("gemini/custom-model"),  # shorthand
            get_model(config=ModelConfig(provider="gemini", model_name="custom-model")),  # config
        ]

        assert all(isinstance(model, Mock) for model in models)
        assert mock_gemini_class.call_count == 4

    @patch("rhesis.sdk.models.providers.openrouter.OpenRouterLLM")
    def test_openrouter_integration(self, mock_openrouter_class):
        """Test full integration with openrouter provider."""
        mock_instance = Mock(spec=BaseLLM)
        mock_openrouter_class.return_value = mock_instance

        # Test all creation methods for openrouter
        models = [
            get_model("openrouter"),  # provider only
            get_model("openrouter", "anthropic/claude-3.5-sonnet"),  # provider + model
            get_model("openrouter/anthropic/claude-3.5-sonnet"),  # shorthand
            get_model(
                config=ModelConfig(
                    provider="openrouter", model_name="anthropic/claude-3.5-sonnet"
                )
            ),  # config
        ]

        assert all(isinstance(model, Mock) for model in models)
        assert mock_openrouter_class.call_count == 4

    @patch("rhesis.sdk.models.providers.vertex_ai.VertexAILLM")
    def test_vertex_ai_integration(self, mock_vertex_ai_class):
        """Test full integration with vertex_ai provider."""
        mock_instance = Mock(spec=BaseLLM)
        mock_vertex_ai_class.return_value = mock_instance

        # Test all creation methods for vertex_ai
        models = [
            get_model("vertex_ai"),  # provider only
            get_model("vertex_ai", "custom-model"),  # provider + model
            get_model("vertex_ai/custom-model"),  # shorthand
            get_model(
                config=ModelConfig(provider="vertex_ai", model_name="custom-model")
            ),  # config
        ]

        assert all(isinstance(model, Mock) for model in models)
        assert mock_vertex_ai_class.call_count == 4


class TestModelFactoryEdgeCases:
    """Test edge cases and error conditions."""

    def test_get_model_with_invalid_config_type(self):
        """Test get_model with invalid config type."""
        with pytest.raises(AttributeError):
            get_model(config="not-a-config-object")

    @patch("rhesis.sdk.models.providers.native.RhesisLLM")
    def test_get_model_with_very_long_model_name(self, mock_rhesis_class):
        """Test get_model with very long model name."""
        mock_instance = Mock(spec=BaseLLM)
        mock_rhesis_class.return_value = mock_instance

        long_name = "a" * 1000
        result = get_model("rhesis", long_name)

        mock_rhesis_class.assert_called_once_with(model_name=long_name, api_key=None)
        assert result == mock_instance

    @patch("rhesis.sdk.models.providers.native.RhesisLLM")
    def test_get_model_with_special_characters(self, mock_rhesis_class):
        """Test get_model with special characters in model name."""
        mock_instance = Mock(spec=BaseLLM)
        mock_rhesis_class.return_value = mock_instance

        special_name = "model-with-special-chars!@#$%^&*()"
        result = get_model("rhesis", special_name)

        mock_rhesis_class.assert_called_once_with(model_name=special_name, api_key=None)
        assert result == mock_instance

    def test_get_model_provider_case_sensitivity(self):
        """Test that provider names are case-sensitive."""
        # This test documents current behavior - providers are case-sensitive
        with pytest.raises(ValueError, match="Provider Rhesis not supported"):
            get_model("Rhesis")

    @patch("rhesis.sdk.models.providers.native.RhesisLLM")
    def test_get_model_api_key_none_vs_empty_string(self, mock_rhesis_class):
        """Test that None and empty string API keys are handled the same."""
        mock_instance = Mock(spec=BaseLLM)
        mock_rhesis_class.return_value = mock_instance

        # Both should result in api_key=None being passed
        get_model("rhesis", "test-model", None)
        get_model("rhesis", "test-model", "")

        expected_calls = [
            (({"model_name": "test-model", "api_key": None}),),
            (({"model_name": "test-model", "api_key": None}),),
        ]

        assert mock_rhesis_class.call_args_list == expected_calls


class TestGetAvailableLLMModels:
    """Test the get_available_llm_models function."""

    @patch("rhesis.sdk.models.providers.openai.OpenAILLM.get_available_models")
    def test_get_available_llm_models_openai(self, mock_get_models):
        """Test getting available LLM models for OpenAI."""
        mock_get_models.return_value = ["gpt-4", "gpt-3.5-turbo", "gpt-4-turbo"]

        models = get_available_llm_models("openai")

        assert models == ["gpt-4", "gpt-3.5-turbo", "gpt-4-turbo"]
        mock_get_models.assert_called_once()

    @patch("rhesis.sdk.models.providers.gemini.GeminiLLM.get_available_models")
    def test_get_available_llm_models_gemini(self, mock_get_models):
        """Test getting available LLM models for Gemini."""
        mock_get_models.return_value = ["gemini-2.0-flash", "gemini-2.5-flash"]

        models = get_available_llm_models("gemini")

        assert models == ["gemini-2.0-flash", "gemini-2.5-flash"]
        mock_get_models.assert_called_once()

    def test_get_available_llm_models_unsupported_provider(self):
        """Test getting models for unsupported provider raises ValueError."""
        with pytest.raises(ValueError, match="Provider 'unsupported' not supported"):
            get_available_llm_models("unsupported")

    def test_get_available_llm_models_non_litellm_provider(self):
        """Test getting models for provider that doesn't support listing."""
        with pytest.raises(
            ValueError, match="Provider 'rhesis' does not support listing available models"
        ):
            get_available_llm_models("rhesis")


class TestGetAvailableEmbeddingModels:
    """Test the get_available_embedding_models function."""

    @patch("rhesis.sdk.models.providers.openai.OpenAIEmbedder.get_available_models")
    def test_get_available_embedding_models_openai(self, mock_get_models):
        """Test getting available embedding models for OpenAI."""
        mock_get_models.return_value = [
            "text-embedding-3-small",
            "text-embedding-3-large",
            "text-embedding-ada-002",
        ]

        models = get_available_embedding_models("openai")

        assert models == [
            "text-embedding-3-small",
            "text-embedding-3-large",
            "text-embedding-ada-002",
        ]
        mock_get_models.assert_called_once()

    @patch("rhesis.sdk.models.providers.gemini.GeminiEmbedder.get_available_models")
    def test_get_available_embedding_models_gemini(self, mock_get_models):
        """Test getting available embedding models for Gemini."""
        mock_get_models.return_value = ["text-embedding-004", "gemini-embedding-001"]

        models = get_available_embedding_models("gemini")

        assert models == ["text-embedding-004", "gemini-embedding-001"]
        mock_get_models.assert_called_once()

    @patch("rhesis.sdk.models.providers.vertex_ai.VertexAIEmbedder.get_available_models")
    def test_get_available_embedding_models_vertex_ai(self, mock_get_models):
        """Test getting available embedding models for Vertex AI."""
        mock_get_models.return_value = ["text-embedding-005", "text-embedding-004"]

        models = get_available_embedding_models("vertex_ai")

        assert models == ["text-embedding-005", "text-embedding-004"]
        mock_get_models.assert_called_once()

    def test_get_available_embedding_models_unsupported_provider(self):
        """Test getting embedding models for unsupported provider raises ValueError."""
        with pytest.raises(ValueError, match="Embedding provider 'unsupported' not supported"):
            get_available_embedding_models("unsupported")

    def test_get_available_embedding_models_non_embedding_provider(self):
        """Test getting embedding models for provider that doesn't support embeddings."""
        with pytest.raises(ValueError, match="Embedding provider 'anthropic' not supported"):
            get_available_embedding_models("anthropic")
