import logging
from typing import Any, Optional, Union

from deepeval.models.base_model import DeepEvalBaseLLM

from rhesis.sdk.async_utils import run_sync
from rhesis.sdk.models.base import BaseLLM

logger = logging.getLogger(__name__)


class DeepEvalModelWrapper(DeepEvalBaseLLM):
    def __init__(self, model: BaseLLM) -> None:
        self._model = model

    def load_model(self, *args, **kwargs):  # type: ignore[override]
        return self._model.load_model(*args, **kwargs)

    def _convert_to_schema(self, result: Any, schema: Any) -> Any:
        # Raise TypeError on failure so DeepEval's unstructured fallback triggers.
        if isinstance(result, schema):
            return result
        try:
            if isinstance(result, dict) and hasattr(schema, "model_validate"):
                return schema.model_validate(result)
            return schema(**result)
        except Exception as e:
            schema_name = getattr(schema, "__name__", str(schema))
            logger.warning(f"Failed to convert to {schema_name}: {e}")
            raise TypeError(f"Cannot convert to {schema_name}: {e}") from e

    def generate(self, prompt: str, schema: Optional[Any] = None, **kwargs) -> Union[str, Any]:
        return run_sync(self.a_generate(prompt=prompt, schema=schema, **kwargs))

    async def a_generate(
        self, prompt: str, schema: Optional[Any] = None, **kwargs
    ) -> Union[str, Any]:
        result = await self._model.a_generate(prompt, schema=schema, **kwargs)
        return self._convert_to_schema(result, schema) if schema else result

    def get_model_name(self, *args, **kwargs) -> str:
        return self._model.get_model_name(*args, **kwargs)
