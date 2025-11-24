import os

from rhesis.sdk.models.providers.litellm import LiteLLM

DEFAULT_MODEL_NAME = "gemini-2.5-flash-lite"


class GeminiLLM(LiteLLM):
    PROVIDER = "gemini"

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME, api_key=None, **kwargs):
        """
        GeminiLLM: Google Gemini LLM Provider

        This class provides an interface to the Gemini family of large language models via LiteLLM.

        Args:
            model_name (str): The name of the Gemini model to use (default: "gemini-2.0-flash").
            api_key (str, optional): API key for Gemini. If not provided, will use GEMINI_API_KEY
             from environment.
            **kwargs: Additional parameters passed to the underlying LiteLLM completion call.

        Usage:
            >>> llm = GeminiLLM(model_name="gemini-pro")
            >>> result = llm.generate("Tell me a joke.")
            >>> print(result)

        If a Pydantic schema is provided to `generate`, the response will be validated and returned
        as a dict.

        Raises:
            ValueError: If the API key is not set.
        """
        api_key = api_key or os.getenv("GEMINI_API_KEY")
        if api_key is None:
            raise ValueError("GEMINI_API_KEY is not set")
        super().__init__(self.PROVIDER + "/" + model_name, api_key=api_key)
