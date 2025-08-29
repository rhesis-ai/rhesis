import json
import os
from typing import Any, Dict, List, Optional

import requests

from rhesis.sdk.client import Client
from rhesis.sdk.services.base import BaseLLM

DEFAULT_MODEL_NAME = "rhesis-llm-v1"


class RhesisLLMService(BaseLLM):
    """Service for interacting with the LLM API endpoints."""

    def __init__(
        self, model_name: str = DEFAULT_MODEL_NAME, api_key=None, base_url=None, **kwargs
    ) -> None:
        self.api_key = api_key or os.getenv("RHESIS_API_KEY")
        self.base_url = base_url or os.getenv("RHESIS_BASE_URL")

        if self.api_key is None:
            raise ValueError("RHESIS_API_KEY is not set")

        super().__init__(model_name, **kwargs)

    def load_model(self) -> Any:
        self.client = Client(api_key=self.api_key, base_url=self.base_url)
        self.headers = {
            "Authorization": f"Bearer {self.client.api_key}",
            "Content-Type": "application/json",
        }
        return self

    def generate(self, prompt: str, response_format: str = "json_object", **kwargs: Any) -> Any:
        """Run a chat completion using the API, and return the response."""
        try:
            response = self.create_completion(
                messages=[{"role": "user", "content": prompt}],
                response_format=response_format,
                **kwargs,
            )
            response_content = response["choices"][0]["message"]["content"]

            if response_format == "json_object":
                try:
                    return json.loads(response_content)
                except json.JSONDecodeError as e:
                    # Return the raw content for the synthesizer to handle
                    print(f"JSON parsing failed: {e}. Returning raw content for custom parsing.")
                    return response_content

            return response_content

        except (requests.exceptions.HTTPError, KeyError, IndexError) as e:
            # Log the error and return an appropriate message
            print(f"Error occurred while running the prompt: {e}")
            if response_format == "json_object":
                return {"error": "An error occurred while processing the request."}

            return "An error occurred while processing the request."

    def create_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4000,
        response_format: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Create a chat completion using the API.

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate (increased default for larger responses)
            **kwargs: Additional parameters to pass to the API

        Returns:
            Dict[str, Any]: The raw response from the API

        Raises:
            requests.exceptions.HTTPError: If the API request fails
            ValueError: If the response cannot be parsed
        """
        request_data = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": response_format,
            **kwargs,
        }

        response = requests.post(
            self.client.get_url("services/chat/completions"),
            headers=self.headers,
            json=request_data,
        )

        response.raise_for_status()
        result: Dict[str, Any] = response.json()
        return result


if __name__ == "__main__":
    model = RhesisLLMService(model_name="rhesis-llm-v1")
    print(
        model.generate(
            prompt="What is the capital of France? Return json with answer and reasoning"
        )
    )
