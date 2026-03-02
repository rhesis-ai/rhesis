"""
Language Model and Embedding Model Factory for Rhesis SDK.

This module provides a unified way to create model instances with smart
defaults and comprehensive error handling.
"""

import importlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, Literal, NamedTuple, Optional, Union, overload

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
    name_lower = (model_name or provider or "").lower()
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


# =============================================================================
# Registry-driven Model Creation
# =============================================================================

_PROVIDERS_MODULE = "rhesis.sdk.models.providers"


class _ProviderSpec(NamedTuple):
    """Specification for lazily importing and instantiating a provider class.

    Flags control which standard arguments are forwarded to the constructor:
      pass_api_key    -- set False for local-only providers (ollama, huggingface, ...)
      pass_dimensions -- set False for embedders that ignore the dimensions param
    """

    module: str
    class_name: str
    pass_api_key: bool = True
    pass_dimensions: bool = True


def _create_from_spec(
    spec: _ProviderSpec,
    model_type: ModelType,
    model_name: str,
    api_key: Optional[str],
    dimensions: Optional[int] = None,
    **kwargs,
) -> Union[BaseLLM, BaseEmbedder]:
    """Generic model creator that lazily imports and instantiates a provider class."""
    mod = importlib.import_module(spec.module)
    cls = getattr(mod, spec.class_name)

    call_kwargs: dict = {"model_name": model_name, **kwargs}
    if spec.pass_api_key:
        call_kwargs["api_key"] = api_key
    if model_type == ModelType.EMBEDDING and spec.pass_dimensions:
        call_kwargs["dimensions"] = dimensions

    return cls(**call_kwargs)


# Vertex AI requires special constructor handling (no api_key, service-account auth)


def _create_vertex_ai_llm(model_name: str, api_key: Optional[str], **kwargs) -> BaseLLM:
    """Factory wrapper for VertexAILLM (api_key ignored, uses service account)."""
    from rhesis.sdk.models.providers.vertex_ai import VertexAILLM

    return VertexAILLM(model_name=model_name, **kwargs)


def _create_vertex_ai_embedding_model(
    model_name: str,
    api_key: Optional[str],
    dimensions: Optional[int],
    **kwargs,
) -> BaseEmbedder:
    """Factory wrapper for VertexAIEmbedder (api_key ignored, uses service account)."""
    from rhesis.sdk.models.providers.vertex_ai import VertexAIEmbedder

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


# =============================================================================
# Unified Model Registry
# =============================================================================

