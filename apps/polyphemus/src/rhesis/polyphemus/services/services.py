"""
Polyphemus service - Model instance management for inference.
This module provides model instances that can be used across the application.
Models are loaded lazily on first request to avoid blocking application startup.
Models are selected based on user request (model parameter in generate endpoint).
Default model is LazyModelLoader.
"""

import asyncio
import logging
import os
from typing import Optional

from rhesis.polyphemus.models import LazyModelLoader

from rhesis.sdk.models import BaseLLM

logger = logging.getLogger("rhesis-polyphemus")

# Model cache: maps model identifier to model instance
_model_cache: dict[str, BaseLLM] = {}

# Async lock for thread-safe model loading
_model_lock = asyncio.Lock()

# Default model identifier - can be overridden via environment variable
DEFAULT_MODEL = os.environ.get("DEFAULT_MODEL", "huggingface/distilgpt2")


def is_model_loaded(model_name: Optional[str] = None) -> bool:
    """
    Check if a model instance is initialized and loaded.
    Non-blocking check that doesn't trigger model loading.

    Args:
        model_name: Model identifier. If None, checks default model.

    Returns:
        bool: True if model is loaded, False otherwise
    """
    model_id = model_name or DEFAULT_MODEL
    if model_id not in _model_cache:
        return False

    model = _model_cache[model_id]
    # Check if model has model/tokenizer attributes (HuggingFace models)
    if hasattr(model, "model") and hasattr(model, "tokenizer"):
        return model.model is not None and model.tokenizer is not None
    # For other model types, assume loaded if in cache
    return True


async def get_polyphemus_instance(model_name: Optional[str] = None) -> BaseLLM:
    """
    Get or create a model instance with lazy async initialization.

    The model is only loaded on first access, not at module import time.
    This prevents blocking application startup and aligns with the design intent
    that models should load on first request.

    Models are cached by model identifier, so subsequent requests for the same
    model will reuse the cached instance.

    Args:
        model_name: Model identifier in format "provider/model" or just model name.
            If None, uses default model (LazyModelLoader with huggingface/distilgpt2).

    Returns:
        BaseLLM: The model instance
    """
    # Use default model if not provided
    model_id = model_name or DEFAULT_MODEL

    # Check if model is already cached (fast path)
    if model_id in _model_cache:
        logger.debug(f"Using cached model instance for: {model_id}")
        return _model_cache[model_id]

    # Model not in cache - need to load it
    async with _model_lock:
        # Double-check pattern: another coroutine might have initialized it while we waited
        if model_id in _model_cache:
            logger.debug(f"Model was cached by another coroutine: {model_id}")
            return _model_cache[model_id]

        logger.info(f"Initializing LazyModelLoader with model: {model_id} (first time)")

        try:
            # Create LazyModelLoader instance with auto_loading=False to defer model loading
            model_instance = LazyModelLoader(model_name=model_id, auto_loading=False)

            # Load model asynchronously in executor to avoid blocking event loop
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, model_instance.load_model)

            # Cache the model instance
            _model_cache[model_id] = model_instance

            logger.info(
                f"Model instance cached and ready: {model_id}, "
                f"model loaded: {getattr(model_instance, 'model', None) is not None}, "
                f"cache size: {len(_model_cache)}"
            )
            return _model_cache[model_id]
        except Exception as load_error:
            # If model loading fails, log error
            logger.error(f"Failed to load model '{model_id}': {str(load_error)}")
            # Only fall back if this wasn't already the default model
            if model_id != DEFAULT_MODEL:
                # Exit lock context before recursive call to avoid deadlock
                pass
            else:
                # If default also fails, re-raise the error
                raise

    # If we get here, the requested model failed and we should fall back to default
    # (lock is now released, safe to make recursive call)
    if model_id != DEFAULT_MODEL:
        logger.info(f"Falling back to default model: {DEFAULT_MODEL}")
        default_model = await get_polyphemus_instance(model_name=None)
        # Cache the default model under the requested model_id to avoid retrying failures
        _model_cache[model_id] = default_model
        return default_model
    else:
        # This shouldn't happen, but if it does, raise the original error
        raise RuntimeError(f"Failed to load default model: {DEFAULT_MODEL}")
