from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Union

from rhesis.sdk.services.providers.rhesis import RhesisLLMService


class ModelType(Enum):
    """Supported model types in Rhesis."""

    RHESIS = "rhesis"
    OPENAI = "openai"


DEFAULT_MODEL_NAMES = {
    ModelType.RHESIS: "rhesis-default",
    ModelType.OPENAI: "gpt-4o",
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

    model_type: ModelType
    model_name: Optional[str] = None
    api_key: Optional[str] = None
    extra_params: dict = field(default_factory=dict)


class ModelFactory:
    """Factory for creating model instances."""

    @staticmethod
    def create_model(
        config: ModelConfig,
    ) -> Union[RhesisLLMService,]:
        """Create a model instance based on the configuration."""
        if config.model_type == ModelType.RHESIS:
            return RhesisLLMService(model_name=config.model_name, api_key=config.api_key)
        else:
            raise ValueError(f"Model type {config.model_type} not supported")

    @staticmethod
    def create_default_model(
        model_type: Union[ModelType, str] = ModelType.RHESIS.value,
    ) -> Union[RhesisLLMService,]:
        # Use environment variable for default model name if not provided
        if model_type == ModelType.RHESIS:
            model_name = DEFAULT_MODEL_NAMES[ModelType.RHESIS]

            config = ModelConfig(model_type=ModelType.RHESIS, model_name=model_name)

        return ModelFactory.create_model(config)


if __name__ == "__main__":
    model_config = ModelConfig(model_type=ModelType.RHESIS, model_name="rhesis-default")
    model = ModelFactory.create_default_model()
    print(model.generate(prompt="What is the capital of France?"))
