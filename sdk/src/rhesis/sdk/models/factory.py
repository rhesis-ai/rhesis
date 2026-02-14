"""
Model Factory for Rhesis SDK

This module provides a simple and intuitive way to create language model instances
and embedding model instances with smart defaults and comprehensive error handling.

"""

from dataclasses import dataclass, field
from typing import Callable, Dict, Optional

from rhesis.sdk.models.base import BaseEmbedder, BaseLLM

# Default configuration
DEFAULT_PROVIDER = "rhesis"
DEFAULT_MODELS = {
    "rhesis": "rhesis-default",
    "anthropic": "claude-4",
    "cohere": "command-r-plus",
    "gemini": "gemini-2.0-flash",
    "groq": "llama3-8b-8192",
    "huggingface": "meta-llama/Llama-2-7b-chat-hf",
    "lmformatenforcer": "meta-llama/Llama-2-7b-chat-hf",
    "meta_llama": "Llama-3.3-70B-Instruct",
    "mistral": "mistral-medium-latest",
    "ollama": "llama3.1",
    "openai": "gpt-4o",
    "openrouter": "openai/gpt-4o-mini",
    "perplexity": "sonar-pro",
    "polyphemus": "",  # Polyphemus uses API's default model
    "replicate": "llama-2-70b-chat",
    "together_ai": "togethercomputer/llama-2-70b-chat",
    "vertex_ai": "gemini-2.0-flash",  # Best performance - avoid 2.5-flash
}

# Default embedding models per provider
DEFAULT_EMBEDDING_MODEL_PROVIDER = "openai"
DEFAULT_EMBEDDING_MODELS = {
    "openai": "text-embedding-3-small",
    "gemini": "gemini-embedding-001",
    "vertex_ai": "text-embedding-005",
}


# Factory functions for each provider, the are used to create the model instance and
# avoid circular imports


def _create_rhesis_llm(model_name: str, api_key: Optional[str], **kwargs) -> BaseLLM:
    """Factory function for RhesisLLM."""
    from rhesis.sdk.models.providers.native import RhesisLLM

    return RhesisLLM(model_name=model_name, api_key=api_key, **kwargs)


def _create_gemini_llm(model_name: str, api_key: Optional[str], **kwargs) -> BaseLLM:
    """Factory function for GeminiLLM."""
    from rhesis.sdk.models.providers.gemini import GeminiLLM

    return GeminiLLM(model_name=model_name, api_key=api_key, **kwargs)


def _create_ollama_llm(model_name: str, api_key: Optional[str], **kwargs) -> BaseLLM:
    """Factory function for OllamaLLM."""
    from rhesis.sdk.models.providers.ollama import OllamaLLM

    return OllamaLLM(model_name=model_name, **kwargs)


def _create_openai_llm(model_name: str, api_key: Optional[str], **kwargs) -> BaseLLM:
    """Factory function for OpenAILLM."""
    from rhesis.sdk.models.providers.openai import OpenAILLM

    return OpenAILLM(model_name=model_name, api_key=api_key)


def _create_vertex_ai_llm(model_name: str, api_key: Optional[str], **kwargs) -> BaseLLM:
    """Factory function for VertexAILLM."""
    from rhesis.sdk.models.providers.vertex_ai import VertexAILLM

    # Note: api_key is ignored for Vertex AI as it uses service account credentials
    return VertexAILLM(model_name=model_name, **kwargs)


def _create_anthropic_llm(model_name: str, api_key: Optional[str], **kwargs) -> BaseLLM:
    """Factory function for AnthropicLLM."""
    from rhesis.sdk.models.providers.anthropic import AnthropicLLM

    return AnthropicLLM(model_name=model_name, api_key=api_key, **kwargs)


def _create_cohere_llm(model_name: str, api_key: Optional[str], **kwargs) -> BaseLLM:
    """Factory function for CohereLLM."""
    from rhesis.sdk.models.providers.cohere import CohereLLM

    return CohereLLM(model_name=model_name, api_key=api_key, **kwargs)


def _create_groq_llm(model_name: str, api_key: Optional[str], **kwargs) -> BaseLLM:
    """Factory function for GroqLLM."""
    from rhesis.sdk.models.providers.groq import GroqLLM

    return GroqLLM(model_name=model_name, api_key=api_key, **kwargs)


