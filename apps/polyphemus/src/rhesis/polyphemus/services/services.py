"""
Polyphemus service - Model instance management for inference.
This module provides model instances that can be used across the application.
Models are loaded lazily on first request to avoid blocking application startup.
Models are selected based on user request (model parameter in generate endpoint).
Default model is TinyLLM.
"""

import asyncio
import logging
from typing import Optional

from rhesis.polyphemus.models import TinyLLM

from rhesis.sdk.models import BaseLLM

logger = logging.getLogger("rhesis-polyphemus")

# Model cache: maps model identifier to model instance
_model_cache: dict[str, BaseLLM] = {}

# Async lock for thread-safe model loading
_model_lock = asyncio.Lock()

# Default model identifier
DEFAULT_MODEL = "huggingface/distilgpt2"


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
            If None, uses default model (TinyLLM with huggingface/distilgpt2).

    Returns:
        BaseLLM: The model instance
    """
    # Use default model if not provided
    model_id = model_name or DEFAULT_MODEL

    if model_id not in _model_cache:
        async with _model_lock:
            # Double-check pattern: another coroutine might have initialized it
            if model_id not in _model_cache:
                logger.info(f"Initializing TinyLLM with model: {model_id}")

                # Create TinyLLM instance with auto_loading=False to defer model loading
                model_instance = TinyLLM(model_name=model_id, auto_loading=False)

                # Load model asynchronously in executor to avoid blocking event loop
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, model_instance.load_model)

                # Cache the model instance
                _model_cache[model_id] = model_instance

                logger.info(
                    f"Model instance initialized: {model_id}, "
                    f"model loaded: {getattr(model_instance, 'model', None) is not None}"
                )

    return _model_cache[model_id]
