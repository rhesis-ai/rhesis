"""
Model Factory for Rhesis SDK

This module provides a simple and intuitive way to create LLM model instances
with smart defaults and comprehensive error handling.

"""

from dataclasses import dataclass, field
from typing import Callable, Dict, Optional

from rhesis.sdk.models.base import BaseLLM

# Default configuration
DEFAULT_PROVIDER = "rhesis"
DEFAULT_MODELS = {
    "rhesis": "rhesis-default",
    "anthropic": "claude-4",
    "gemini": "gemini-2.0-flash",
    "groq": "llama3-8b-8192",
    "huggingface": "meta-llama/Llama-2-7b-chat-hf",
    "meta_llama": "Llama-3.3-70B-Instruct",
    "mistral": "mistral-medium-latest",
    "ollama": "llama3.1",
    "openai": "gpt-4o",
    "perplexity": "sonar-pro",
    "replicate": "llama-2-70b-chat",
    "together_ai": "togethercomputer/llama-2-70b-chat",
    "vertex_ai": "gemini-2.0-flash",  # Best performance - avoid 2.5-flash
}


# Factory functions for each provider, the are used to create the model instance and
# avoid circular imports


def _create_rhesis_llm(model_name: str, api_key: Optional[str]) -> BaseLLM:
    """Factory function for RhesisLLM."""
    from rhesis.sdk.models.providers.native import RhesisLLM

    return RhesisLLM(model_name=model_name, api_key=api_key)


def _create_gemini_llm(model_name: str, api_key: Optional[str]) -> BaseLLM:
    """Factory function for GeminiLLM."""
    from rhesis.sdk.models.providers.gemini import GeminiLLM

    return GeminiLLM(model_name=model_name, api_key=api_key)


def _create_ollama_llm(model_name: str, api_key: Optional[str]) -> BaseLLM:
    """Factory function for OllamaLLM."""
    from rhesis.sdk.models.providers.ollama import OllamaLLM

    return OllamaLLM(model_name=model_name)


def _create_openai_llm(model_name: str, api_key: Optional[str]) -> BaseLLM:
    """Factory function for OpenAILLM."""
    from rhesis.sdk.models.providers.openai import OpenAILLM

    return OpenAILLM(model_name=model_name, api_key=api_key)


def _create_vertex_ai_llm(model_name: str, api_key: Optional[str]) -> BaseLLM:
    """Factory function for VertexAILLM."""
    from rhesis.sdk.models.providers.vertex_ai import VertexAILLM

    # Note: api_key is ignored for Vertex AI as it uses service account credentials
    return VertexAILLM(model_name=model_name)


def _create_anthropic_llm(model_name: str, api_key: Optional[str]) -> BaseLLM:
    """Factory function for AnthropicLLM."""
    from rhesis.sdk.models.providers.anthropic import AnthropicLLM

    return AnthropicLLM(model_name=model_name, api_key=api_key)


def _create_groq_llm(model_name: str, api_key: Optional[str]) -> BaseLLM:
    """Factory function for GroqLLM."""
    from rhesis.sdk.models.providers.groq import GroqLLM

    return GroqLLM(model_name=model_name, api_key=api_key)


def _create_huggingface_llm(model_name: str, api_key: Optional[str]) -> BaseLLM:
    """Factory function for HuggingFaceLLM."""
    from rhesis.sdk.models.providers.huggingface import HuggingFaceLLM

    # Note: api_key is ignored for HuggingFace as it uses local models
    return HuggingFaceLLM(model_name=model_name)


def _create_meta_llama_llm(model_name: str, api_key: Optional[str]) -> BaseLLM:
    """Factory function for MetaLlamaLLM."""
    from rhesis.sdk.models.providers.meta_llama import MetaLlamaLLM

    return MetaLlamaLLM(model_name=model_name, api_key=api_key)


def _create_mistral_llm(model_name: str, api_key: Optional[str]) -> BaseLLM:
    """Factory function for MistralLLM."""
    from rhesis.sdk.models.providers.mistral import MistralLLM

    return MistralLLM(model_name=model_name, api_key=api_key)