def _create_huggingface_llm(model_name: str, api_key: Optional[str], **kwargs) -> BaseLLM:
    """Factory function for HuggingFaceLLM."""
    from rhesis.sdk.models.providers.huggingface import HuggingFaceLLM

    # Note: api_key is ignored for HuggingFace as it uses local models
    return HuggingFaceLLM(model_name=model_name, **kwargs)


def _create_lmformatenforcer_llm(model_name: str, api_key: Optional[str], **kwargs) -> BaseLLM:
    """Factory function for LMFormatEnforcerLLM."""
    from rhesis.sdk.models.providers.lmformatenforcer import LMFormatEnforcerLLM

    # Note: api_key is ignored for LMFormatEnforcer as it uses local models
    return LMFormatEnforcerLLM(model_name=model_name, **kwargs)


def _create_meta_llama_llm(model_name: str, api_key: Optional[str], **kwargs) -> BaseLLM:
    """Factory function for MetaLlamaLLM."""
    from rhesis.sdk.models.providers.meta_llama import MetaLlamaLLM

    return MetaLlamaLLM(model_name=model_name, api_key=api_key, **kwargs)


def _create_mistral_llm(model_name: str, api_key: Optional[str], **kwargs) -> BaseLLM:
    """Factory function for MistralLLM."""
    from rhesis.sdk.models.providers.mistral import MistralLLM

    return MistralLLM(model_name=model_name, api_key=api_key, **kwargs)


def _create_perplexity_llm(model_name: str, api_key: Optional[str], **kwargs) -> BaseLLM:
    """Factory function for PerplexityLLM."""
    from rhesis.sdk.models.providers.perplexity import PerplexityLLM

    return PerplexityLLM(model_name=model_name, api_key=api_key, **kwargs)


def _create_replicate_llm(model_name: str, api_key: Optional[str], **kwargs) -> BaseLLM:
    """Factory function for ReplicateLLM."""
    from rhesis.sdk.models.providers.replicate import ReplicateLLM

    return ReplicateLLM(model_name=model_name, api_key=api_key, **kwargs)


def _create_together_ai_llm(model_name: str, api_key: Optional[str], **kwargs) -> BaseLLM:
    """Factory function for TogetherAILLM."""
    from rhesis.sdk.models.providers.together_ai import TogetherAILLM

    return TogetherAILLM(model_name=model_name, api_key=api_key, **kwargs)


def _create_openrouter_llm(model_name: str, api_key: Optional[str], **kwargs) -> BaseLLM:
    """Factory function for OpenRouterLLM."""
    from rhesis.sdk.models.providers.openrouter import OpenRouterLLM

    return OpenRouterLLM(model_name=model_name, api_key=api_key, **kwargs)


def _create_polyphemus_llm(model_name: str, api_key: Optional[str], **kwargs) -> BaseLLM:
    """Factory function for PolyphemusLLM."""
    from rhesis.sdk.models.providers.polyphemus import PolyphemusLLM

    return PolyphemusLLM(model_name=model_name, api_key=api_key, **kwargs)


# Provider registry mapping provider names to their factory functions
PROVIDER_REGISTRY: Dict[str, Callable[[str, Optional[str]], BaseLLM]] = {
    "rhesis": _create_rhesis_llm,
    "anthropic": _create_anthropic_llm,
    "cohere": _create_cohere_llm,
    "gemini": _create_gemini_llm,
    "groq": _create_groq_llm,
    "huggingface": _create_huggingface_llm,
    "lmformatenforcer": _create_lmformatenforcer_llm,
    "meta_llama": _create_meta_llama_llm,
    "mistral": _create_mistral_llm,
    "ollama": _create_ollama_llm,
    "openai": _create_openai_llm,
    "openrouter": _create_openrouter_llm,
    "perplexity": _create_perplexity_llm,
    "polyphemus": _create_polyphemus_llm,
    "replicate": _create_replicate_llm,
    "together_ai": _create_together_ai_llm,
    "vertex_ai": _create_vertex_ai_llm,
}


