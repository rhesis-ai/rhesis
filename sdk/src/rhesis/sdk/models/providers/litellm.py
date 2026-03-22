import json
from typing import AsyncIterator, List, Optional, Type, Union

import litellm
from litellm import acompletion, batch_completion, embedding
from pydantic import BaseModel

from rhesis.sdk.errors import NO_MODEL_NAME_PROVIDED
from rhesis.sdk.models.base import BaseEmbedder, BaseLLM, Embedding
from rhesis.sdk.models.utils import validate_llm_response

litellm.suppress_debug_info = True


class LiteLLM(BaseLLM):
    PROVIDER: str

    def __init__(
        self,
        model_name: str,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        api_version: Optional[str] = None,
    ):
        """
        LiteLLM: LiteLLM Provider for Model inference

        This class provides an interface for interacting with all models accessible through LiteLLM.

        Args:
            model_name (str): The name of the model to use including the provider.
            api_key (Optional[str]): The API key for authentication.
             If not provided, LiteLLM will handle it internally.
            api_base (Optional[str]): The base URL for the API endpoint.
                If not provided, LiteLLM uses its default or env vars.
            api_version (Optional[str]): The API version string
                (e.g. for Azure). If not provided, LiteLLM uses its
                default or env vars.

        Usage:
            >>> llm = LiteLLM(model_name="provider/model", api_key="your_api_key")
            >>> result = llm.generate(prompt="Tell me a joke.", system_prompt="You are funny")
            >>> print(result)

        If a Pydantic schema is provided to `generate`, the response will be validated and returned
        as a dict.
        """
        self.api_key = api_key
        self.api_base = api_base
        self.api_version = api_version
        if not model_name or not isinstance(model_name, str) or model_name.strip() == "":
            raise ValueError(NO_MODEL_NAME_PROVIDED)
        super().__init__(model_name)

    def load_model(self):
        """
        LiteLLM handles model loading internally, so no loading is needed
        """
        pass

    async def a_generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        schema: Optional[Union[Type[BaseModel], dict]] = None,
        *args,
        **kwargs,
    ) -> Union[str, dict]:
        """
        Run an async chat completion using LiteLLM, returning the response.
        The schema will be used to validate the response if provided.

        Called directly via ``await model.a_generate(...)`` or indirectly
        through ``model.generate(...)`` which bridges via ``run_sync()``.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            schema: Either a Pydantic model or OpenAI-wrapped JSON schema dict

        Returns:
            str or dict: Raw text if no schema, validated dict if schema provided
        """
        messages = (
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ]
            if system_prompt
            else [{"role": "user", "content": prompt}]
        )

        response = await acompletion(
            model=self.model_name,
            messages=messages,
            response_format=schema,
            api_key=self.api_key,
            api_base=self.api_base,
            api_version=self.api_version,
            *args,
            **kwargs,
        )

        response_content = response.choices[0].message.content  # type: ignore
        if schema:
            response_content = json.loads(response_content)
            validate_llm_response(response_content, schema)
            return response_content
        return response_content

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Stream LLM response token-by-token using litellm async streaming."""
        messages = (
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ]
            if system_prompt
            else [{"role": "user", "content": prompt}]
        )

        response = await acompletion(
            model=self.model_name,
            messages=messages,
            stream=True,
            api_key=self.api_key,
            api_base=self.api_base,
            api_version=self.api_version,
            **kwargs,
        )

        async for chunk in response:
            delta = chunk.choices[0].delta  # type: ignore
            content = getattr(delta, "content", None)
            if content:
                yield content

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

        responses = batch_completion(
            model=self.model_name,
            messages=messages,
            response_format=response_format,
            api_key=self.api_key,
            api_base=self.api_base,
            api_version=self.api_version,
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


class LiteLLMEmbedder(BaseEmbedder):
    """LiteLLM-based embedder supporting multiple providers.

    This class provides an interface for generating embeddings using any model
    accessible through LiteLLM.

    Args:
        model_name: The name of the embedding model (e.g., "text-embedding-3-small").
        api_key: Optional API key. If not provided, LiteLLM uses environment variables.
        dimensions: Optional embedding dimensions (only supported by some models).

    Usage:
        >>> embedder = LiteLLMEmbedder(model_name="text-embedding-3-small")
        >>> embedding = embedder.generate("Hello, world!")
        >>> embeddings = embedder.generate_batch(["Hello", "World"])
    """

    PROVIDER: str

    def __init__(
        self,
        model_name: str,
        api_key: Optional[str] = None,
        dimensions: Optional[int] = None,
    ):
        if not model_name or not isinstance(model_name, str) or model_name.strip() == "":
            raise ValueError(NO_MODEL_NAME_PROVIDED)
        super().__init__(model_name)
        self.api_key = api_key
        self.dimensions = dimensions

    def generate(self, text: str, **kwargs) -> Embedding:
        """Generate embedding for a single text.

        Args:
            text: The input text to embed.
            **kwargs: Additional parameters passed to litellm.embedding().

        Returns:
            A list of floats representing the embedding vector.

        Raises:
            TypeError: If text is not a string.
        """
        if not isinstance(text, str):
            raise TypeError(f"text must be a string, got {type(text).__name__}")

        # Allow overriding dimensions per call
        dimensions = kwargs.pop("dimensions", self.dimensions)

        response = embedding(
            model=self.model_name,
            input=[text],
            api_key=self.api_key,
            dimensions=dimensions,
            **kwargs,
        )
        return response["data"][0]["embedding"]

    def generate_batch(self, texts: List[str], **kwargs) -> List[Embedding]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of input texts to embed.
            **kwargs: Additional parameters passed to litellm.embedding().

        Returns:
            A list of embedding vectors, one for each input text.

        Raises:
            TypeError: If texts is not a list or contains non-string elements.
        """
        if not isinstance(texts, list):
            raise TypeError(f"texts must be a list, got {type(texts).__name__}")
        if not all(isinstance(t, str) for t in texts):
            raise TypeError("all elements in texts must be strings")

        # Allow overriding dimensions per call
        dimensions = kwargs.pop("dimensions", self.dimensions)

        response = embedding(
            model=self.model_name,
            input=texts,
            api_key=self.api_key,
            dimensions=dimensions,
            **kwargs,
        )
        return [item["embedding"] for item in response["data"]]

    @classmethod
    def get_available_models(cls) -> List[str]:
        models_list = litellm.get_valid_models(
            custom_llm_provider=cls.PROVIDER,
            check_provider_endpoint=False,
        )
        models_list = [model.replace(cls.PROVIDER + "/", "") for model in models_list]
        # Keep ONLY embedding models (opposite of LiteLLM filtering)
        models_list = [model for model in models_list if "embedding" in model.lower()]

        return models_list
