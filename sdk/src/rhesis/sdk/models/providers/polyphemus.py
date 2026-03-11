import asyncio
import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Type

import jsonfinder
import requests
from pydantic import BaseModel

from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.models.defaults import DEFAULT_LANGUAGE_MODELS, model_name_from_id
from rhesis.sdk.models.utils import validate_llm_response

logger = logging.getLogger(__name__)

DEFAULT_MODEL = DEFAULT_LANGUAGE_MODELS["polyphemus"]
DEFAULT_MODEL_NAME = model_name_from_id(DEFAULT_MODEL)
DEFAULT_POLYPHEMUS_URL = os.getenv("DEFAULT_POLYPHEMUS_URL") or "https://polyphemus.rhesis.ai"
DEFAULT_REQUEST_TIMEOUT = int(os.getenv("RHESIS_LLM_TIMEOUT", "300"))  # 5 minutes


class PolyphemusLLM(BaseLLM):
    """Service for interacting with the Polyphemus API endpoints."""

    def __init__(
        self, model_name: str = DEFAULT_MODEL_NAME, api_key=None, base_url=None, **kwargs
    ) -> None:
        """
        PolyphemusLLM: Polyphemus LLM Provider

        This class provides an interface to the Polyphemus API for generating text
        using various Hugging Face models.

        Args:
            model_name (str, optional): The name of the model to use.
                If not provided, the API will use its default model.
            api_key (str, optional): API key for Polyphemus. If not provided,
                will use RHESIS_API_KEY from environment.
            base_url (str, optional): Base URL for the Polyphemus API.
                If not provided, will use DEFAULT_POLYPHEMUS_URL.
            **kwargs: Additional parameters passed to the underlying client.

        Usage:
            >>> llm = PolyphemusLLM()
            >>> result = llm.generate("Tell me a joke.")
            >>> print(result)

        Raises:
            ValueError: If the API key is not set.
        """
        self.api_key = api_key or os.getenv("RHESIS_API_KEY")
        self.base_url = base_url or DEFAULT_POLYPHEMUS_URL

        if self.api_key is None:
            raise ValueError("RHESIS_API_KEY is not set")

        super().__init__(model_name, **kwargs)

    def load_model(self) -> Any:
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "accept": "application/json",
        }
        return self

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        schema: Optional[Type[BaseModel]] = None,
        include_reasoning: bool = False,
        **kwargs: Any,
    ) -> Any:
        """
        Run a chat completion using the Polyphemus API, and return the response.

        Args:
            prompt: The user prompt to send
            system_prompt: Optional system prompt
            schema: Optional Pydantic BaseModel for structured output
            include_reasoning: If True, include reasoning tokens within <think> tags.
                If False (default), strip out reasoning tokens.
            **kwargs: Additional parameters passed to create_completion

        Returns:
            str if no schema provided, dict if schema provided
        """
        try:
            # If schema is provided, augment the system prompt to request JSON output
            if schema:
                schema_description = json.dumps(schema.model_json_schema(), indent=2)
                schema_instructions = (
                    "\nRespond strictly in valid JSON matching this schema"
                    " and filling all fields\n" + f"{schema_description}"
                )

                # Build system prompt with /no_think prefix, existing prompt and schema instructions
                if system_prompt:
                    system_prompt = "/no_think\n" + system_prompt + schema_instructions
                else:
                    system_prompt = "/no_think" + schema_instructions

            # Build messages array
            messages = []

            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            messages.append({"role": "user", "content": prompt})

            response = self.create_completion(
                messages=messages,
                json_schema=schema.model_json_schema() if schema else None,
                **kwargs,
            )

            # Extract the assistant's message content from the response
            if "choices" in response and len(response["choices"]) > 0:
                content = response["choices"][0]["message"]["content"]

                # If schema was provided, parse and validate the JSON response
                if schema:
                    parsed = self._extract_json(content)
                    if not parsed:
                        logger.error("No valid JSON found in response")
                        return {"error": "No valid JSON found in response."}
                    validate_llm_response(parsed, schema)
                    return parsed

                # Strip reasoning tokens if include_reasoning is False
                if not include_reasoning:
                    content = self._strip_reasoning_tokens(content)

                return content

            # Return appropriate type based on whether schema was provided
            if schema:
                return {"error": "No response generated."}
            return "No response generated."

        except (requests.exceptions.HTTPError, KeyError, IndexError, json.JSONDecodeError) as e:
            # Log the error and return an appropriate message
            logger.error(f"Error occurred while running the prompt: {e}", exc_info=True)
            if schema:
                return {"error": "An error occurred while processing the request."}

            return "An error occurred while processing the request."

    async def a_generate(self, *args, **kwargs) -> Any:
        """Async version of generate. Runs sync generate() in a thread pool."""
        return await asyncio.to_thread(self.generate, *args, **kwargs)

    def generate_batch(
        self,
        prompts: List[str],
        system_prompt: Optional[str] = None,
        schema: Optional[Type[BaseModel]] = None,
        include_reasoning: bool = False,
        **kwargs: Any,
    ) -> List[Any]:
        """
        Run chat completions for multiple prompts using the Polyphemus API.

        Applies the same schema/system_prompt and post-processing as generate() to
        each prompt. Results are returned in the same order as prompts. Failed
        items return an error string or {"error": "..."} when schema is set.

        Args:
            prompts: List of user prompts to send.
            system_prompt: Optional system prompt (shared by all).
            schema: Optional Pydantic BaseModel for structured output.
            include_reasoning: If False, strip <think> tokens from each response.
            **kwargs: Additional parameters passed to the API for all requests.

        Returns:
            List of results (str or dict per prompt, same semantics as generate()).
        """
        if not prompts:
            return []

        # Separate HTTP-client-only kwargs from API-level kwargs so that
        # client options like "timeout" are never forwarded in the JSON body.
        _CLIENT_ONLY = {"timeout"}
        timeout = kwargs.get("timeout")
        api_kwargs = {k: v for k, v in kwargs.items() if k not in _CLIENT_ONLY}

        requests_list: List[Dict[str, Any]] = []
        for prompt in prompts:
            sys = system_prompt
            if schema:
                schema_description = json.dumps(schema.model_json_schema(), indent=2)
                schema_instructions = (
                    "\nRespond strictly in valid JSON matching this schema"
                    " and filling all fields\n" + schema_description
                )
                if sys:
                    sys = "/no_think\n" + sys + schema_instructions
                else:
                    sys = "/no_think" + schema_instructions

            messages: List[Dict[str, str]] = []
            if sys:
                messages.append({"role": "system", "content": sys})
            messages.append({"role": "user", "content": prompt})

            req: Dict[str, Any] = {
                "messages": messages,
                "json_schema": schema.model_json_schema() if schema else None,
                **api_kwargs,
            }
            if self.model_name:
                req["model"] = self.model_name
            requests_list.append(req)

        def err_placeholder(msg: str) -> Any:
            return {"error": msg} if schema else msg

        try:
            batch_response = self.create_batch_completion(requests_list, timeout=timeout)
        except requests.exceptions.HTTPError as e:
            logger.error("Batch request failed: %s", e, exc_info=True)
            return [err_placeholder("An error occurred while processing the request.")] * len(
                prompts
            )

        results: List[Any] = []
        for item in batch_response.get("responses", []):
            if item.get("error"):
                results.append(err_placeholder(str(item["error"])))
                continue
            choices = item.get("choices", [])
            if not choices:
                results.append(err_placeholder("No response generated."))
                continue
            content = choices[0].get("message", {}).get("content", "")
            if schema:
                parsed = self._extract_json(content)
                if not parsed:
                    results.append({"error": "No valid JSON found in response."})
                else:
                    try:
                        validate_llm_response(parsed, schema)
                        results.append(parsed)
                    except Exception as e:
                        logger.warning("Validation failed for batch item: %s", e)
                        results.append({"error": "Validation failed."})
            else:
                if not include_reasoning:
                    content = self._strip_reasoning_tokens(content)
                results.append(content)

        # Guarantee result list length matches input length.
        # Fill any missing items (server returned fewer than requested).
        while len(results) < len(prompts):
            logger.warning(
                "Server returned %d responses for %d prompts; padding with errors.",
                len(results),
                len(prompts),
            )
            results.append(err_placeholder("No response from server."))

        # Trim any surplus items (should never happen, but be defensive).
        return results[: len(prompts)]

    def _extract_json(self, output: str) -> str:
        """
        Extract the JSON part of a text. Return the last found JSON object
        as a JSON string, or "" if none found.
        """
        last = ""
        for _, _, obj in jsonfinder.jsonfinder(output):
            if obj is not None:
                last = obj
        return last

    def _strip_reasoning_tokens(self, content: str) -> str:
        """
        Remove reasoning tokens enclosed in <think>...</think> tags.

        Args:
            content: The content that may contain reasoning tokens

        Returns:
            Content with reasoning tokens removed
        """
        # Remove <think>...</think> tags and their content
        # Use re.DOTALL to match across newlines
        cleaned_content = re.sub(
            r"<think>.*?</think>", "", content, flags=re.DOTALL | re.IGNORECASE
        )
        # Strip any extra whitespace that may be left
        return cleaned_content.strip()

    def create_completion(
        self,
        messages: list,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Create a chat completion using the Polyphemus API.

        Args:
            messages: List of message objects with role and content
            **kwargs: Additional parameters to pass to the API

        Returns:
            Dict[str, Any]: The response from the API containing choices, model, and usage

        Raises:
            requests.exceptions.HTTPError: If the API request fails
            ValueError: If the response cannot be parsed
        """
        timeout = kwargs.pop("timeout", DEFAULT_REQUEST_TIMEOUT)

        request_data = {
            "messages": messages,
            **kwargs,
        }

        # Only include model if it's specified
        if self.model_name:
            request_data["model"] = self.model_name

        url = f"{self.base_url}/generate"

        # Calculate prompt size for debugging
        total_prompt_chars = sum(len(m.get("content", "")) for m in messages)
        logger.debug(
            "[Polyphemus] POST %s | model=%s | messages=%d | prompt_chars=%d",
            url,
            request_data.get("model"),
            len(request_data.get("messages", [])),
            total_prompt_chars,
        )

        request_start = time.time()
        response = requests.post(
            url,
            headers=self.headers,
            json=request_data,
            timeout=timeout,
        )
        request_elapsed = time.time() - request_start

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError:
            logger.error(
                "[Polyphemus] HTTP %s after %.1fs",
                getattr(response, "status_code", "?"),
                request_elapsed,
            )
            raise

        logger.debug(
            "[Polyphemus] HTTP 200 in %.1fs",
            request_elapsed,
        )

        result: Dict[str, Any] = response.json()

        # Log usage info if available
        usage = result.get("usage", {})
        if usage:
            logger.debug(
                "[Polyphemus] Token usage: prompt=%s, completion=%s, total=%s",
                usage.get("prompt_tokens", "?"),
                usage.get("completion_tokens", "?"),
                usage.get("total_tokens", "?"),
            )

        return result

    def create_batch_completion(
        self,
        requests_list: List[Dict[str, Any]],
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Create multiple chat completions in one request using the Polyphemus API.

        Args:
            requests_list: List of request dicts (messages, optional model,
                json_schema, temperature, max_tokens, etc. per item).
            **kwargs: Optional timeout for the HTTP request.

        Returns:
            Dict with "responses" key containing a list of response dicts
            (choices, model, usage) or {"error": str} per item.

        Raises:
            requests.exceptions.HTTPError: If the API request fails
        """
        request_data: Dict[str, Any] = {"requests": requests_list}
        url = f"{self.base_url}/generate_batch"
        timeout = kwargs.get("timeout")
        if timeout is None:
            timeout = DEFAULT_REQUEST_TIMEOUT

        logger.debug(
            "[Polyphemus] POST %s | batch_size=%d",
            url,
            len(requests_list),
        )

        request_start = time.time()
        response = requests.post(
            url,
            headers=self.headers,
            json=request_data,
            timeout=timeout,
        )
        request_elapsed = time.time() - request_start

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError:
            logger.error(
                "[Polyphemus] HTTP %s after %.1fs (batch)",
                getattr(response, "status_code", "?"),
                request_elapsed,
            )
            raise

        logger.debug("[Polyphemus] HTTP 200 in %.1fs (batch)", request_elapsed)
        return response.json()