@dataclass
class LanguageModelConfig:
    """Configuration for a language model instance.

    Args:
        provider: The provider name (e.g., "rhesis", "anthropic", "gemini", "openai", "ollama")
        model_name: Specific model name (E.g gpt-4o, gemini-2.0-flash, claude-4, etc)
        api_key: The API key to use for the model.
        extra_params: Extra parameters to pass to the model.
    """

    provider: str | None = None
    model_name: str | None = None
    api_key: str | None = None
    extra_params: dict = field(default_factory=dict)


# Deprecated alias for backward compatibility
ModelConfig = LanguageModelConfig


def get_language_model(
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
    config: Optional[LanguageModelConfig] = None,
    **kwargs,
) -> BaseLLM:
    """Create a language model instance with smart defaults and comprehensive error handling.

    This function provides multiple ways to create a language model instance:

    1. **Minimal**: `get_language_model()` - uses all defaults
    2. **Provider only**: `get_language_model("rhesis")` - uses default model for provider
    3. **Provider + Model**: `get_language_model("rhesis", "rhesis-llm-v1")`
    4. **Shorthand**: `get_language_model("rhesis/rhesis-llm-v1")`
    5. **Full config**: `get_language_model(config=LanguageModelConfig(...))`

    Args:
        provider: Provider name (e.g., "rhesis", "anthropic", "gemini", "openai",
            "mistral", "ollama")
        model_name: Specific model name
        api_key: API key for authentication
        config: Complete configuration object
        **kwargs: Additional parameters passed to LanguageModelConfig

    Returns:
        BaseLLM: Configured language model instance

    Raises:
        ValueError: If configuration is invalid or provider not supported
        ImportError: If required dependencies are missing

    Examples:
        >>> # Basic usage with defaults
        >>> model = get_language_model()

        >>> # Specify provider and model
        >>> model = get_language_model("rhesis", "rhesis-llm-v1")

        >>> # Use provider/model shorthand
        >>> model = get_language_model("rhesis/rhesis-llm-v1")

        >>> # Use different providers
        >>> model = get_language_model("anthropic", "claude-4")
        >>> model = get_language_model("openai", "gpt-4o")
        >>> model = get_language_model("mistral/mistral-medium-latest")

        >>> # With custom configuration
        >>> config = LanguageModelConfig(
        ...     provider="gemini",
        ...     model_name="gemini-pro",
        ...     api_key="your-api-key"
        ... )
        >>> model = get_language_model(config=config)

        >>> # With extra parameters
        >>> model = get_language_model(
        ...     "rhesis",
        ...     "rhesis-llm-v1",
        ...     extra_params={"temperature": 0.5}
        ... )
    """

    # Create configuration
    if config:
        # Update config with any additional parameters
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)
        cfg = config
    else:
        cfg = LanguageModelConfig()
    # Case: shorthand string like "provider/model"
    if provider and "/" in provider and model_name is None:
        # split only first "/" so that names like "rhesis/rhesis-default" still work
        prov, model = provider.split("/", 1)
        provider, model_name = prov, model

    provider = provider or cfg.provider or DEFAULT_PROVIDER
    if provider not in DEFAULT_MODELS.keys():
        raise ValueError(f"Provider {provider} not supported")
    model_name = model_name or cfg.model_name or DEFAULT_MODELS[provider]
    api_key = api_key or cfg.api_key

    config = LanguageModelConfig(provider=provider, model_name=model_name, api_key=api_key)

    # Get the factory function for the provider
    factory_func = PROVIDER_REGISTRY.get(config.provider)
    if factory_func is None:
        raise ValueError(f"Provider {config.provider} not supported")

    # Use the factory function to create the model instance
    return factory_func(config.model_name, config.api_key, **kwargs)


# Deprecated alias for backward compatibility
def get_model(
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
    config: Optional[LanguageModelConfig] = None,
    **kwargs,
) -> BaseLLM:
    """Deprecated: Use get_language_model() instead.

    This function is kept for backward compatibility and will be removed in a future version.
    """
    return get_language_model(provider, model_name, api_key, config, **kwargs)


