from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

if TYPE_CHECKING:
    from rhesis.sdk.entities.model import Model

# Type alias for embeddings
Embedding = List[float]


class BaseLLM(ABC):
    PROVIDER: str = ""  # Subclasses should override this

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
            A string or dict (if schema provided).
        """
        pass

    @abstractmethod
    def generate_batch(self, *args, **kwargs) -> List[Union[str, Dict[str, Any]]]:
        """Runs the model on multiple prompts to output LLM responses.

        Returns:
            A list of strings or dicts (if schema provided).
        """
        pass

    def get_model_name(self, *args, **kwargs) -> str:
        return f"Class name: {self.__class__.__name__}, model name: {self.model_name}"

    def get_available_models(self) -> List[str]:
        raise NotImplementedError("Subclasses must implement this method")

    def push(self, name: str, description: Optional[str] = None) -> "Model":
        """Save this LLM configuration to the Rhesis platform as a Model entity.

        Creates a Model entity with this LLM's provider, model name, and API key,
        then saves it to the platform.

        Args:
            name: Name for the saved model configuration (required)
            description: Optional description for the model

        Returns:
            Model: The created Model entity (can be used for set_default_generation, etc.)

        Raises:
            ValueError: If provider is not set on this LLM class

        Example:
            >>> from rhesis.sdk.models.factory import get_model
            >>> llm = get_model("openai", "gpt-4", api_key="sk-...")
            >>> model = llm.push(name="My GPT-4 Production")
            >>> model.set_default_generation()
        """
        from rhesis.sdk.entities.model import Model

        provider = getattr(self, "PROVIDER", None)
        if not provider:
            raise ValueError(
                "Cannot push LLM: PROVIDER class variable is not set. "
                "This LLM implementation does not support push()."
            )

        # Extract model name (remove provider prefix if present, e.g., "openai/gpt-4" -> "gpt-4")
        model_name = (
            self.model_name.split("/", 1)[-1]
            if self.model_name and "/" in self.model_name
            else self.model_name
        )

        # Get API key if available
        api_key = getattr(self, "api_key", None)

        model = Model(
            name=name,
            description=description,
            provider=provider,
            model_name=model_name,
            key=api_key,
        )
        model.push()
        return model


class BaseEmbedder(ABC):
    """Base class for embedding models."""

    def __init__(self, model_name: str, *args, **kwargs):
        self.model_name = model_name

    @abstractmethod
    def generate(self, text: str, **kwargs) -> Embedding:
        """Generate embedding for a single text.

        Args:
            text: The input text to embed.
            **kwargs: Additional parameters (e.g., dimensions).

        Returns:
            A list of floats representing the embedding vector.
        """
        pass

    @abstractmethod
    def generate_batch(self, texts: List[str], **kwargs) -> List[Embedding]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of input texts to embed.
            **kwargs: Additional parameters (e.g., dimensions).

        Returns:
            A list of embedding vectors, one for each input text.
        """
        pass

    def get_model_name(self) -> str:
        return f"Class name: {self.__class__.__name__}, model name: {self.model_name}"
