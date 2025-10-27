import os

from rhesis.sdk.models.providers.litellm import LiteLLM

PROVIDER = "meta_llama"
DEFAULT_MODEL_NAME = "Llama-3.3-70B-Instruct"


class MetaLlamaLLM(LiteLLM):
    def __init__(self, model_name: str = DEFAULT_MODEL_NAME, api_key=None, **kwargs):
        """
        MetaLlamaLLM: Meta Llama LLM Provider

        This class provides an interface to the Meta Llama family of large language models via LiteLLM.

        Args:
            model_name (str): The name of the Meta Llama model to use (default: "Llama-3.3-70B-Instruct").
            api_key (str, optional): API key for Meta Llama. If not provided, will use LLAMA_API_KEY
             from environment.
            **kwargs: Additional parameters passed to the underlying LiteLLM completion call.

        Usage:
            >>> llm = MetaLlamaLLM(model_name="Llama-3.3-70B-Instruct")
            >>> result = llm.generate("Tell me a joke.")
            >>> print(result)

        If a Pydantic schema is provided to `generate`, the response will be validated and returned
        as a dict.

        Raises:
            ValueError: If the API key is not set.
        """
        api_key = api_key or os.getenv("LLAMA_API_KEY")
        if api_key is None:
            raise ValueError("LLAMA_API_KEY is not set")
        super().__init__(PROVIDER + "/" + model_name, api_key=api_key)


