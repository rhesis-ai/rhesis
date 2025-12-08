"""
Model implementations for Polyphemus service.
Contains different model classes that can be used based on configuration.
"""

import logging
import os
from typing import Any, Dict, Optional, Union

from rhesis.sdk.models import BaseLLM
from rhesis.sdk.models.factory import get_model

logger = logging.getLogger("rhesis-polyphemus")

# Default model for LazyModelLoader - can be overridden via environment variable
DEFAULT_MODEL = os.environ.get("DEFAULT_MODEL", "huggingface/distilgpt2")

# Model path configuration - supports local path or GCS bucket location
# For GCS paths (gs://...), HuggingFace will load directly without downloading
MODEL_PATH = os.environ.get("MODEL_PATH", "")


class LazyModelLoader(BaseLLM):
    """
    LazyModelLoader model class that can load any LLM model based on user requirements.

    This is a flexible model wrapper that uses the SDK's get_model factory
    to load any supported model type (HuggingFace, OpenAI, Anthropic, etc.)
    based on the model name/type provided.

    The model name can be specified in the format:
    - "provider/model-name" (e.g., "huggingface/distilgpt2", "openai/gpt-4o")
    - "model-name" (defaults to huggingface provider)
    """

    def __init__(self, model_name: Optional[str] = None, auto_loading: bool = True):
        """
        Initialize LazyModelLoader model.

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

        If MODEL_PATH is configured:
        - For local paths: loads from local disk
        - For GCS paths (gs://...): loads directly from GCS without downloading
          (saves container memory by streaming model files to GPU)
        - If not set: uses HuggingFace Hub to download model

        The model can be any supported type (HuggingFace, OpenAI, etc.)
        based on the model_name format.

        Returns:
            self: Returns self for method chaining
        """
        if self._internal_model is None:
            logger.info(f"Loading model: {self._model_name}")

            # Determine the model path to use
            model_path = None
            if MODEL_PATH:
                # For GCS paths, construct the full path to the model directory
                if MODEL_PATH.startswith("gs://"):
                    model_name_dir = self._model_name.split("/")[-1]
                    model_path = f"{MODEL_PATH}/{model_name_dir}"
                    logger.info(f"Loading directly from GCS (no download): {model_path}")
                else:
                    # Use local path directly
                    model_path = MODEL_PATH
                    logger.info(f"Loading from local path: {model_path}")
            else:
                # No MODEL_PATH set - will use HuggingFace Hub
                logger.info("No MODEL_PATH set, will download from HuggingFace Hub")

            if model_path:
                logger.info(f"Model path: {model_path}")

            # Use SDK's get_model factory to create the appropriate model
            # Pass auto_loading=False and model_path via kwargs
            # Configure load_kwargs for memory optimization
            # Use torch_dtype (not dtype) for HuggingFace models
            default_load_kwargs = {"torch_dtype": "float16"}

            # Allow override via environment variable for advanced configurations
            # Examples:
            # - 8-bit: LOAD_KWARGS='{"load_in_8bit": true, "device_map": "auto"}'
            # - 4-bit: LOAD_KWARGS='{"load_in_4bit": true, "device_map": "auto"}'
            load_kwargs_env = os.environ.get("LOAD_KWARGS")
            if load_kwargs_env:
                import json

                try:
                    default_load_kwargs = json.loads(load_kwargs_env)
                    logger.info(f"Using custom load_kwargs from env: {default_load_kwargs}")
                except json.JSONDecodeError:
                    logger.warning(
                        f"Invalid LOAD_KWARGS JSON, using default: {default_load_kwargs}"
                    )

            try:
                self._internal_model = get_model(
                    self._model_name,
                    auto_loading=False,
                    model_path=model_path,
                    load_kwargs=default_load_kwargs,
                )
            except TypeError:
                # If model_path is not supported by this model type, try without it
                logger.info("model_path not supported for this model type, creating without it")
                self._internal_model = get_model(self._model_name, auto_loading=False)

            # Load the model (for HuggingFace models, this loads model and tokenizer)
            if hasattr(self._internal_model, "load_model"):
                self._internal_model.load_model()

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
