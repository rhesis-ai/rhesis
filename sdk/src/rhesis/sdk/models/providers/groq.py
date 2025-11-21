import os

from rhesis.sdk.models.providers.litellm import LiteLLM

DEFAULT_MODEL_NAME = "llama3-8b-8192"


class GroqLLM(LiteLLM):
    PROVIDER = "groq"

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME, api_key=None, **kwargs):
        """
        GroqLLM: Groq LLM Provider

        This class provides an interface to the Groq family of large language models via LiteLLM.

        Args:
            model_name (str): The name of the Groq model to use (default: "llama3-8b-8192").
            api_key (str, optional): API key for Groq. If not provided, will use GROQ_API_KEY
             from environment.
            **kwargs: Additional parameters passed to the underlying LiteLLM completion call.

        Usage:
            >>> llm = GroqLLM(model_name="llama3-8b-8192")
            >>> result = llm.generate("Tell me a joke.")
            >>> print(result)

        If a Pydantic schema is provided to `generate`, the response will be validated and returned
        as a dict.

        Raises:
            ValueError: If the API key is not set.
        """
        api_key = api_key or os.getenv("GROQ_API_KEY")
        if api_key is None:
            raise ValueError("GROQ_API_KEY is not set")
        super().__init__(self.PROVIDER + "/" + model_name, api_key=api_key)