def _create_perplexity_llm(model_name: str, api_key: Optional[str]) -> BaseLLM:
    """Factory function for PerplexityLLM."""
    from rhesis.sdk.models.providers.perplexity import PerplexityLLM

    return PerplexityLLM(model_name=model_name, api_key=api_key)


def _create_replicate_llm(model_name: str, api_key: Optional[str]) -> BaseLLM:
    """Factory function for ReplicateLLM."""
    from rhesis.sdk.models.providers.replicate import ReplicateLLM

    return ReplicateLLM(model_name=model_name, api_key=api_key)


def _create_together_ai_llm(model_name: str, api_key: Optional[str]) -> BaseLLM:
    """Factory function for TogetherAILLM."""
    from rhesis.sdk.models.providers.together_ai import TogetherAILLM

    return TogetherAILLM(model_name=model_name, api_key=api_key)


# Provider registry mapping provider names to their factory functions
PROVIDER_REGISTRY: Dict[str, Callable[[str, Optional[str]], BaseLLM]] = {
    "rhesis": _create_rhesis_llm,
    "anthropic": _create_anthropic_llm,
    "gemini": _create_gemini_llm,
    "groq": _create_groq_llm,
    "huggingface": _create_huggingface_llm,
    "meta_llama": _create_meta_llama_llm,
    "mistral": _create_mistral_llm,
    "ollama": _create_ollama_llm,
    "openai": _create_openai_llm,
    "perplexity": _create_perplexity_llm,
    "replicate": _create_replicate_llm,
    "together_ai": _create_together_ai_llm,
    "vertex_ai": _create_vertex_ai_llm,
}


@dataclass
class ModelConfig:
    """Configuration for a model instance.

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


def get_model(
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
    config: Optional[ModelConfig] = None,
    **kwargs,
) -> BaseLLM:
    """Create a model instance with smart defaults and comprehensive error handling.

    This function provides multiple ways to create a model instance:

    1. **Minimal**: `get_model()` - uses all defaults
    2. **Provider only**: `get_model("rhesis")` - uses default model for provider
    3. **Provider + Model**: `get_model("rhesis", "rhesis-llm-v1")`
    4. **Shorthand**: `get_model("rhesis/rhesis-llm-v1")`
    5. **Full config**: `get_model(config=ModelConfig(...))`

    Args:
        provider: Provider name (e.g., "rhesis", "anthropic", "gemini", "openai",
            "mistral", "ollama")
        model_name: Specific model name
        api_key: API key for authentication
        config: Complete configuration object
        **kwargs: Additional parameters passed to ModelConfig

    Returns:
        BaseLLM: Configured model instance

    Raises:
        ValueError: If configuration is invalid or provider not supported
        ImportError: If required dependencies are missing

    Examples:
        >>> # Basic usage with defaults
        >>> model = get_model()

        >>> # Specify provider and model
        >>> model = get_model("rhesis", "rhesis-llm-v1")

        >>> # Use provider/model shorthand
        >>> model = get_model("rhesis/rhesis-llm-v1")

        >>> # Use different providers
        >>> model = get_model("anthropic", "claude-4")
        >>> model = get_model("openai", "gpt-4o")
        >>> model = get_model("mistral/mistral-medium-latest")

        >>> # With custom configuration
        >>> config = ModelConfig(
        ...     provider="gemini",
        ...     model_name="gemini-pro",
        ...     api_key="your-api-key"
        ... )
        >>> model = get_model(config=config)

        >>> # With extra parameters
        >>> model = get_model(
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
        cfg = ModelConfig()
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

    config = ModelConfig(provider=provider, model_name=model_name, api_key=api_key)

    # Get the factory function for the provider
    factory_func = PROVIDER_REGISTRY.get(config.provider)
    if factory_func is None:
        raise ValueError(f"Provider {config.provider} not supported")

    # Use the factory function to create the model instance
    return factory_func(config.model_name, config.api_key)
