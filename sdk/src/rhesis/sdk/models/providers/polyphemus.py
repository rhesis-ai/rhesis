import json
import logging
import os
import re
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

    def generate_batch(
        self,
        prompts: List[str],
        system_prompt: Optional[str] = None,
        schema: Optional[Type[BaseModel]] = None,
        include_reasoning: bool = False,
        **kwargs: Any,
    ) -> List[Any]:
        """Batch processing is not implemented for PolyphemusLLM."""
        raise NotImplementedError("generate_batch is not implemented for PolyphemusLLM")

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
        request_data = {
            "messages": messages,
            **kwargs,
        }

        # Only include model if it's specified
        if self.model_name:
            request_data["model"] = self.model_name

        url = f"{self.base_url}/generate"

        logger.debug(f"Polyphemus request URL: {url}")
        logger.debug(f"Polyphemus request body: {json.dumps(request_data, default=str)}")

        response = requests.post(
            url,
            headers=self.headers,
            json=request_data,
        )

        if response.status_code != 200:
            logger.error(
                f"Polyphemus error: status={response.status_code}, body={response.text}"
            )
        response.raise_for_status()
        result: Dict[str, Any] = response.json()
        return result