# provider -> model_type -> _ProviderSpec (data) or Callable (special-case wrapper)
UNIFIED_MODEL_REGISTRY: Dict[str, Dict[ModelType, Union[_ProviderSpec, Callable]]] = {
    "rhesis": {
        ModelType.LANGUAGE: _ProviderSpec(f"{_PROVIDERS_MODULE}.native", "RhesisLLM"),
        ModelType.EMBEDDING: _ProviderSpec(
            f"{_PROVIDERS_MODULE}.native",
            "RhesisEmbedder",
            pass_dimensions=False,
        ),
    },
    "openai": {
        ModelType.LANGUAGE: _ProviderSpec(f"{_PROVIDERS_MODULE}.openai", "OpenAILLM"),
        ModelType.EMBEDDING: _ProviderSpec(f"{_PROVIDERS_MODULE}.openai", "OpenAIEmbedder"),
    },
    "gemini": {
        ModelType.LANGUAGE: _ProviderSpec(f"{_PROVIDERS_MODULE}.gemini", "GeminiLLM"),
        ModelType.EMBEDDING: _ProviderSpec(f"{_PROVIDERS_MODULE}.gemini", "GeminiEmbedder"),
    },
    "vertex_ai": {
        ModelType.LANGUAGE: _create_vertex_ai_llm,
        ModelType.EMBEDDING: _create_vertex_ai_embedding_model,
    },
    "anthropic": {
        ModelType.LANGUAGE: _ProviderSpec(f"{_PROVIDERS_MODULE}.anthropic", "AnthropicLLM"),
    },
    "cohere": {
        ModelType.LANGUAGE: _ProviderSpec(f"{_PROVIDERS_MODULE}.cohere", "CohereLLM"),
    },
    "groq": {
        ModelType.LANGUAGE: _ProviderSpec(f"{_PROVIDERS_MODULE}.groq", "GroqLLM"),
    },
    "huggingface": {
        ModelType.LANGUAGE: _ProviderSpec(
            f"{_PROVIDERS_MODULE}.huggingface", "HuggingFaceLLM", pass_api_key=False
        ),
    },
    "lmformatenforcer": {
        ModelType.LANGUAGE: _ProviderSpec(
            f"{_PROVIDERS_MODULE}.lmformatenforcer",
            "LMFormatEnforcerLLM",
            pass_api_key=False,
        ),
    },
    "meta_llama": {
        ModelType.LANGUAGE: _ProviderSpec(f"{_PROVIDERS_MODULE}.meta_llama", "MetaLlamaLLM"),
    },
    "mistral": {
        ModelType.LANGUAGE: _ProviderSpec(f"{_PROVIDERS_MODULE}.mistral", "MistralLLM"),
    },
    "ollama": {
        ModelType.LANGUAGE: _ProviderSpec(
            f"{_PROVIDERS_MODULE}.ollama",
            "OllamaLLM",
            pass_api_key=False,
        ),
    },
    "openrouter": {
        ModelType.LANGUAGE: _ProviderSpec(f"{_PROVIDERS_MODULE}.openrouter", "OpenRouterLLM"),
    },
    "perplexity": {
        ModelType.LANGUAGE: _ProviderSpec(f"{_PROVIDERS_MODULE}.perplexity", "PerplexityLLM"),
    },
    "polyphemus": {
        ModelType.LANGUAGE: _ProviderSpec(f"{_PROVIDERS_MODULE}.polyphemus", "PolyphemusLLM"),
    },
    "replicate": {
        ModelType.LANGUAGE: _ProviderSpec(f"{_PROVIDERS_MODULE}.replicate", "ReplicateLLM"),
    },
    "together_ai": {
        ModelType.LANGUAGE: _ProviderSpec(f"{_PROVIDERS_MODULE}.together_ai", "TogetherAILLM"),
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

    # Look up factory in unified registry
    provider_factories = UNIFIED_MODEL_REGISTRY.get(provider, {})
    factory = provider_factories.get(resolved_type)

    if factory is None:
        supported_types = [t.value for t in provider_factories.keys()]
        raise ValueError(
            f"Provider '{provider}' does not support model type "
            f"'{resolved_type.value}'. Supported types: {supported_types}"
        )

    # Dispatch: _ProviderSpec uses generic creator, callables are invoked directly
    if isinstance(factory, _ProviderSpec):
        return _create_from_spec(factory, resolved_type, model_name, api_key, dimensions, **kwargs)
    elif resolved_type == ModelType.EMBEDDING:
        return factory(model_name, api_key, dimensions, **kwargs)
    else:
        return factory(model_name, api_key, **kwargs)


# =============================================================================
# Typed Factory Functions: get_language_model, get_embedding_model
# =============================================================================


def get_language_model(
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
    config: Optional[LanguageModelConfig] = None,
    **kwargs,
) -> BaseLLM:
    """Create a language model instance (LLM).

    Same as get_model() but always returns a language model, using language
    defaults when provider/model are omitted. Use this when you want a
    BaseLLM and do not want auto-detection.

    Args:
        provider: Provider name or "provider/model_name" as first positional
        model_name: Specific model name (omit when using unified format)
        api_key: API key for authentication
        config: Complete configuration object
        **kwargs: Additional parameters passed to the model

    Returns:
        BaseLLM: Configured language model instance

    Examples:
        >>> llm = get_language_model()
        >>> llm = get_language_model("openai/gpt-4o")
        >>> llm = get_language_model("anthropic", "claude-4")
    """
    return get_model(
        provider=provider,
        model_name=model_name,
        api_key=api_key,
        model_type=ModelType.LANGUAGE,
        config=config,
        **kwargs,
    )


def get_embedding_model(
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
    dimensions: Optional[int] = None,
    config: Optional[EmbeddingModelConfig] = None,
    **kwargs,
) -> BaseEmbedder:
    """Create an embedding model instance.

    Same as get_model(..., model_type="embedding") with embedding defaults.
    Use this when you want a BaseEmbedder without passing model_type.

    Args:
        provider: Provider name or "provider/model_name" as first positional
        model_name: Specific model name (omit when using unified format)
        api_key: API key for authentication
        dimensions: Optional embedding dimensions (model-dependent)
        config: Complete configuration object
        **kwargs: Additional parameters passed to the model

    Returns:
        BaseEmbedder: Configured embedding model instance

    Examples:
        >>> embedder = get_embedding_model()
        >>> embedder = get_embedding_model("openai/text-embedding-3-small")
        >>> embedder = get_embedding_model("openai", dimensions=512)
    """
    return get_model(
        provider=provider,
        model_name=model_name,
        api_key=api_key,
        model_type=ModelType.EMBEDDING,
        dimensions=dimensions,
        config=config,
        **kwargs,
    )


# Backward compatibility: get_embedder was the previous name for embedding models
get_embedder = get_embedding_model


# =============================================================================
# Helper Functions for Listing Available Models
# =============================================================================

# Providers that support listing available models, keyed by (module, class_name)
_LISTABLE_LLM_PROVIDERS: Dict[str, tuple[str, str]] = {
    "anthropic": (f"{_PROVIDERS_MODULE}.anthropic", "AnthropicLLM"),
    "cohere": (f"{_PROVIDERS_MODULE}.cohere", "CohereLLM"),
    "gemini": (f"{_PROVIDERS_MODULE}.gemini", "GeminiLLM"),
    "groq": (f"{_PROVIDERS_MODULE}.groq", "GroqLLM"),
    "meta_llama": (f"{_PROVIDERS_MODULE}.meta_llama", "MetaLlamaLLM"),
    "mistral": (f"{_PROVIDERS_MODULE}.mistral", "MistralLLM"),
    "ollama": (f"{_PROVIDERS_MODULE}.ollama", "OllamaLLM"),
    "openai": (f"{_PROVIDERS_MODULE}.openai", "OpenAILLM"),
    "openrouter": (f"{_PROVIDERS_MODULE}.openrouter", "OpenRouterLLM"),
    "perplexity": (f"{_PROVIDERS_MODULE}.perplexity", "PerplexityLLM"),
    "replicate": (f"{_PROVIDERS_MODULE}.replicate", "ReplicateLLM"),
    "together_ai": (f"{_PROVIDERS_MODULE}.together_ai", "TogetherAILLM"),
    "vertex_ai": (f"{_PROVIDERS_MODULE}.vertex_ai", "VertexAILLM"),
}

_LISTABLE_EMBEDDING_PROVIDERS: Dict[str, tuple[str, str]] = {
    "openai": (f"{_PROVIDERS_MODULE}.openai", "OpenAIEmbedder"),
    "gemini": (f"{_PROVIDERS_MODULE}.gemini", "GeminiEmbedder"),
    "vertex_ai": (f"{_PROVIDERS_MODULE}.vertex_ai", "VertexAIEmbedder"),
}


def _list_models(module_path: str, class_name: str) -> list[str]:
    """Import a provider class and call its get_available_models() class method."""
    mod = importlib.import_module(module_path)
    cls = getattr(mod, class_name)
    return cls.get_available_models()


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

    if ModelType.LANGUAGE not in UNIFIED_MODEL_REGISTRY.get(provider, {}):
        raise ValueError(f"Provider '{provider}' does not support language models.")

    if provider not in _LISTABLE_LLM_PROVIDERS:
        raise ValueError(
            f"Provider '{provider}' does not support listing "
            f"available models. Only the following providers support "
            f"this feature: "
            f"{', '.join(sorted(_LISTABLE_LLM_PROVIDERS.keys()))}"
        )

    module_path, class_name = _LISTABLE_LLM_PROVIDERS[provider]
    return _list_models(module_path, class_name)


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

    if ModelType.EMBEDDING not in UNIFIED_MODEL_REGISTRY.get(provider, {}):
        raise ValueError(f"Provider '{provider}' does not support embedding models.")

    if provider not in _LISTABLE_EMBEDDING_PROVIDERS:
        raise ValueError(
            f"Provider '{provider}' does not support listing "
            f"available embedding models. Only the following providers "
            f"support this feature: "
            f"{', '.join(sorted(_LISTABLE_EMBEDDING_PROVIDERS.keys()))}"
        )

    module_path, class_name = _LISTABLE_EMBEDDING_PROVIDERS[provider]
    return _list_models(module_path, class_name)
