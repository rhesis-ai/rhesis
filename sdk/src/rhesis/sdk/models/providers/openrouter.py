import os

from rhesis.sdk.models.providers.litellm import LiteLLM

DEFAULT_MODEL_NAME = "openai/gpt-4o-mini"


class OpenRouterLLM(LiteLLM):
    PROVIDER = "openrouter"

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME, api_key=None):
        """
        OpenRouterLLM: OpenRouter LLM Provider

        This class provides an interface to various language models via OpenRouter using LiteLLM.

        Args:
            model_name (str): The name of the model to use (default: "openai/gpt-4o-mini").
            api_key (str, optional): API key for OpenRouter. If not provided, will use
             OPENROUTER_API_KEY from environment.

        Usage:
            >>> llm = OpenRouterLLM(model_name="anthropic/claude-3.5-sonnet")
            >>> result = llm.generate("Tell me a joke.")
            >>> print(result)

        If a Pydantic schema is provided to `generate`, the response will be validated and returned
        as a dict.

        Raises:
            ValueError: If the API key is not set.
        """
        api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if api_key is None:
            raise ValueError("OPENROUTER_API_KEY is not set")
        super().__init__(self.PROVIDER + "/" + model_name, api_key=api_key)
