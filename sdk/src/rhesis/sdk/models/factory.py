"""
Language Model and Embedding Model Factory for Rhesis SDK.

This module provides a unified way to create model instances with smart
defaults and comprehensive error handling.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, Literal, Optional, Union, overload

from rhesis.sdk.models.base import BaseEmbedder, BaseLLM
from rhesis.sdk.models.defaults import (
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_EMBEDDING_MODELS,
    DEFAULT_LANGUAGE_MODEL,
    DEFAULT_LANGUAGE_MODELS,
    model_name_from_id,
    parse_model_id,
)

# =============================================================================
# Model Type Classification
# =============================================================================


class ModelType(str, Enum):
    """Enum for model types."""

    LANGUAGE = "language"
    EMBEDDING = "embedding"
    IMAGE = "image"  # Reserved for future use


# Known patterns for fallback heuristics
EMBEDDING_PATTERNS = ["embedding", "embed"]
IMAGE_PATTERNS = ["dall-e", "image", "stable-diffusion"]


def _classify_model(provider: str, model_name: str) -> ModelType:
    """Determine model type from litellm metadata, falling back to heuristics.

    Args:
        provider: The model provider (e.g., "openai", "anthropic")
        model_name: The model name (e.g., "gpt-4o", "text-embedding-3-small")

    Returns:
        ModelType: The detected model type

    Strategy:
        1. Try litellm.get_model_info() for reliable metadata
        2. Fall back to name-based heuristics for custom/fine-tuned models
        3. Default to language model (most common case)
    """
    # 1. Try litellm model info (most reliable)
    try:
        import litellm

        full_name = f"{provider}/{model_name}"
        info = litellm.get_model_info(full_name)
        mode = info.get("mode", "")

        if mode == "embedding":
            return ModelType.EMBEDDING
        elif mode in ("chat", "completion"):
            return ModelType.LANGUAGE
    except Exception:
        pass  # Fall through to heuristics

    # 2. Name-based heuristics (fallback)
    name_lower = model_name.lower()
    if any(p in name_lower for p in EMBEDDING_PATTERNS):
        return ModelType.EMBEDDING
    if any(p in name_lower for p in IMAGE_PATTERNS):
        return ModelType.IMAGE

    # 3. Default to language model (most common case)
    return ModelType.LANGUAGE


# =============================================================================
# Default Configuration (unified provider/name format)
# =============================================================================
# Derived: provider part of the default (for backward compatibility)
DEFAULT_LANGUAGE_MODEL_PROVIDER = parse_model_id(DEFAULT_LANGUAGE_MODEL)[0]
DEFAULT_EMBEDDING_MODEL_PROVIDER = parse_model_id(DEFAULT_EMBEDDING_MODEL)[0]


# Factory functions for each provider, the are used to create the model instance and
# avoid circular imports


def _create_rhesis_llm(model_name: str, api_key: Optional[str], **kwargs) -> BaseLLM:
    """Factory function for RhesisLLM."""
    from rhesis.sdk.models.providers.native import RhesisLLM

    return RhesisLLM(model_name=model_name, api_key=api_key, **kwargs)


def _create_rhesis_embedding_model(
    model_name: str, api_key: Optional[str], dimensions: Optional[int], **kwargs
) -> BaseEmbedder:
    """Factory function for Rhesis embedding model."""
    from rhesis.sdk.models.providers.native import RhesisEmbedder

    return RhesisEmbedder(model_name=model_name, api_key=api_key, **kwargs)


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


# =============================================================================
# Unified Model Registry
# =============================================================================

# Unified registry: provider -> model_type -> factory_func
UNIFIED_MODEL_REGISTRY: Dict[str, Dict[ModelType, Callable]] = {
    "rhesis": {
        ModelType.LANGUAGE: _create_rhesis_llm,
        ModelType.EMBEDDING: _create_rhesis_embedding_model,
    },
    "openai": {
        ModelType.LANGUAGE: _create_openai_llm,
        ModelType.EMBEDDING: _create_openai_embedding_model,
    },
    "gemini": {
        ModelType.LANGUAGE: _create_gemini_llm,
        ModelType.EMBEDDING: _create_gemini_embedding_model,
    },
    "vertex_ai": {
        ModelType.LANGUAGE: _create_vertex_ai_llm,
        ModelType.EMBEDDING: _create_vertex_ai_embedding_model,
    },
    # Language-only providers
    "anthropic": {
        ModelType.LANGUAGE: _create_anthropic_llm,
    },
    "cohere": {
        ModelType.LANGUAGE: _create_cohere_llm,
    },
    "groq": {
        ModelType.LANGUAGE: _create_groq_llm,
    },
    "huggingface": {
        ModelType.LANGUAGE: _create_huggingface_llm,
    },
    "lmformatenforcer": {
        ModelType.LANGUAGE: _create_lmformatenforcer_llm,
    },
    "meta_llama": {
        ModelType.LANGUAGE: _create_meta_llama_llm,
    },
    "mistral": {
        ModelType.LANGUAGE: _create_mistral_llm,
    },
    "ollama": {
        ModelType.LANGUAGE: _create_ollama_llm,
    },
    "openrouter": {
        ModelType.LANGUAGE: _create_openrouter_llm,
    },
    "perplexity": {
        ModelType.LANGUAGE: _create_perplexity_llm,
    },
    "polyphemus": {
        ModelType.LANGUAGE: _create_polyphemus_llm,
    },
    "replicate": {
        ModelType.LANGUAGE: _create_replicate_llm,
    },
    "together_ai": {
        ModelType.LANGUAGE: _create_together_ai_llm,
    },
}


# =============================================================================
# Configuration Classes
# =============================================================================


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


# =============================================================================
# Unified get_model() Function
# =============================================================================

# Type alias for any model instance
AnyModel = Union[BaseLLM, BaseEmbedder]


# Overloads for type safety
@overload
def get_model(
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
    model_type: Literal["language"] = ...,
    **kwargs,
) -> BaseLLM: ...


@overload
def get_model(
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
    model_type: Literal["embedding"] = ...,
    dimensions: Optional[int] = None,
    **kwargs,
) -> BaseEmbedder: ...


@overload
def get_model(
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
    **kwargs,
) -> Union[BaseLLM, BaseEmbedder]: ...


def get_model(
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
    model_type: Optional[Union[ModelType, str]] = None,
    dimensions: Optional[int] = None,
    config: Optional[Union[LanguageModelConfig, EmbeddingModelConfig]] = None,
    **kwargs,
) -> Union[BaseLLM, BaseEmbedder]:
    """Create any model instance - language or embedding.

    The model type is auto-detected from the model name. You can
    override detection with the `model_type` parameter.

    Pass a unified "provider/model_name" as the first argument;
    it is resolved in the background (e.g. get_model("vertex_ai/text-embedding-005")).

    Args:
        provider: Provider name, or "provider/model_name" as first positional
        model_name: Specific model name (omit when using unified format)
        api_key: API key for authentication
        model_type: Explicit model type ("language" or "embedding"). Auto-detected if not provided.
        dimensions: Optional embedding dimensions (for embedding models only)
        config: Complete configuration object
        **kwargs: Additional parameters passed to the model

    Returns:
        Union[BaseLLM, BaseEmbedder]: Configured model instance

    Raises:
        ValueError: If configuration is invalid or provider not supported

    Examples:
        >>> # Language model (auto-detected)
        >>> llm = get_model("openai/gpt-4o")
        >>> llm.generate("Hello!")

        >>> # Embedding model (auto-detected from name)
        >>> embedder = get_model("openai/text-embedding-3-small")
        >>> embedder.generate("Hello!")

        >>> # Explicit type override
        >>> embedder = get_model("openai", "custom-ft", model_type="embedding")

        >>> # With dimensions for embeddings
        >>> embedder = get_model("openai/text-embedding-3-small", dimensions=512)

        >>> # Explicit language type for type safety
        >>> llm = get_model("openai/gpt-4o", model_type="language")
    """
    # Extract values from config if provided
    if config:
        provider = provider or config.provider
        model_name = model_name or config.model_name
        api_key = api_key or config.api_key
        if isinstance(config, EmbeddingModelConfig):
            dimensions = dimensions or config.dimensions

    # Parse shorthand notation (e.g., "openai/gpt-4o")
    if provider and "/" in provider and model_name is None:
        prov, model = provider.split("/", 1)
        provider, model_name = prov, model

    # Resolve defaults (defaults are stored as full ids: provider/name)
    if model_type is not None:
        # Explicit type provided
        resolved_type = ModelType(model_type)
        if resolved_type == ModelType.LANGUAGE:
            if provider is None and model_name is None:
                provider, model_name = parse_model_id(DEFAULT_LANGUAGE_MODEL)
            else:
                provider = provider or DEFAULT_LANGUAGE_MODEL_PROVIDER
                if model_name is None:
                    full_id = DEFAULT_LANGUAGE_MODELS.get(provider)
                    model_name = model_name_from_id(full_id) if full_id else None
        elif resolved_type == ModelType.EMBEDDING:
            if provider is None and model_name is None:
                provider, model_name = parse_model_id(DEFAULT_EMBEDDING_MODEL)
            else:
                provider = provider or DEFAULT_EMBEDDING_MODEL_PROVIDER
                if model_name is None:
                    full_id = DEFAULT_EMBEDDING_MODELS.get(provider)
                    model_name = model_name_from_id(full_id) if full_id else None
    else:
        # Auto-detect type
        if provider is None and model_name is None:
            provider, model_name = parse_model_id(DEFAULT_LANGUAGE_MODEL)
        else:
            provider = provider or DEFAULT_LANGUAGE_MODEL_PROVIDER
            if model_name is None:
                full_id = DEFAULT_LANGUAGE_MODELS.get(provider)
                model_name = model_name_from_id(full_id) if full_id else None
        resolved_type = _classify_model(provider, model_name)

    # Validate provider exists
    if provider not in UNIFIED_MODEL_REGISTRY:
        available = ", ".join(sorted(UNIFIED_MODEL_REGISTRY.keys()))
        raise ValueError(f"Provider '{provider}' not supported. Available providers: {available}")

    # Look up factory function in unified registry
    provider_factories = UNIFIED_MODEL_REGISTRY.get(provider, {})
    factory_func = provider_factories.get(resolved_type)

    if factory_func is None:
        supported_types = [t.value for t in provider_factories.keys()]
        raise ValueError(
            f"Provider '{provider}' does not support model type "
            f"'{resolved_type.value}'. Supported types: {supported_types}"
        )

    # Call factory with appropriate parameters
    if resolved_type == ModelType.EMBEDDING:
        return factory_func(model_name, api_key, dimensions, **kwargs)
    else:
        return factory_func(model_name, api_key, **kwargs)


# =============================================================================
# Helper Functions for Listing Available Models
# =============================================================================


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
    if provider not in UNIFIED_MODEL_REGISTRY:
        available_providers = ", ".join(sorted(UNIFIED_MODEL_REGISTRY.keys()))
        raise ValueError(
            f"Provider '{provider}' not supported. Available providers: {available_providers}"
        )

    # Check if provider supports language models
    if ModelType.LANGUAGE not in UNIFIED_MODEL_REGISTRY.get(provider, {}):
        raise ValueError(f"Provider '{provider}' does not support language models.")

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
    if provider not in UNIFIED_MODEL_REGISTRY:
        available_providers = ", ".join(sorted(UNIFIED_MODEL_REGISTRY.keys()))
        raise ValueError(
            f"Embedding provider '{provider}' not supported. "
            f"Available providers: {available_providers}"
        )

    # Check if provider supports embedding models
    if ModelType.EMBEDDING not in UNIFIED_MODEL_REGISTRY.get(provider, {}):
        raise ValueError(f"Provider '{provider}' does not support embedding models.")

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
