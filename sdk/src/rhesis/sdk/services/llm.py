import json
from typing import Any, List, Dict, Optional

from litellm import completion, ModelResponse
import litellm

from rhesis.sdk.errors import JSON_MODE_ERROR_INVALID_JSON, GENERAL_MODEL_ERROR_PROCESSING_REQUEST
from rhesis.sdk.services.providers.rhesis_ import RhesisLLMHandler


class LLMService:
    def __init__(self, model: str = "ollama/llama2") -> None:
        self.model = model
        litellm.custom_provider_map.append(
            {
                "provider": "rhesis",
                "custom_handler": RhesisLLMHandler(),
            },
        )

    def run(self,
            prompt: str,
            system_prompt: Optional[str] = None,
            response_format: Optional[str] = None,
            **kwargs: Any) -> Any:
        """Run a chat completion using LiteLLM, returning the response."""
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ] if system_prompt else [
                {"role": "user", "content": prompt},
            ]

            response = completion(
                self.model,
                prompt=prompt,
                response_format={"type": response_format} if response_format else None,
                messages=messages,
                **kwargs,
            )

            response_content = response["choices"][0]["message"]["content"]

            if response_format == "json_object":
                try:
                    return json.loads(response_content)
                except json.JSONDecodeError as e:
                    print(JSON_MODE_ERROR_INVALID_JSON.format(error=e))
                    return response_content


            return response_content

        except Exception as e:
            print(GENERAL_MODEL_ERROR_PROCESSING_REQUEST.format(error=e))
            if response_format == "json_object":
                return {"error": "An error occurred while processing the request."}
            return "An error occurred while processing the request."
