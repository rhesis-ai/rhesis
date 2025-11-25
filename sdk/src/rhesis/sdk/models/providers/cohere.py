import os

from rhesis.sdk.models.providers.litellm import LiteLLM

DEFAULT_MODEL_NAME = "command-r-plus"


class CohereLLM(LiteLLM):
    PROVIDER = "cohere"

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME, api_key=None, **kwargs):
        """
        CohereLLM: Cohere LLM Provider

        This class provides an interface to the Cohere family of large language models via LiteLLM.

        Args:
            model_name (str): The name of the Cohere model to use (default: "command-r-plus").
            api_key (str, optional): API key for Cohere. If not provided, will use COHERE_API_KEY
             from environment.
            **kwargs: Additional parameters passed to the underlying LiteLLM completion call.

        Usage:
            >>> llm = CohereLLM(model_name="command-r-plus")
            >>> result = llm.generate("Tell me a joke.")
            >>> print(result)

        If a Pydantic schema is provided to `generate`, the response will be validated and returned
        as a dict.

        Raises:
            ValueError: If the API key is not set.
        """
        api_key = api_key or os.getenv("COHERE_API_KEY")
        if api_key is None:
            raise ValueError("COHERE_API_KEY is not set")
        super().__init__(self.PROVIDER + "/" + model_name, api_key=api_key)
