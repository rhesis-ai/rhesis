# Import DeepEvalBaseLLM for proper custom model implementation

import inspect
import json
from typing import Any, Optional, Union

from deepeval.models.base_model import DeepEvalBaseLLM

from rhesis.sdk.models.base import BaseLLM


class DeepEvalModelWrapper(DeepEvalBaseLLM):
    def __init__(self, model: BaseLLM) -> None:
        self._model = model

    def load_model(self, *args, **kwargs):  # type: ignore[override]
        return self._model.load_model(*args, **kwargs)

    def generate(self, prompt: str, schema: Optional[Any] = None, **kwargs) -> Union[str, Any]:
        """
        Generate response from the model with optional structured output.

        Args:
            prompt: The prompt to generate from
            schema: Optional Pydantic schema for structured output
            **kwargs: Additional generation parameters

        Returns:
            Generated response (str or schema instance if schema provided)
        """
        # Check if underlying model's generate() accepts schema parameter
        model_generate_sig = inspect.signature(self._model.generate)
        supports_schema = "schema" in model_generate_sig.parameters

        # Generate response
        if supports_schema:
            # Model supports schema natively
            result = self._model.generate(prompt, schema=schema, **kwargs)
        else:
            # Model doesn't support schema, generate as string
            result = self._model.generate(prompt, **kwargs)

        # If schema provided and result is a string, try to parse it
        if schema is not None and isinstance(result, str):
            try:
                # Try to parse JSON and create schema instance
                parsed_json = json.loads(result)
                # Assume schema is a Pydantic model
                return schema(**parsed_json)
            except (json.JSONDecodeError, TypeError, ValueError):
                # If parsing fails, return the string as-is
                # DeepEval will handle the error
                return result

        return result  # type: ignore[return-value]

    async def a_generate(
        self, prompt: str, schema: Optional[Any] = None, **kwargs
    ) -> Union[str, Any]:
        """
        Async generate response from the model with optional structured output.

        Args:
            prompt: The prompt to generate from
            schema: Optional Pydantic schema for structured output
            **kwargs: Additional generation parameters

        Returns:
            Generated response (str or schema instance if schema provided)
        """
        # Delegate to synchronous generate (async support can be added later)
        return self.generate(prompt, schema=schema, **kwargs)

    def get_model_name(self, *args, **kwargs) -> str:
        return self._model.get_model_name(*args, **kwargs)
