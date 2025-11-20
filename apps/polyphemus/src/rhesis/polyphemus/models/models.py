"""
Model implementations for Polyphemus service.
Contains different model classes that can be used based on configuration.
"""

import logging
from typing import Any, Dict, Optional, Union

from rhesis.sdk.models import BaseLLM
from rhesis.sdk.models.factory import get_model

logger = logging.getLogger("rhesis-polyphemus")

# Default model for TinyLLM
DEFAULT_MODEL = "huggingface/distilgpt2"


class TinyLLM(BaseLLM):
    """
    TinyLLM model class that can load any LLM model based on user requirements.

    This is a flexible model wrapper that uses the SDK's get_model factory
    to load any supported model type (HuggingFace, OpenAI, Anthropic, etc.)
    based on the model name/type provided.

    The model name can be specified in the format:
    - "provider/model-name" (e.g., "huggingface/distilgpt2", "openai/gpt-4o")
    - "model-name" (defaults to huggingface provider)
    """

    def __init__(self, model_name: Optional[str] = None, auto_loading: bool = True):
        """
        Initialize TinyLLM model.

        Args:
            model_name: Model identifier in format "provider/model" or just model name.
                If None, uses default model (huggingface/distilgpt2).
            auto_loading: Whether to automatically load the model on initialization.
                If False, model loading is deferred until load_model() is called.
        """
        # Use default model if not provided
        self._model_name = model_name or DEFAULT_MODEL
        self._auto_loading = auto_loading
        self._internal_model: Optional[BaseLLM] = None

        # Set model_name for BaseLLM compatibility (don't call super().__init__
        # as it would trigger load_model immediately)
        self.model_name = self._model_name
        self.model = None
        self.tokenizer = None

        if auto_loading:
            self.load_model()

    def load_model(self) -> BaseLLM:
        """
        Load the model using the SDK's get_model factory.

        The model can be any supported type (HuggingFace, OpenAI, etc.)
        based on the model_name format.

        Returns:
            self: Returns self for method chaining
        """
        if self._internal_model is None:
            logger.info(f"Loading model: {self._model_name}")

            # Use SDK's get_model factory to create the appropriate model
            # The factory handles provider/model parsing automatically
            # Pass auto_loading=False via kwargs to defer model loading
            try:
                self._internal_model = get_model(self._model_name, auto_loading=False)
            except TypeError:
                # If auto_loading is not supported, create without it and load manually
                self._internal_model = get_model(self._model_name)

            # Load the model (for HuggingFace models, this loads model and tokenizer)
            if hasattr(self._internal_model, "load_model"):
                self._internal_model.load_model()

            # For HuggingFace models, fix pad_token if needed
            if (
                hasattr(self._internal_model, "tokenizer")
                and self._internal_model.tokenizer is not None
            ):
                if self._internal_model.tokenizer.pad_token is None:
                    self._internal_model.tokenizer.pad_token = (
                        self._internal_model.tokenizer.eos_token
                    )

            # Set model attribute for compatibility
            if hasattr(self._internal_model, "model"):
                self.model = self._internal_model.model
            if hasattr(self._internal_model, "tokenizer"):
                self.tokenizer = self._internal_model.tokenizer

            logger.info(f"Model loaded successfully: {self._model_name}")

        return self

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        schema: Optional[Any] = None,
        **kwargs,
    ) -> Union[str, Dict[str, Any]]:
        """
        Generate a response using the loaded model.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            schema: Optional schema for structured output
            **kwargs: Additional generation parameters

        Returns:
            str or dict: Generated response
        """
        if self._internal_model is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        # Delegate to the internal model
        return self._internal_model.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            schema=schema,
            **kwargs,
        )
