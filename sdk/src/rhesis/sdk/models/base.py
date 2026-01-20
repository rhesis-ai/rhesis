from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, List, Union

if TYPE_CHECKING:
    from rhesis.sdk.models.content import ContentPart, Message


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

    def get_available_models(self) -> List[str]:
        raise NotImplementedError("Subclasses must implement this method")

    def generate_multimodal(
        self, messages: List["Message"], schema: Any = None, **kwargs
    ) -> Union[str, Dict[str, Any]]:
        """Generate a response from multimodal messages.

        This method supports messages containing mixed content types including
        text, images, audio, video, and files.

        Args:
            messages: List of Message objects with potentially mixed content
            schema: Optional Pydantic model or JSON schema for structured output
            **kwargs: Additional provider-specific parameters

        Returns:
            String response or dict if schema provided

        Raises:
            NotImplementedError: If model doesn't support multimodal generation
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support multimodal generation. "
            "Use generate() for text-only prompts."
        )

    def analyze_content(
        self, content: Union["ContentPart", List["ContentPart"]], prompt: str, **kwargs
    ) -> str:
        """Analyze content (image, audio, video, file) with a text prompt.

        Convenience method for single-turn content analysis.

        Args:
            content: Single ContentPart or list of ContentPart objects
            prompt: Question/instruction about the content
            **kwargs: Additional parameters

        Returns:
            Text analysis/description

        Raises:
            NotImplementedError: If model doesn't support content analysis
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not support content analysis.")

    def generate_image(
        self, prompt: str, n: int = 1, size: str = "1024x1024", **kwargs
    ) -> Union[str, List[str]]:
        """Generate images from a text prompt.

        Args:
            prompt: Text description of the image to generate
            n: Number of images to generate (default: 1)
            size: Image size (e.g., "1024x1024", "512x512")
            **kwargs: Additional provider-specific parameters

        Returns:
            URL(s) of generated image(s). Single URL if n=1, list if n>1

        Raises:
            NotImplementedError: If model doesn't support image generation
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not support image generation.")
