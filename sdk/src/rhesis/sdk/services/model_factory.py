"""
Model Factory for Rhesis SDK

This module provides a simple and intuitive way to create LLM model instances
with smart defaults and comprehensive error handling.

"""

from dataclasses import dataclass, field
from typing import Optional

from rhesis.sdk.services.base import BaseLLM

# Default configuration
DEFAULT_PROVIDER = "rhesis"
DEFAULT_MODELS = {
    "rhesis": "rhesis-default",
    "rhesis_premium": "rhesis-premium-default",
}


@dataclass
class ModelConfig:
    """Configuration for a model instance.

    Args:
        provider: The provider name (e.g., "rhesis", "rhesis_premium")
        model_name: Specific model name (E.g gpt-4o, gemini-2.0-flash, etc)
        api_key: The API key to use for the model.
        extra_params: Extra parameters to pass to the model.
    """

    provider: str = DEFAULT_PROVIDER
    model_name: str = DEFAULT_MODELS[DEFAULT_PROVIDER]
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
        provider: Provider name (e.g., "rhesis", "rhesis_premium")
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

        >>> # With custom configuration
        >>> config = ModelConfig(
        ...     provider="rhesis_premium",
        ...     model_name="rhesis-premium-v1",
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
    model_name = model_name or cfg.model_name or DEFAULT_MODELS[provider]
    api_key = api_key or cfg.api_key
    config = ModelConfig(provider=provider, model_name=model_name, api_key=api_key)

    if config.provider == "rhesis":
        from rhesis.sdk.services.providers.rhesis_provider import RhesisLLMService

        return RhesisLLMService(model_name=config.model_name, api_key=config.api_key)
    elif config.provider == "rhesis_premium":
        from rhesis.sdk.services.providers.rhesis_premium import RhesisPremiumLLMService

        return RhesisPremiumLLMService(model_name=config.model_name, api_key=config.api_key)
    else:
        raise ValueError(f"Provider {config.provider} not supported")


if __name__ == "__main__":
    model = get_model("rhesis_premium/sdsf")
    print(model.get_model_name())
    print(model.generate(prompt="What is the capital of France?"))
