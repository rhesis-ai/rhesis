import json
from typing import List, Optional, Type, Union

import litellm
from litellm import batch_completion, completion
from pydantic import BaseModel

from rhesis.sdk.errors import NO_MODEL_NAME_PROVIDED
from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.models.utils import validate_llm_response

litellm.suppress_debug_info = True


class LiteLLM(BaseLLM):
    PROVIDER: str

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
        schema: Optional[Union[Type[BaseModel], dict]] = None,
        *args,
        **kwargs,
    ) -> Union[str, dict]:
        """
        Run a chat completion using LiteLLM, returning the response.
        The schema will be used to validate the response if provided.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            schema: Either a Pydantic model or OpenAI-wrapped JSON schema dict

        Returns:
            str or dict: Raw text if no schema, validated dict if schema provided
        """
        # handle system prompt
        messages = (
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}]
            if system_prompt
            else [{"role": "user", "content": prompt}]
        )

        # Handle schema format for LiteLLM
        # Dict schemas must already be in OpenAI-wrapped format
        # LiteLLM can handle both Pydantic models and OpenAI-wrapped dicts directly
        response_format = schema

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
            response_content = json.loads(response_content)
            validate_llm_response(response_content, schema)
            return response_content
        else:
            return response_content

    def generate_batch(
        self,
        prompts: List[str],
        system_prompt: Optional[str] = None,
        schema: Optional[Union[Type[BaseModel], dict]] = None,
        n: int = 1,
        *args,
        **kwargs,
    ) -> List[Union[str, dict]]:
        """
        Run batch chat completions using LiteLLM, returning a list of responses.
        Each prompt generates n responses.

        Args:
            prompts: List of user prompts
            system_prompt: Optional system prompt (applied to all prompts)
            schema: Either a Pydantic model or OpenAI-wrapped JSON schema dict
            n: Number of completions to generate per prompt

        Returns:
            List of str or dict: Raw text if no schema, validated dicts if schema provided.
            The list contains n responses for each prompt, in order.
        """
        # Convert prompts to message format for litellm batch_completion
        if system_prompt:
            messages = [
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ]
                for prompt in prompts
            ]
        else:
            messages = [[{"role": "user", "content": prompt}] for prompt in prompts]

        # Handle schema format for LiteLLM
        response_format = schema

        # Use litellm batch_completion
        responses = batch_completion(
            model=self.model_name,
            messages=messages,
            response_format=response_format,
            api_key=self.api_key,
            n=n,
            *args,
            **kwargs,
        )

        # Extract content from responses (each response has n choices)
        results: List[Union[str, dict]] = []
        for response in responses:
            for choice in response.choices:
                content = choice.message.content
                if schema:
                    content = json.loads(content)
                    validate_llm_response(content, schema)
                results.append(content)

        return results

    @classmethod
    def get_available_models(cls) -> List[str]:
        models_list = litellm.get_valid_models(
            custom_llm_provider=cls.PROVIDER,
            check_provider_endpoint=False,
        )
        # Remove provider prefix from model names
        models_list = [model.replace(cls.PROVIDER + "/", "") for model in models_list]
        # Remove vision models from the list
        models_list = [model for model in models_list if "vision" not in model]
        # Remove embedding models from the list
        models_list = [model for model in models_list if "embedding" not in model]
        # Remove audio models from the list
        models_list = [model for model in models_list if "audio" not in model]
        # Remove image models from the list
        models_list = [model for model in models_list if "image" not in model]
        # Remove video models from the list
        models_list = [model for model in models_list if "video" not in model]

        return models_list
