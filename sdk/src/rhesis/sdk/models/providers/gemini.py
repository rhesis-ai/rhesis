"""
Available models:
        •	gemini-pro
        •	gemini-1.5-pro-latest
        •	gemini-2.0-flash
        •	gemini-2.0-flash-exp
        •	gemini-2.0-flash-lite-preview-02-05


"""

import json
import os
from typing import Optional, Union

from litellm import completion
from pydantic import BaseModel

from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.models.utils import validate_llm_response

PROVIDER = "gemini"
DEFAULT_MODEL_NAME = "gemini-2.0-flash"


class GeminiLLM(BaseLLM):
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
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if self.api_key is None:
            raise ValueError("GEMINI_API_KEY is not set")
        super().__init__(model_name)

    def load_model(self, *args, **kwargs):
        return None  # LiteLLM handles model loading internally

    def generate(
        self, prompt: str, schema: Optional[BaseModel] = None, *args, **kwargs
    ) -> Union[str, dict]:
        messages = [{"role": "user", "content": prompt}]
        response = completion(
            model=f"{PROVIDER}/{self.model_name}",
            messages=messages,
            response_format=schema,
            api_key=self.api_key,
            *args,
            **kwargs,
        )
        response_content = response.choices[0].message.content
        if schema:
            response_content = json.loads(response_content)
            validate_llm_response(response_content, schema)
            return response_content
        else:
            return response_content
