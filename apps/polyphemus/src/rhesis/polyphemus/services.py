"""
Polyphemus service - Singleton instance of HuggingFaceLLM for inference.
This module provides a shared instance that can be used across the application.
Models are loaded lazily on first request to avoid blocking application startup.
"""

import asyncio
import logging
import os

from rhesis.sdk.models import HuggingFaceLLM

logger = logging.getLogger("rhesis-polyphemus")

# Model name - can be overridden via environment variable
modelname = os.environ.get("HF_MODEL", "distilgpt2")

# Singleton instance
_polyphemus_instance = None

# Async lock for thread-safe initialization
_polyphemus_lock = asyncio.Lock()


def is_model_loaded() -> bool:
    """
    Check if the model instance is initialized and loaded.
    Non-blocking check that doesn't trigger model loading.

    Returns:
        bool: True if model is loaded, False otherwise
    """
    return _polyphemus_instance is not None and (
        _polyphemus_instance.model is not None and _polyphemus_instance.tokenizer is not None
    )


async def get_polyphemus_instance() -> HuggingFaceLLM:  # should base llm instead
    """
    Get or create the singleton HuggingFaceLLM instance with lazy async initialization.

    The model is only loaded on first access, not at module import time.
    This prevents blocking application startup and aligns with the design intent
    that models should load on first request.

    Returns:
        HuggingFaceLLM: The singleton instance
    """
    global _polyphemus_instance

    if _polyphemus_instance is None:
        async with _polyphemus_lock:
            # Double-check pattern: another coroutine might have initialized it
            if _polyphemus_instance is None:
                logger.info(f"Initializing HuggingFaceLLM with model: {modelname}")

                # Create instance with auto_loading=False to defer model loading
                _polyphemus_instance = HuggingFaceLLM(modelname, auto_loading=False)

                # Load model asynchronously in executor to avoid blocking event loop
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, _polyphemus_instance.load_model)

                # # Fix pad_token for GPT-2 models if needed
                # if _polyphemus_instance.tokenizer.pad_token is None:
                #     _polyphemus_instance.tokenizer.pad_token = (
                #         _polyphemus_instance.tokenizer.eos_token
                #     )

                logger.info(
                    f"Polyphemus instance initialized with model: {modelname}, "
                    f"model loaded: {_polyphemus_instance.model is not None}, "
                    f"tokenizer loaded: {_polyphemus_instance.tokenizer is not None}"
                )

    return _polyphemus_instance


# Example child class for specific models (following the pattern from example)
class TinyLLM(HuggingFaceLLM):
    """Example child class for specific model configurations"""

    def __init__(self):
        super().__init__(modelname)
        # Fix pad_token for GPT-2 models if needed
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
