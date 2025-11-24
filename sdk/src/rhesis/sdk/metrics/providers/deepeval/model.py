# Import DeepEvalBaseLLM for proper custom model implementation

import inspect
import json
import logging
from typing import Any, Optional, Union

from deepeval.models.base_model import DeepEvalBaseLLM

from rhesis.sdk.models.base import BaseLLM

logger = logging.getLogger(__name__)


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

        # If schema provided, try to convert result to schema instance
        if schema is not None:
            # If result is a string, parse as JSON first
            if isinstance(result, str):
                try:
                    parsed_json = json.loads(result)
                except (json.JSONDecodeError, ValueError):
                    # If parsing fails, return the string as-is
                    # DeepEval will handle the error
                    return result
            elif isinstance(result, dict):
                # Result is already a dict
                parsed_json = result
            else:
                # Result is some other type, return as-is
                return result

            # Try to instantiate the Pydantic schema
            try:
                schema_instance = schema(**parsed_json)
                logger.debug(
                    f"Successfully instantiated schema {schema.__name__} "
                    f"from parsed data with keys: {list(parsed_json.keys())}"
                )
                return schema_instance
            except (TypeError, ValueError) as e:
                # If instantiation fails, log and return the raw data
                # This allows DeepEval to provide more specific error messages
                logger.warning(
                    f"Failed to instantiate schema {schema.__name__}: {e}. "
                    f"Returning raw data with keys: {list(parsed_json.keys())}"
                )
                return parsed_json

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
