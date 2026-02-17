from typing import Optional, Type, Union

from pydantic import BaseModel

from rhesis.sdk.models.providers.litellm import LiteLLM

"""
According to the LiteLLM documentation, the Provider has to be set to ollama_chat for better
responses.
https://docs.litellm.ai/docs/providers/ollama#using-ollama-apichat
"""

DEFAULT_MODEL_NAME = "llama3.1"


class OllamaLLM(LiteLLM):
    PROVIDER = "ollama_chat"

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME, **kwargs):
        """
        OllamaLLM: Ollama LLM Provider

        This class provides an interface to the Ollama family of large language models via LiteLLM.

        In order to use this class, you need to have Ollama installed and running.
        See https://ollama.com/download for more information.

        Each model before the use should be downloaded using the following command:
        >> ollama pull <model_name>

        Args:
            model_name (str): The name of the Ollama model to use (default: "llama3.1").
            **kwargs: Additional parameters passed to the underlying LiteLLM completion call.

        Usage:
            >>> llm = OllamaLLM(model_name="llama3.1")
            >>> result = llm.generate("Tell me a joke.")
            >>> print(result)

        If a Pydantic schema is provided to `generate`, the response will be validated and returned
        as a dict.

        Raises:
            ValueError: If the API key is not set.
        """
        self.api_base = kwargs.get("api_base", "http://localhost:11434")
        super().__init__(self.PROVIDER + "/" + model_name)

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        schema: Optional[Type[BaseModel]] = None,
    ) -> Union[str, dict]:
        return super().generate(prompt, system_prompt, schema, api_base=self.api_base)
