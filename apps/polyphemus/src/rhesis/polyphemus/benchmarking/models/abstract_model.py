import textwrap
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, Any


class ModelProvider(Enum):
    """Enum for different LLM providers"""
    GOOGLE = "google"
    HUGGINGFACE = "huggingface"
    NONE = "none"


@dataclass
class Invocation:
    """Represents a request to an LLM. Must contain a prompt and can include additional parameters for generation."""
    prompt: str
    system_prompt: Optional[str] = None
    additional_params: Optional[Dict[str, Any]] = field(default_factory=dict)

    def __str__(self):
        additional_params_str = ""
        if self.additional_params:
            for key, value in self.additional_params.items():
                additional_params_str += f"{key}: {value}\n"
        else:
            "No additional parameters provided.\n"
        additional_params_str = textwrap.indent(additional_params_str, "\t")

        string = ""
        string += "System Prompt: " + (self.system_prompt if self.system_prompt else "None") + "\n"
        string += "Prompt: " + self.prompt + "\n"
        string += "Additional Parameters:\n"
        string += additional_params_str
        return string


@dataclass
class ModelResponse:
    """Represents a response from an LLM"""
    content: str
    model_name: str
    model_location: str
    provider: ModelProvider
    request: Invocation
    tokens_used: Optional[int] = None
    response_time: Optional[float] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def __str__(self):
        request_string = textwrap.indent(str(self.request), "\t")

        string = ""
        string += f"Model: {self.model_name} ({self.provider.value})\n"
        string += f"Location: {self.model_location}\n"
        string += f"Request:\n{request_string}\n"
        string += f"Answer: {self.content}\n"
        if self.tokens_used is not None:
            string += f"Tokens used: {self.tokens_used}\n"
        if self.response_time is not None:
            string += f"Response time: {self.response_time:.2f}s\n"
        if self.error is not None:
            string += f"Error: {self.error}\n"
        if self.metadata is not None:
            string += "Metadata:\n"
            for key, value in self.metadata.items():
                if value is not None:
                    string += f"{key}: {value}\n"
        return string.strip()


class Model(ABC):
    """
    Abstract base class for LLM models.
    Provides a consistent interface for different LLM providers.
    """

    def __init__(self):
        self.name = None
        self.location = None
        self.provider = None
        self.tokens_used = 0

    @abstractmethod
    def load_model(self):
        """
        Load the model from its location.
        This method should be implemented by subclasses to handle model loading.
        """
        pass

    @abstractmethod
    def unload_model(self):
        """
        Unload the model to free up resources.
        This method should be implemented by subclasses to handle model unloading.
        """
        pass

    @abstractmethod
    def generate_response(self, request: Invocation) -> ModelResponse:
        """
        Generate a response for the given request.
        This method should be implemented by subclasses to handle the actual
        generation of content based on the prompt and parameters.
        
        Args:
            request: The ModelRequest containing prompt and parameters
            
        Returns:
            ModelResponse with the generated content and metadata
        """
        pass

    @abstractmethod
    def get_recommended_request(self, prompt: str, system_prompt: Optional[str], additional_params: Optional[Dict[str, Any]]) -> Invocation:
        """
        Get a request object for the given prompt containing recommended parameters.
        This method should be implemented by subclasses to provide standard
        model specific parameters for the request.
        """
        pass
