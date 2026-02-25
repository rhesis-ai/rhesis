from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

if TYPE_CHECKING:
    from rhesis.sdk.entities.model import Model

# Type alias for embeddings
Embedding = List[float]


class BaseModel(ABC):
    """Common base class for all model types (language, embedding, future: image)."""

    PROVIDER: str = ""  # Subclasses should override this
    MODEL_TYPE: str = ""  # "language", "embedding", "image" - subclasses should override

    def __init__(self, model_name: str, *args, **kwargs):
        self.model_name = model_name

    def get_model_name(self) -> str:
        return f"{self.__class__.__name__}: {self.model_name}"

    def push(self, name: str, description: Optional[str] = None) -> "Model":
        """Save this model configuration to the Rhesis platform as a Model entity.

        Creates a Model entity with this model's provider, model name, and API key,
        then saves it to the platform.

        Args:
            name: Name for the saved model configuration (required)
            description: Optional description for the model

        Returns:
            Model: The created Model entity

        Raises:
            ValueError: If provider is not set on this model class

        Example:
            >>> model = get_model("openai/gpt-4", api_key="sk-...")
            >>> model_entity = model.push(name="My Production Model")
        """
        from rhesis.sdk.entities.model import Model

        provider = getattr(self, "PROVIDER", None)
        if not provider:
            raise ValueError(
                "Cannot push model: PROVIDER class variable is not set. "
                "This model implementation does not support push()."
            )

        # Extract model name (remove provider prefix if present)
        model_name = (
            self.model_name.split("/", 1)[-1]
            if self.model_name and "/" in self.model_name
            else self.model_name
        )

        # Get API key if available
        api_key = getattr(self, "api_key", None)

        # Determine model_type from MODEL_TYPE class variable ("language" or "embedding")
        model_type = getattr(self, "MODEL_TYPE", "language")

        model = Model(
            name=name,
            description=description,
            provider=provider,
            model_name=model_name,
            model_type=model_type,
            key=api_key,
        )
        model.push()
        return model


class BaseLLM(BaseModel):
    MODEL_TYPE = "language"

    def __init__(self, model_name, *args, **kwargs):
        super().__init__(model_name, *args, **kwargs)
        self.model = self.load_model(*args, **kwargs)

        # Wrap generate with retry for transient errors and error responses
        from rhesis.sdk.models.utils import llm_retry

        self.generate = llm_retry(self.generate)

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

    def get_available_models(self) -> List[str]:
        raise NotImplementedError("Subclasses must implement this method")


class BaseEmbedder(BaseModel):
    """Base class for embedding models."""

    MODEL_TYPE = "embedding"

    def __init__(self, model_name: str, *args, **kwargs):
        super().__init__(model_name, *args, **kwargs)

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

    def get_available_models(self) -> List[str]:
        """Get the list of available embedding models for this provider.

        Subclasses should override this method to return provider-specific embedding models.

        Returns:
            List of embedding model names

        Raises:
            NotImplementedError: If the subclass doesn't implement this method
        """
        raise NotImplementedError("Subclasses must implement this method")
