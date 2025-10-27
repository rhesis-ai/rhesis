from abc import ABC, abstractmethod
from typing import Any, Dict, Union


class BaseLLM(ABC):
    def __init__(self, model_name, *args, **kwargs):
        self.model_name = model_name
        self.model = self.load_model(*args, **kwargs)

    @abstractmethod
    def load_model(self, *args, **kwargs):
        """Loads a model

        Returns:
            A model object
        """
        pass

    @abstractmethod
    def generate(self, *args, **kwargs) -> Union[str, Dict[str, Any]]:
        """Runs the model to output LLM response.

        Returns:
            A string.
        """
        pass

    def get_model_name(self, *args, **kwargs) -> str:
        return f"Class name: {self.__class__.__name__}, model name: {self.model_name}"
