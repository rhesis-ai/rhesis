# Import DeepEvalBaseLLM for proper custom model implementation

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

    def _convert_to_schema(self, result: Any, schema: Any) -> Any:
        """Convert result to Pydantic schema instance if possible."""
        # Parse string to dict if needed
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except (json.JSONDecodeError, ValueError):
                return result  # Return string, let DeepEval handle error

        # If not a dict at this point, return as-is
        if not isinstance(result, dict):
            return result

        # Try to instantiate schema
        try:
            schema_instance = schema(**result)
            logger.debug(f"Instantiated {schema.__name__} with keys: {list(result.keys())}")
            return schema_instance
        except (TypeError, ValueError) as e:
            logger.warning(f"Failed to instantiate {schema.__name__}: {e}")
            return result  # Return dict as fallback

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
        # Generate response (all our models support schema parameter)
        result = self._model.generate(prompt, schema=schema, **kwargs)

        # Convert to schema if provided
        return self._convert_to_schema(result, schema) if schema else result

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
