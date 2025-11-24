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

        # If schema provided, try to convert result to schema object
        if schema is not None:
            if isinstance(result, str):
                return self._parse_to_schema(result, schema)
            elif isinstance(result, dict):
                # Result is already a dict, try to instantiate schema
                return self._dict_to_schema(result, schema)

        return result  # type: ignore[return-value]

    def _parse_to_schema(self, result: str, schema: Any) -> Union[str, Any]:
        """
        Parse string result to Pydantic schema object.

        Args:
            result: String result from model
            schema: Pydantic schema class

        Returns:
            Schema instance or original string if parsing fails
        """
        try:
            # Try to parse JSON
            parsed_json = json.loads(result)
            return self._dict_to_schema(parsed_json, schema)

        except json.JSONDecodeError:
            # Not valid JSON, return string as-is
            return result
        except Exception:
            # Catch-all for any other errors
            return result

    def _dict_to_schema(self, data: Any, schema: Any) -> Any:
        """
        Convert dict/list data to Pydantic schema object.

        Args:
            data: Parsed JSON data (dict or list)
            schema: Pydantic schema class

        Returns:
            Schema instance or original data if conversion fails
        """
        try:
            # If data is a dict, try to instantiate schema
            if isinstance(data, dict):
                try:
                    schema_instance = schema(**data)

                    # Verify it's a proper Pydantic instance, not a dict
                    if isinstance(schema_instance, dict):
                        # Schema constructor returned a dict somehow
                        # This shouldn't happen with Pydantic but handle it
                        # Try using model_validate if available (Pydantic v2)
                        if hasattr(schema, "model_validate"):
                            return schema.model_validate(data)
                        # Try parse_obj for Pydantic v1
                        elif hasattr(schema, "parse_obj"):
                            return schema.parse_obj(data)
                        # Fall back to returning the dict
                        return data

                    return schema_instance

                except (TypeError, ValueError, AttributeError):
                    # Direct instantiation failed, try Pydantic validators
                    if hasattr(schema, "model_validate"):
                        # Pydantic v2
                        return schema.model_validate(data)
                    elif hasattr(schema, "parse_obj"):
                        # Pydantic v1
                        return schema.parse_obj(data)
                    # If all fails, return original data
                    return data

            # If data is a list or other type, return as-is
            return data

        except Exception:
            # If all parsing attempts fail, return original data
            return data

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