def get_available_language_models(provider: str) -> list[str]:
    """Get the list of available language models for a specific provider.

    This function retrieves the available language models by calling the provider class's
    get_available_models() method. It supports all LiteLLM-based providers.

    Args:
        provider: Provider name (e.g., "anthropic", "openai", "gemini", "groq")

    Returns:
        List of available language model names for the provider

    Raises:
        ValueError: If the provider is not supported or doesn't support listing models
        ImportError: If required dependencies for the provider are missing

    Examples:
        >>> # Get Anthropic models
        >>> models = get_available_language_models("anthropic")
        >>> print(models)
        ['claude-3-5-sonnet-20241022', 'claude-3-5-haiku-20241022', ...]

        >>> # Get OpenAI models
        >>> models = get_available_language_models("openai")

        >>> # Get Gemini models
        >>> models = get_available_language_models("gemini")
    """
    if provider not in PROVIDER_REGISTRY:
        available_providers = ", ".join(sorted(PROVIDER_REGISTRY.keys()))
        raise ValueError(
            f"Provider '{provider}' not supported. Available providers: {available_providers}"
        )

    # Map of providers that support get_available_models (LiteLLM-based providers)
    litellm_providers = {
        "anthropic": _get_anthropic_models,
        "cohere": _get_cohere_models,
        "gemini": _get_gemini_models,
        "groq": _get_groq_models,
        "meta_llama": _get_meta_llama_models,
        "mistral": _get_mistral_models,
        "ollama": _get_ollama_models,
        "openai": _get_openai_models,
        "openrouter": _get_openrouter_models,
        "perplexity": _get_perplexity_models,
        "replicate": _get_replicate_models,
        "together_ai": _get_together_ai_models,
        "vertex_ai": _get_vertex_ai_models,
    }

    if provider not in litellm_providers:
        raise ValueError(
            f"Provider '{provider}' does not support listing available models. "
            f"Only the following providers support this feature: "
            f"{', '.join(sorted(litellm_providers.keys()))}"
        )

    # Call the provider-specific function to get models
    return litellm_providers[provider]()


def get_available_embedding_models(provider: str) -> list[str]:
    """Get the list of available embedding models for a specific provider.

    This function retrieves available embedding models by calling the provider's
    embedder class get_available_models() method. It supports OpenAI, Gemini,
    and Vertex AI providers.

    Args:
        provider: Provider name (e.g., "openai", "gemini", "vertex_ai")

    Returns:
        List of available embedding model names for the provider

    Raises:
        ValueError: If the provider is not supported or doesn't support embeddings
        ImportError: If required dependencies for the provider are missing

    Examples:
        >>> # Get OpenAI embedding models
        >>> models = get_available_embedding_models("openai")
        >>> print(models)
        ['text-embedding-3-small', 'text-embedding-3-large', 'text-embedding-ada-002']

        >>> # Get Gemini embedding models
        >>> models = get_available_embedding_models("gemini")

        >>> # Get Vertex AI embedding models
        >>> models = get_available_embedding_models("vertex_ai")
    """
    if provider not in EMBEDDING_MODEL_REGISTRY:
        available_providers = ", ".join(sorted(EMBEDDING_MODEL_REGISTRY.keys()))
        raise ValueError(
            f"Embedding provider '{provider}' not supported. "
            f"Available embedding providers: {available_providers}"
        )

    # Map of providers that support embedding model listing
    embedding_model_providers = {
        "openai": _get_openai_embedding_models,
        "gemini": _get_gemini_embedding_models,
        "vertex_ai": _get_vertex_ai_embedding_models,
    }

    if provider not in embedding_model_providers:
        raise ValueError(
            f"Provider '{provider}' does not support listing available embedding models. "
            f"Only the following providers support this feature: "
            f"{', '.join(sorted(embedding_model_providers.keys()))}"
        )

    # Call the provider-specific function to get embedding models
    return embedding_model_providers[provider]()


# Provider-specific functions to get available embedding models
def _get_openai_embedding_models() -> list[str]:
    """Get available OpenAI embedding models."""
    from rhesis.sdk.models.providers.openai import OpenAIEmbedder

    return OpenAIEmbedder.get_available_models()


def _get_gemini_embedding_models() -> list[str]:
    """Get available Gemini embedding models."""
    from rhesis.sdk.models.providers.gemini import GeminiEmbedder

    return GeminiEmbedder.get_available_models()


def _get_vertex_ai_embedding_models() -> list[str]:
    """Get available Vertex AI embedding models."""
    from rhesis.sdk.models.providers.vertex_ai import VertexAIEmbedder

    return VertexAIEmbedder.get_available_models()


