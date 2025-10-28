import os

from rhesis.sdk.models.providers.litellm import LiteLLM

PROVIDER = "mistral"
DEFAULT_MODEL_NAME = "mistral-medium-latest"


class MistralLLM(LiteLLM):
    def __init__(self, model_name: str = DEFAULT_MODEL_NAME, api_key=None, **kwargs):
        """
        MistralLLM: Mistral LLM Provider

        This class provides an interface to the Mistral family of large language models via LiteLLM.

        Args:
            model_name (str): The name of the Mistral model to use
            (default: "mistral-medium-latest").
            api_key (str, optional): API key for Mistral. If not provided, will use MISTRAL_API_KEY
             from environment.
            **kwargs: Additional parameters passed to the underlying LiteLLM completion call.

        Usage:
            >>> llm = MistralLLM(model_name="mistral-medium-latest")
            >>> result = llm.generate("Tell me a joke.")
            >>> print(result)

        If a Pydantic schema is provided to `generate`, the response will be validated and returned
        as a dict.

        Raises:
            ValueError: If the API key is not set.
        """
        api_key = api_key or os.getenv("MISTRAL_API_KEY")
        if api_key is None:
            raise ValueError("MISTRAL_API_KEY is not set")
        super().__init__(PROVIDER + "/" + model_name, api_key=api_key)
