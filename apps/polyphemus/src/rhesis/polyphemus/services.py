"""
Polyphemus service - Singleton instance of HuggingFaceLLM for inference.
This module provides a shared instance that can be used across the application.
"""

import logging
import os

from rhesis.sdk.models import HuggingFaceLLM

logger = logging.getLogger("rhesis-polyphemus")

# Model name - can be overridden via environment variable
modelname = os.environ.get("HF_MODEL", "distilgpt2")

# Singleton instance
_polyphemus_instance = None


def get_polyphemus_instance() -> HuggingFaceLLM:
    """
    Get or create the singleton HuggingFaceLLM instance.

    This follows the pattern from the example code:
    - Normal usage: Creates HuggingFaceLLM instance
    - Child classes: Can extend HuggingFaceLLM for specific models
    - Manual loading: Supports auto_loading=False for manual control

    Returns:
        HuggingFaceLLM: The singleton instance
    """
    global _polyphemus_instance

    if _polyphemus_instance is None:
        logger.info(f"Initializing HuggingFaceLLM with model: {modelname}")
        _polyphemus_instance = HuggingFaceLLM(modelname)

        # Ensure model is loaded
        if _polyphemus_instance.model is None or _polyphemus_instance.tokenizer is None:
            logger.info("Model not auto-loaded, loading explicitly...")
            _polyphemus_instance.load_model()

        # Fix pad_token for GPT-2 models if needed
        if _polyphemus_instance.tokenizer.pad_token is None:
            _polyphemus_instance.tokenizer.pad_token = _polyphemus_instance.tokenizer.eos_token

        logger.info(
            f"Polyphemus instance initialized with model: {modelname}, "
            f"model loaded: {_polyphemus_instance.model is not None}, "
            f"tokenizer loaded: {_polyphemus_instance.tokenizer is not None}"
        )

    return _polyphemus_instance


# Export the singleton instance (lazy initialization on first access)
# This matches the pattern: from rhesis.polyphemus.services import polyphemus_instance
polyphemus_instance = get_polyphemus_instance()


# Example child class for specific models (following the pattern from example)
class TinyLLM(HuggingFaceLLM):
    """Example child class for specific model configurations"""

    def __init__(self):
        super().__init__(modelname)
        # Fix pad_token for GPT-2 models if needed
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
