import json
from typing import Optional, Type, Union

import litellm
from litellm import completion
from pydantic import BaseModel

from rhesis.sdk.errors import NO_MODEL_NAME_PROVIDED
from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.models.utils import validate_llm_response

litellm.suppress_debug_info = True


class LiteLLM(BaseLLM):
    def __init__(self, model_name: str, api_key: Optional[str] = None):
        """
        LiteLLM: LiteLLM Provider for Model inference

        This class provides an interface for interacting with all models accessible through LiteLLM.

        Args:
            model_name (str): The name of the model to use including the provider.
            api_key (Optional[str]): The API key for authentication.
             If not provided, LiteLLM will handle it internally.

        Usage:
            >>> llm = LiteLLM(model_name="provider/model", api_key="your_api_key")
            >>> result = llm.generate(prompt="Tell me a joke.", system_prompt="You are funny")
            >>> print(result)

        If a Pydantic schema is provided to `generate`, the response will be validated and returned
        as a dict.
        """
        self.api_key = api_key  # LiteLLM will handle Environment Retrieval
        if not model_name or not isinstance(model_name, str) or model_name.strip() == "":
            raise ValueError(NO_MODEL_NAME_PROVIDED)
        super().__init__(model_name)

    def load_model(self):
        """
        LiteLLM handles model loading internally, so no loading is needed
        """
        pass

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        schema: Optional[Type[BaseModel]] = None,
        *args,
        **kwargs,
    ) -> Union[str, dict]:
        """
        Run a chat completion using LiteLLM, returning the response.
        The schema will be used to validate the response if provided.
        """
        # handle system prompt
        messages = (
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}]
            if system_prompt
            else [{"role": "user", "content": prompt}]
        )

        # Handle schema format for LiteLLM
        # LiteLLM expects either a Pydantic model or {"type": "json_object"} for JSON mode
        response_format = schema
        if schema and isinstance(schema, dict):
            # OpenAI-wrapped schema: use JSON mode and we'll validate manually after
            response_format = {"type": "json_object"}

        # Call the completion function passing given arguments
        response = completion(
            model=self.model_name,
            messages=messages,
            response_format=response_format,
            api_key=self.api_key,
            *args,
            **kwargs,
        )

        response_content = response.choices[0].message.content  # type: ignore
        if schema:
            # Strip markdown code fences if present (```json ... ```)
            if isinstance(response_content, str):
                response_content = response_content.strip()
                if response_content.startswith("```"):
                    # Remove opening fence (```json or ```)
                    lines = response_content.split("\n", 1)
                    if len(lines) > 1:
                        response_content = lines[1]
                    # Remove closing fence
                    if response_content.endswith("```"):
                        response_content = response_content[:-3]
                    response_content = response_content.strip()
            
            response_content = json.loads(response_content)
            validate_llm_response(response_content, schema)
            return response_content
        else:
            return response_content
