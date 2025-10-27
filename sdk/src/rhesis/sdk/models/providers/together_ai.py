import os

from rhesis.sdk.models.providers.litellm import LiteLLM

PROVIDER = "together_ai"
DEFAULT_MODEL_NAME = "togethercomputer/llama-2-70b-chat"


class TogetherAILLM(LiteLLM):
    def __init__(self, model_name: str = DEFAULT_MODEL_NAME, api_key=None, **kwargs):
        """
        TogetherAILLM: Together AI LLM Provider

        This class provides an interface to the Together AI family of large language models via
        LiteLLM.

        Args:
            model_name (str): The name of the Together AI model to use
            (default: "togethercomputer/llama-2-70b-chat").  api_key (str, optional): API key for
            Together AI. If not provided, will use TOGETHERAI_API_KEY
            from environment.
            **kwargs: Additional parameters passed to the underlying LiteLLM completion call.

        Usage:
            >>> llm = TogetherAILLM(model_name="togethercomputer/llama-2-70b-chat")
            >>> result = llm.generate("Tell me a joke.")
            >>> print(result)

        If a Pydantic schema is provided to `generate`, the response will be validated and returned
        as a dict.

        Raises:
            ValueError: If the API key is not set.
        """
        api_key = api_key or os.getenv("TOGETHERAI_API_KEY")
        if api_key is None:
            raise ValueError("TOGETHERAI_API_KEY is not set")
        super().__init__(PROVIDER + "/" + model_name, api_key=api_key)
