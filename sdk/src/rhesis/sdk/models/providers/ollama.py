from typing import Optional

from rhesis.sdk.models.defaults import DEFAULT_LANGUAGE_MODELS, model_name_from_id
from rhesis.sdk.models.providers.litellm import LiteLLM

"""
According to the LiteLLM documentation, the Provider has to be set to ollama_chat for better
responses.
https://docs.litellm.ai/docs/providers/ollama#using-ollama-apichat
"""

DEFAULT_MODEL = DEFAULT_LANGUAGE_MODELS["ollama"]
DEFAULT_MODEL_NAME = model_name_from_id(DEFAULT_MODEL)


class OllamaLLM(LiteLLM):
    PROVIDER = "ollama_chat"

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        api_base: Optional[str] = None,
        **kwargs,
    ):
        """
        OllamaLLM: Ollama LLM Provider

        This class provides an interface to the Ollama family of large language models via LiteLLM.

        In order to use this class, you need to have Ollama installed and running.
        See https://ollama.com/download for more information.

        Each model before the use should be downloaded using the following command:
        >> ollama pull <model_name>

        Args:
            model_name (str): The name of the Ollama model to use (default: "llama3.1").
            api_base (Optional[str]): The Ollama server URL.
                Defaults to http://localhost:11434.
            **kwargs: Additional parameters passed to the underlying LiteLLM completion call.

        Usage:
            >>> llm = OllamaLLM(model_name="llama3.1")
            >>> result = llm.generate("Tell me a joke.")
            >>> print(result)

        If a Pydantic schema is provided to `generate`, the response will be validated and returned
        as a dict.
        """
        super().__init__(
            self.PROVIDER + "/" + model_name,
            api_base=api_base or "http://localhost:11434",
        )
