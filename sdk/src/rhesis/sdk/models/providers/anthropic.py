import os

from rhesis.sdk.models.providers.litellm import LiteLLM

PROVIDER = "anthropic"
DEFAULT_MODEL_NAME = "claude-4"


class AnthropicLLM(LiteLLM):
    def __init__(self, model_name: str = DEFAULT_MODEL_NAME, api_key=None, **kwargs):
        """
        AnthropicLLM: Anthropic LLM Provider

        This class provides an interface to the Anthropic family of large language models via LiteLLM.

        Args:
            model_name (str): The name of the Anthropic model to use (default: "claude-4").
            api_key (str, optional): API key for Anthropic. If not provided, will use ANTHROPIC_API_KEY
             from environment.
            **kwargs: Additional parameters passed to the underlying LiteLLM completion call.

        Usage:
            >>> llm = AnthropicLLM(model_name="claude-4")
            >>> result = llm.generate("Tell me a joke.")
            >>> print(result)

        If a Pydantic schema is provided to `generate`, the response will be validated and returned
        as a dict.

        Raises:
            ValueError: If the API key is not set.
        """
        api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if api_key is None:
            raise ValueError("ANTHROPIC_API_KEY is not set")
        super().__init__(PROVIDER + "/" + model_name, api_key=api_key)
