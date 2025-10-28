import os

from rhesis.sdk.models.providers.litellm import LiteLLM

PROVIDER = "perplexity"
DEFAULT_MODEL_NAME = "sonar-pro"


class PerplexityLLM(LiteLLM):
    def __init__(self, model_name: str = DEFAULT_MODEL_NAME, api_key=None, **kwargs):
        """
        PerplexityLLM: Perplexity AI LLM Provider

        This class provides an interface to the Perplexity AI family of large language models via
        LiteLLM.

        Args:
            model_name (str): The name of the Perplexity model to use (default: "sonar-pro").
            api_key (str, optional): API key for Perplexity AI. If not provided, will use
            PERPLEXITYAI_API_KEY from environment.
            **kwargs: Additional parameters passed to the underlying LiteLLM completion call.

        Usage:
            >>> llm = PerplexityLLM(model_name="sonar-pro")
            >>> result = llm.generate("Tell me a joke.")
            >>> print(result)

        If a Pydantic schema is provided to `generate`, the response will be validated and returned
        as a dict.

        Raises:
            ValueError: If the API key is not set.
        """
        api_key = api_key or os.getenv("PERPLEXITYAI_API_KEY")
        if api_key is None:
            raise ValueError("PERPLEXITYAI_API_KEY is not set")
        super().__init__(PROVIDER + "/" + model_name, api_key=api_key)
