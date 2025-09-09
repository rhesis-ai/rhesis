import os
from enum import Enum
from typing import Any, Dict, Optional, Union

from deepeval.models import (
    AmazonBedrockModel,
    AnthropicModel,
    AzureOpenAIModel,
    GeminiModel,
    GPTModel,
    OllamaModel,
)


class ModelType(Enum):
    """Supported model types for DeepEval."""

    GEMINI = "gemini"
    OPENAI = "openai"
    AZURE_OPENAI = "azure_openai"
    ANTHROPIC = "anthropic"
    BEDROCK = "bedrock"
    OLLAMA = "ollama"


class ModelConfig:
    """Configuration for a DeepEval model."""

    def __init__(
        self, model_type: ModelType, model_name: str, api_key: Optional[str] = None, **kwargs
    ):
        self.model_type = model_type
        self.model_name = model_name
        self.api_key = api_key
        self.extra_params = kwargs


class ModelFactory:
    """Factory for creating DeepEval model instances."""

    @staticmethod
    def create_model(
        config: ModelConfig,
    ) -> Union[
        GeminiModel, GPTModel, AzureOpenAIModel, AnthropicModel, AmazonBedrockModel, OllamaModel
    ]:
        """Create a model instance based on the configuration."""

        if config.model_type == ModelType.GEMINI:
            api_key = config.api_key or os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise ValueError(
                    "GEMINI_API_KEY environment variable is required for Gemini models"
                )

            return GeminiModel(model_name=config.model_name, api_key=api_key, **config.extra_params)

        elif config.model_type == ModelType.OPENAI:
            api_key = config.api_key or os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError(
                    "OPENAI_API_KEY environment variable is required for OpenAI models"
                )

            return GPTModel(model=config.model_name, api_key=api_key, **config.extra_params)

        elif config.model_type == ModelType.AZURE_OPENAI:
            api_key = config.api_key or os.getenv("AZURE_OPENAI_API_KEY")
            endpoint = config.extra_params.get("azure_endpoint") or os.getenv(
                "AZURE_OPENAI_ENDPOINT"
            )

            if not api_key:
                raise ValueError(
                    "AZURE_OPENAI_API_KEY environment variable is required for Azure OpenAI models"
                )
            if not endpoint:
                raise ValueError(
                    "azure_endpoint parameter or AZURE_OPENAI_ENDPOINT environment variable is required for Azure OpenAI models"
                )

            return AzureOpenAIModel(
                model=config.model_name,
                api_key=api_key,
                azure_endpoint=endpoint,
                **{k: v for k, v in config.extra_params.items() if k != "azure_endpoint"},
            )

        elif config.model_type == ModelType.ANTHROPIC:
            api_key = config.api_key or os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError(
                    "ANTHROPIC_API_KEY environment variable is required for Anthropic models"
                )

            return AnthropicModel(model=config.model_name, api_key=api_key, **config.extra_params)

        elif config.model_type == ModelType.BEDROCK:
            access_key_id = config.extra_params.get("access_key_id") or os.getenv(
                "AWS_ACCESS_KEY_ID"
            )
            secret_access_key = config.extra_params.get("secret_access_key") or os.getenv(
                "AWS_SECRET_ACCESS_KEY"
            )
            region_name = config.extra_params.get("region_name") or os.getenv(
                "AWS_DEFAULT_REGION", "us-east-1"
            )

            return AmazonBedrockModel(
                model_id=config.model_name,
                aws_access_key_id=access_key_id,
                aws_secret_access_key=secret_access_key,
                region_name=region_name,
                **{
                    k: v
                    for k, v in config.extra_params.items()
                    if k not in ["access_key_id", "secret_access_key", "region_name"]
                },
            )

        elif config.model_type == ModelType.OLLAMA:
            base_url = config.extra_params.get("base_url") or os.getenv(
                "OLLAMA_BASE_URL", "http://localhost:11434"
            )

            return OllamaModel(
                model=config.model_name,
                base_url=base_url,
                **{k: v for k, v in config.extra_params.items() if k != "base_url"},
            )

        else:
            raise ValueError(f"Unsupported model type: {config.model_type}")

    @staticmethod
    def create_default_model(
        model_type: str = "gemini", model_name: str = None
    ) -> Union[
        GeminiModel, GPTModel, AzureOpenAIModel, AnthropicModel, AmazonBedrockModel, OllamaModel
    ]:
        """Create a default model configuration."""
        try:
            model_type_enum = ModelType(model_type.lower())
        except ValueError:
            raise ValueError(
                f"Unsupported model type: {model_type}. Supported types: {[t.value for t in ModelType]}"
            )

        # Use environment variable for default model name if not provided
        if model_name is None:
            if model_type_enum == ModelType.GEMINI:
                model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-2.0-flash-001")
            else:
                # Get default model name for other types
                model_type_for_default = model_type.lower()
                default_names = {
                    "openai": "gpt-4",
                    "azure_openai": "gpt-4",
                    "anthropic": "claude-3-sonnet-20240229",
                    "bedrock": "anthropic.claude-3-sonnet-20240229-v1:0",
                    "ollama": "llama2",
                }
                model_name = default_names.get(model_type_for_default, "gemini-1.5-pro")

        config = ModelConfig(model_type=model_type_enum, model_name=model_name)

        return ModelFactory.create_model(config)


def get_model_from_config(
    config: Optional[Dict[str, Any]] = None,
) -> Union[
    GeminiModel, GPTModel, AzureOpenAIModel, AnthropicModel, AmazonBedrockModel, OllamaModel
]:
    """
    Get a model instance from configuration.

    This function can be easily extended to read from database configuration
    instead of environment variables and default values.

    Args:
        config: Optional configuration dictionary. If None, uses default Gemini model.
                Expected format:
                {
                    "type": "gemini",
                    "model_name": "gemini-1.5-pro",
                    "api_key": "optional_api_key",
                    "extra_params": {}
                }

    Returns:
        Model instance ready to use with DeepEval metrics.
    """
    if config is None:
        # Default configuration - can be changed to read from database
        return ModelFactory.create_default_model()

    model_type = config.get("type", "gemini")
    model_name = config.get("model_name")
    api_key = config.get("api_key")
    extra_params = config.get("extra_params", {})

    # If no model name provided, use environment variable or default
    if model_name is None:
        if model_type.lower() == "gemini":
            model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-1.5-pro")
        else:
            # Get default model name for other types
            model_type_for_default = model_type.lower()
            default_names = {
                "openai": "gpt-4",
                "azure_openai": "gpt-4",
                "anthropic": "claude-3-sonnet-20240229",
                "bedrock": "anthropic.claude-3-sonnet-20240229-v1:0",
                "ollama": "llama2",
            }
            model_name = default_names.get(model_type_for_default, "gemini-1.5-pro")

    try:
        model_type_enum = ModelType(model_type.lower())
    except ValueError:
        raise ValueError(
            f"Unsupported model type: {model_type}. Supported types: {[t.value for t in ModelType]}"
        )

    model_config = ModelConfig(
        model_type=model_type_enum, model_name=model_name, api_key=api_key, **extra_params
    )

    return ModelFactory.create_model(model_config)
