# Import DeepEvalBaseLLM for proper custom model implementation

from typing import Any, Optional

from deepeval.models.base_model import DeepEvalBaseLLM

from rhesis.sdk.models.base import BaseLLM


class DeepEvalModelWrapper(DeepEvalBaseLLM):
    def __init__(self, model: BaseLLM) -> None:
        self._model = model

    def load_model(self, *args, **kwargs):  # type: ignore[override]
        return self._model.load_model(*args, **kwargs)

    def generate(self, prompt: str, schema: Optional[Any] = None, **kwargs) -> str:
        """
        Generate response from the model.

        Args:
            prompt: The prompt to generate from
            schema: Optional schema for structured output (ignored for compatibility)
            **kwargs: Additional generation parameters

        Returns:
            Generated response string
        """
        # Note: schema parameter is accepted for DeepEval compatibility
        # but not used since our base models don't support structured output yet
        return self._model.generate(prompt, **kwargs)  # type: ignore[return-value]

    async def a_generate(self, prompt: str, schema: Optional[Any] = None, **kwargs) -> str:
        """
        Async generate response from the model.

        Args:
            prompt: The prompt to generate from
            schema: Optional schema for structured output (ignored for compatibility)
            **kwargs: Additional generation parameters

        Returns:
            Generated response string
        """
        # Delegate to synchronous generate (async support can be added later)
        return self.generate(prompt, schema=schema, **kwargs)

    def get_model_name(self, *args, **kwargs) -> str:
        return self._model.get_model_name(*args, **kwargs)
