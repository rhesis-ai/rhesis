from enum import Enum
from typing import Any, Dict, Optional, Union

# Import DeepEvalBaseLLM for proper custom model implementation
from deepeval.models import (
    DeepEvalBaseLLM,
)

from rhesis.sdk.services.providers.rhesis import RhesisLLMService


class ModelType(Enum):
    """Supported model types for DeepEval."""

    RHESIS = "rhesis"


class ModelConfig:
    """Configuration for a DeepEval model."""

    def __init__(
        self, model_type: ModelType, model_name: str, api_key: Optional[str] = None, **kwargs
    ):
        self.model_type = model_type
        self.model_name = model_name
        self.api_key = api_key
        self.extra_params = kwargs


class RhesisModelWrapper(RhesisLLMService, DeepEvalBaseLLM):
    def generate(self, prompt: str) -> str:
        return super().generate(prompt, response_format="text")

    async def a_generate(self, prompt: str) -> str:
        """Asynchronously generate text using the Rhesis service.

        Args:
            prompt: The input prompt string

        Returns:
            Generated text response as string
        """
        # For now, use synchronous generation
        # TODO: Implement async support when RhesisLLMService supports it
        return self.generate(prompt)


class ModelFactory:
    """Factory for creating DeepEval model instances."""

    @staticmethod
    def create_model(
        config: ModelConfig,
    ) -> Union[RhesisModelWrapper,]:
        """Create a model instance based on the configuration."""

        return RhesisModelWrapper(model_name=config.model_name, api_key=config.api_key)

    @staticmethod
    def create_default_model(
        model_type: str = "gemini", model_name: str = None
    ) -> RhesisModelWrapper:
        # Use environment variable for default model name if not provided
        model_name = "rhesis-default"

        config = ModelConfig(model_type=ModelType.RHESIS, model_name=model_name)

        return ModelFactory.create_model(config)


def get_model_from_config(
    config: Optional[Dict[str, Any]] = None,
) -> RhesisModelWrapper:
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

    model_type = ModelType(config.get("type"))
    model_name = config.get("model_name")
    api_key = config.get("api_key")
    extra_params = config.get("extra_params", {})

    # If no model name provided, use environment variable or default

    model_config = ModelConfig(
        model_type=model_type, model_name=model_name, api_key=api_key, **extra_params
    )

    return ModelFactory.create_model(model_config)