# Provider-specific functions to get available models
def _get_anthropic_models() -> list[str]:
    """Get available Anthropic models."""
    from rhesis.sdk.models.providers.anthropic import AnthropicLLM

    return AnthropicLLM.get_available_models()


def _get_cohere_models() -> list[str]:
    """Get available Cohere models."""
    from rhesis.sdk.models.providers.cohere import CohereLLM

    return CohereLLM.get_available_models()


def _get_gemini_models() -> list[str]:
    """Get available Gemini models."""
    from rhesis.sdk.models.providers.gemini import GeminiLLM

    return GeminiLLM.get_available_models()


def _get_groq_models() -> list[str]:
    """Get available Groq models."""
    from rhesis.sdk.models.providers.groq import GroqLLM

    return GroqLLM.get_available_models()


def _get_meta_llama_models() -> list[str]:
    """Get available Meta Llama models."""
    from rhesis.sdk.models.providers.meta_llama import MetaLlamaLLM

    return MetaLlamaLLM.get_available_models()


def _get_mistral_models() -> list[str]:
    """Get available Mistral models."""
    from rhesis.sdk.models.providers.mistral import MistralLLM

    return MistralLLM.get_available_models()


def _get_ollama_models() -> list[str]:
    """Get available Ollama models."""
    from rhesis.sdk.models.providers.ollama import OllamaLLM

    return OllamaLLM.get_available_models()


def _get_openai_models() -> list[str]:
    """Get available OpenAI models."""
    from rhesis.sdk.models.providers.openai import OpenAILLM

    return OpenAILLM.get_available_models()


def _get_perplexity_models() -> list[str]:
    """Get available Perplexity models."""
    from rhesis.sdk.models.providers.perplexity import PerplexityLLM

    return PerplexityLLM.get_available_models()


def _get_replicate_models() -> list[str]:
    """Get available Replicate models."""
    from rhesis.sdk.models.providers.replicate import ReplicateLLM

    return ReplicateLLM.get_available_models()


def _get_together_ai_models() -> list[str]:
    """Get available Together AI models."""
    from rhesis.sdk.models.providers.together_ai import TogetherAILLM

    return TogetherAILLM.get_available_models()


def _get_vertex_ai_models() -> list[str]:
    """Get available Vertex AI models."""
    from rhesis.sdk.models.providers.vertex_ai import VertexAILLM

    return VertexAILLM.get_available_models()


def _get_openrouter_models() -> list[str]:
    """Get available OpenRouter models."""
    from rhesis.sdk.models.providers.openrouter import OpenRouterLLM

    return OpenRouterLLM.get_available_models()


# =============================================================================
# Embedding Model Factory
# =============================================================================


def _create_openai_embedding_model(
    model_name: str, api_key: Optional[str], dimensions: Optional[int], **kwargs
) -> BaseEmbedder:
    """Factory function for OpenAI embedding model."""
    from rhesis.sdk.models.providers.openai import OpenAIEmbedder

    return OpenAIEmbedder(model_name=model_name, api_key=api_key, dimensions=dimensions, **kwargs)


def _create_gemini_embedding_model(
    model_name: str, api_key: Optional[str], dimensions: Optional[int], **kwargs
) -> BaseEmbedder:
    """Factory function for Gemini embedding model."""
    from rhesis.sdk.models.providers.gemini import GeminiEmbedder

    return GeminiEmbedder(model_name=model_name, api_key=api_key, dimensions=dimensions, **kwargs)


def _create_vertex_ai_embedding_model(
    model_name: str, api_key: Optional[str], dimensions: Optional[int], **kwargs
) -> BaseEmbedder:
    """Factory function for Vertex AI embedding model.

    Note: api_key is ignored for Vertex AI, which uses service account credentials.
    """
    from rhesis.sdk.models.providers.vertex_ai import VertexAIEmbedder

    # Extract Vertex AI-specific parameters from kwargs
    credentials = kwargs.pop("credentials", None)
    location = kwargs.pop("location", None)
    project = kwargs.pop("project", None)

    return VertexAIEmbedder(
        model_name=model_name,
        credentials=credentials,
        location=location,
        project=project,
        dimensions=dimensions,
        **kwargs,
    )


# Embedding model provider registry
EMBEDDING_MODEL_REGISTRY: Dict[str, Callable[..., BaseEmbedder]] = {
    "openai": _create_openai_embedding_model,
    "gemini": _create_gemini_embedding_model,
    "vertex_ai": _create_vertex_ai_embedding_model,
}

