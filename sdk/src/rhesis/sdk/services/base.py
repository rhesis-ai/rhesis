from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ModelType(Enum):
    """Supported model types in Rhesis."""

    RHESIS = "rhesis"


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
    model_name: str
    api_key: Optional[str] = None
    extra_params: dict = field(default_factory=dict)


class BaseLLM(ABC):
    def __init__(self, model_name, *args, **kwargs):
        self.model_name = model_name
        self.model = self.load_model(*args, **kwargs)

    @abstractmethod
    def load_model(self, *args, **kwargs):
        """Loads a model, that will be responsible for scoring.

        Returns:
            A model object
        """
        pass

    @abstractmethod
    def generate(self, *args, **kwargs) -> str:
        """Runs the model to output LLM response.

        Returns:
            A string.
        """
        pass

    @abstractmethod
    def get_model_name(self, *args, **kwargs) -> str:
        pass
