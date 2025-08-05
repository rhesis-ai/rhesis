from typing import Optional, Dict, Any

from rhesis.polyphemus.benchmarking.models.abstract_model import Model, ModelProvider, Invocation, ModelResponse


class MockModel(Model):
    """
    Abstract base class for LLM models.
    Provides a consistent interface for different LLM providers.
    """

    def __init__(self, name: str, location: str):
        super(MockModel, self).__init__()
        self.name = name
        self.location = location
        self.provider = ModelProvider.NONE
        self.tokens_used = 0

    def load_model(self):
        """
        Load the model from its location.
        This method should be implemented by subclasses to handle model loading.
        """
        pass

    def unload_model(self):
        """
        Unload the model to free up resources.
        This method should be implemented by subclasses to handle model unloading.
        """
        pass

    def generate_response(self, request: Invocation) -> ModelResponse:
        """
        Generate a response for the given request.

        Args:
            request: The ModelRequest containing prompt and parameters

        Returns:
            ModelResponse with the generated content and metadata
        """
        return ModelResponse(
            content="",
            model_name=self.name,
            model_location=self.location,
            provider=self.provider,
            request=request,
            tokens_used=0,
            response_time=0.0,
        )

    def get_recommended_request(self, prompt: str, system_prompt: Optional[str], additional_params: Optional[Dict[str, Any]]) -> Invocation:
        """
        Get a request object for the given prompt containing the standard
        recommended parameters for the given model.
        """
        return Invocation(prompt=prompt, system_prompt=system_prompt, additional_params=additional_params)
