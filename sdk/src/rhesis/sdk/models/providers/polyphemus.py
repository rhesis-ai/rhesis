import json
import os
import re
from typing import Any, Dict, Optional, Type

import requests
from pydantic import BaseModel

from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.models.utils import validate_llm_response

DEFAULT_POLYPHEMUS_URL = "https://polyphemus.rhesis.ai"


class PolyphemusLLM(BaseLLM):
    """Service for interacting with the Polyphemus API endpoints."""

    def __init__(self, model_name: str = "", api_key=None, base_url=None, **kwargs) -> None:
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
            # If schema is provided, augment the prompt to request JSON output
            if schema:
                json_schema = schema.model_json_schema()
                schema_instruction = (
                    f"\n\nYou must respond with valid JSON matching this schema:\n"
                    f"```json\n{json.dumps(json_schema, indent=2)}\n```\n"
                    f"Only return the JSON object, nothing else. "
                    f"Do not include explanations or markdown."
                )
                prompt = prompt + schema_instruction

            # Build messages array
            messages = []

            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            messages.append({"role": "user", "content": prompt})

            response = self.create_completion(
                messages=messages,
                **kwargs,
            )

            # Extract the assistant's message content from the response
            if "choices" in response and len(response["choices"]) > 0:
                content = response["choices"][0]["message"]["content"]

                # Strip reasoning tokens if include_reasoning is False
                if not include_reasoning:
                    content = self._strip_reasoning_tokens(content)

                # If schema was provided, parse and validate the JSON response
                if schema:
                    response_dict = json.loads(content)
                    validate_llm_response(response_dict, schema)
                    return response_dict

                return content

            # Return appropriate type based on whether schema was provided
            if schema:
                return {"error": "No response generated."}
            return "No response generated."

        except (requests.exceptions.HTTPError, KeyError, IndexError, json.JSONDecodeError) as e:
            # Log the error and return an appropriate message
            print(f"Error occurred while running the prompt: {e}")
            if schema:
                return {"error": "An error occurred while processing the request."}

            return "An error occurred while processing the request."

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
        temperature: float = 0.7,
        max_tokens: int = 512,
        stream: bool = False,
        repetition_penalty: float = 1.2,
        top_p: float = 0,
        top_k: int = 0,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Create a chat completion using the Polyphemus API.

        Args:
            messages: List of message objects with role and content
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate
            stream: Whether to stream the response
            repetition_penalty: Penalty for repetition
            top_p: Top-p sampling parameter
            top_k: Top-k sampling parameter
            **kwargs: Additional parameters to pass to the API

        Returns:
            Dict[str, Any]: The response from the API containing choices, model, and usage

        Raises:
            requests.exceptions.HTTPError: If the API request fails
            ValueError: If the response cannot be parsed
        """
        request_data = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
            "repetition_penalty": repetition_penalty,
            "top_p": top_p,
            "top_k": top_k,
            **kwargs,
        }

        # Only include model if it's specified
        if self.model_name:
            request_data["model"] = self.model_name

        url = f"{self.base_url}/generate"

        response = requests.post(
            url,
            headers=self.headers,
            json=request_data,
        )

        response.raise_for_status()
        result: Dict[str, Any] = response.json()
        return result
