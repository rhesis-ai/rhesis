import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional, Type, Union

import requests
from litellm.llms.base_llm.base_utils import type_to_response_format_param
from pydantic import BaseModel

from rhesis.sdk.errors import NO_MODEL_NAME_PROVIDED
from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.models.utils import validate_llm_response

logger = logging.getLogger(__name__)

DEFAULT_API_BASE = "http://0.0.0.0:4000"
DEFAULT_REQUEST_TIMEOUT = int(os.getenv("LITELLM_PROXY_TIMEOUT", "300"))


class LiteLLMProxy(BaseLLM):
    """LLM provider that sends OpenAI-compatible requests to a LiteLLM Proxy server.

    Unlike the LiteLLM provider (which uses the litellm Python library directly),
    this provider makes raw HTTP requests to a running LiteLLM Proxy instance
    that exposes an OpenAI-compatible /chat/completions endpoint.

    Args:
        model_name: The model name as configured in the proxy (e.g. "gemini").
        api_base: Base URL of the LiteLLM Proxy server.
            Defaults to LITELLM_PROXY_BASE_URL env var or http://0.0.0.0:4000.
        api_key: Optional API key for the proxy.
            Defaults to LITELLM_PROXY_API_KEY env var.

    Usage:
        >>> llm = LiteLLMProxy(model_name="gemini")
        >>> result = llm.generate(
        ...     prompt="what is your name?",
        ...     system_prompt="You are an LLM Arkadiusz Kwasigroch",
        ... )
        >>> print(result)
    """

    PROVIDER = "litellm_proxy"

    def __init__(
        self,
        model_name: str,
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
        **kwargs,
    ):
        if not model_name or not isinstance(model_name, str) or model_name.strip() == "":
            raise ValueError(NO_MODEL_NAME_PROVIDED)

        self.api_base = api_base or os.getenv("LITELLM_PROXY_BASE_URL") or DEFAULT_API_BASE
        self.api_key = api_key or os.getenv("LITELLM_PROXY_API_KEY")
        super().__init__(model_name, **kwargs)

    def load_model(self) -> None:
        """The proxy handles model loading, so no local loading is needed."""
        pass

    def _build_headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        schema: Optional[Union[Type[BaseModel], dict]] = None,
        *args,
        **kwargs,
    ) -> Union[str, dict]:
        """Run a chat completion via the LiteLLM Proxy.

        Args:
            prompt: The user prompt.
            system_prompt: Optional system prompt.
            schema: Either a Pydantic model or OpenAI-wrapped JSON schema dict
                for structured output validation.

        Returns:
            str or dict: Raw text if no schema, validated dict if schema provided.

        Raises:
            requests.exceptions.HTTPError: If the proxy returns a non-2xx status.
        """
        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            **kwargs,
        }

        if schema:
            if isinstance(schema, type) and issubclass(schema, BaseModel):
                # Use LiteLLM's helper so the emitted JSON schema satisfies
                # OpenAI/Azure strict mode (e.g. additionalProperties: false on
                # every object node, including nested $defs).
                payload["response_format"] = type_to_response_format_param(response_format=schema)
            elif isinstance(schema, dict):
                payload["response_format"] = schema

        url = f"{self.api_base.rstrip('/')}/chat/completions"

        logger.debug(
            "[LiteLLMProxy] POST %s | model=%s | prompt_chars=%d",
            url,
            self.model_name,
            len(prompt),
        )

        response = requests.post(
            url,
            headers=self._build_headers(),
            json=payload,
            timeout=DEFAULT_REQUEST_TIMEOUT,
        )
        response.raise_for_status()

        data = response.json()
        content = data["choices"][0]["message"]["content"]

        if schema:
            content = json.loads(content)
            validate_llm_response(content, schema)

        return content

    async def a_generate(self, *args, **kwargs) -> Union[str, dict]:
        """Async version of generate. Runs sync generate() in a thread pool."""
        return await asyncio.to_thread(self.generate, *args, **kwargs)

    def generate_batch(
        self,
        prompts: List[str],
        system_prompt: Optional[str] = None,
        schema: Optional[Union[Type[BaseModel], dict]] = None,
        n: int = 1,
        *args,
        **kwargs,
    ) -> List[Union[str, dict]]:
        """Run batch chat completions by sequentially calling the proxy.

        Args:
            prompts: List of user prompts.
            system_prompt: Optional system prompt (applied to all prompts).
            schema: Either a Pydantic model or OpenAI-wrapped JSON schema dict.
            n: Number of completions to generate per prompt.

        Returns:
            List of str or dict responses, n results per prompt in order.
        """
        results: List[Union[str, dict]] = []
        for prompt in prompts:
            for _ in range(n):
                result = self.generate(
                    prompt,
                    system_prompt=system_prompt,
                    schema=schema,
                    **kwargs,
                )
                results.append(result)
        return results
