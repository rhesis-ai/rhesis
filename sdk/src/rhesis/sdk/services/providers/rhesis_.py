from litellm import CustomLLM, ModelResponse
import requests
from typing import Any, Dict, List
from rhesis.sdk.client import Client


class RhesisLLMHandler(CustomLLM):
    """
    LiteLLM custom handler for the Rhesis hosted models.
    """

    def __init__(self):
        super().__init__()
        self.client = Client()
        self.headers = {
            "Authorization": f"Bearer {self.client.api_key}",
            "Content-Type": "application/json",
        }

    def completion(
            self,
            messages: List[Dict[str, str]],
            **kwargs: Any,
    ) -> ModelResponse:
        """
        Create a chat completion using your hosted API.

        This method is called by LiteLLM to get the model's response.
        """
        model_name = kwargs.get("model")

        print(f"Calling Rhesis model: {model_name}")

        request_data = {
            "messages": messages,
            "stream": kwargs.get("stream", False),
        }

        response = requests.post(
            self.client.get_url("services/chat/completions"),
            headers=self.headers,
            json=request_data,
        )
        response.raise_for_status()

        return ModelResponse(**response.json())