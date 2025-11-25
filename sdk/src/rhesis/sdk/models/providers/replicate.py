import os

from rhesis.sdk.models.providers.litellm import LiteLLM

DEFAULT_MODEL_NAME = "llama-2-70b-chat"


class ReplicateLLM(LiteLLM):
    PROVIDER = "replicate"

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME, api_key=None, **kwargs):
        """
        ReplicateLLM: Replicate LLM Provider

        This class provides an interface to the Replicate family of large language models
        via LiteLLM.

        Args:
            model_name (str): The name of the Replicate model to use (default: "llama-2-70b-chat").
            api_key (str, optional): API key for Replicate. If not provided, will use
            REPLICATE_API_KEY from environment.
            **kwargs: Additional parameters passed to the underlying LiteLLM completion call.

        Usage:
            >>> llm = ReplicateLLM(model_name="llama-2-70b-chat")
            >>> result = llm.generate("Tell me a joke.")
            >>> print(result)

        If a Pydantic schema is provided to `generate`, the response will be validated and returned
        as a dict.

        Raises:
            ValueError: If the API key is not set.
        """
        api_key = api_key or os.getenv("REPLICATE_API_KEY")
        if api_key is None:
            raise ValueError("REPLICATE_API_KEY is not set")
        super().__init__(self.PROVIDER + "/" + model_name, api_key=api_key)
