from dataclasses import dataclass, field

from rhesis.sdk.services.base import BaseLLM

DEFAULT_PROVIDER = "rhesis"

DEFAULT_MODELS = {
    "rhesis": "rhesis-default",
    "rhesis_premium": "rhesis-premium-default",
}


@dataclass
class ModelConfig:
    """Configuration for a model.

    Args:
        model_type: The type of model (E.g OpenAI, Rhesis, Gemini)
        model_name: Specific model name (E.g gpt-4o, gemini-2.0-flash, etc)
        api_key: The API key to use for the model.
        extra_params: Extra parameters to pass to the model.
    """

    provider: str = DEFAULT_PROVIDER
    model_name: str = DEFAULT_MODELS[DEFAULT_PROVIDER]
    api_key: str | None = None
    extra_params: dict = field(default_factory=dict)


def get_model(
    provider: str | None = None,
    model_name: str | None = None,
    api_key: str | None = None,
    config: ModelConfig | None = None,
) -> BaseLLM:
    """Create a model instance based on the configuration."""
    if config:
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