# Deprecated alias for backward compatibility
EMBEDDER_REGISTRY = EMBEDDING_MODEL_REGISTRY


@dataclass
class EmbeddingModelConfig:
    """Configuration for an embedding model instance.

    Args:
        provider: The provider name (e.g., "openai").
        model_name: Specific model name (e.g., "text-embedding-3-small").
        api_key: The API key to use for the embedding model.
        dimensions: Optional embedding dimensions.
        extra_params: Extra parameters to pass to the embedding model.
    """

    provider: str | None = None
    model_name: str | None = None
    api_key: str | None = None
    dimensions: int | None = None
    extra_params: dict = field(default_factory=dict)


# Deprecated alias for backward compatibility
EmbedderConfig = EmbeddingModelConfig


def get_embedding_model(
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
    dimensions: Optional[int] = None,
    config: Optional[EmbeddingModelConfig] = None,
    **kwargs,
) -> BaseEmbedder:
    """Create an embedding model instance with smart defaults and comprehensive error handling.

    This function provides multiple ways to create an embedding model instance:

    1. **Minimal**: `get_embedding_model()` - uses all defaults (OpenAI text-embedding-3-small)
    2. **Provider only**: `get_embedding_model("openai")` - uses default model for provider
    3. **Provider + Model**: `get_embedding_model("openai", "text-embedding-3-large")`
    4. **Shorthand**: `get_embedding_model("openai/text-embedding-3-large")`
    5. **Full config**: `get_embedding_model(config=EmbeddingModelConfig(...))`

    Args:
        provider: Provider name (e.g., "openai").
        model_name: Specific embedding model name.
        api_key: API key for authentication.
        dimensions: Optional embedding dimensions (model-dependent).
        config: Complete configuration object.
        **kwargs: Additional parameters passed to the embedding model.

    Returns:
        BaseEmbedder: Configured embedding model instance.

    Raises:
        ValueError: If configuration is invalid or provider not supported.

    Examples:
        >>> # Basic usage with defaults
        >>> embedder = get_embedding_model()

        >>> # Specify provider and model
        >>> embedder = get_embedding_model("openai", "text-embedding-3-large")

        >>> # Use provider/model shorthand
        >>> embedder = get_embedding_model("openai/text-embedding-3-small")

        >>> # With dimensions
        >>> embedder = get_embedding_model("openai", dimensions=256)

        >>> # With custom configuration
        >>> config = EmbeddingModelConfig(
        ...     provider="openai",
        ...     model_name="text-embedding-3-small",
        ...     dimensions=512
        ... )
        >>> embedder = get_embedding_model(config=config)
    """
    # Create configuration
    if config:
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)
        cfg = config
    else:
        cfg = EmbeddingModelConfig()

    # Case: shorthand string like "provider/model"
    if provider and "/" in provider and model_name is None:
        prov, model = provider.split("/", 1)
        provider, model_name = prov, model

    provider = provider or cfg.provider or DEFAULT_EMBEDDING_MODEL_PROVIDER
    if provider not in DEFAULT_EMBEDDING_MODELS:
        available = ", ".join(sorted(DEFAULT_EMBEDDING_MODELS.keys()))
        raise ValueError(
            f"Embedding model provider '{provider}' not supported. Available: {available}"
        )

    model_name = model_name or cfg.model_name or DEFAULT_EMBEDDING_MODELS[provider]
    api_key = api_key or cfg.api_key
    dimensions = dimensions or cfg.dimensions

    # Get the factory function for the provider
    factory_func = EMBEDDING_MODEL_REGISTRY.get(provider)
    if factory_func is None:
        raise ValueError(f"Embedding model provider '{provider}' not supported")

    return factory_func(model_name, api_key, dimensions, **kwargs)


# Deprecated alias for backward compatibility
def get_embedder(
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
    dimensions: Optional[int] = None,
    config: Optional[EmbeddingModelConfig] = None,
    **kwargs,
) -> BaseEmbedder:
    """Deprecated: Use get_embedding_model() instead.

    This function is kept for backward compatibility and will be removed in a future version.
    """
    return get_embedding_model(provider, model_name, api_key, dimensions, config, **kwargs)
