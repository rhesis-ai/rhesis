"""Shared model-related exceptions."""

from typing import Optional


class ModelConfigurationError(ValueError):
    """Raised when a model configuration is invalid or unavailable."""

    def __init__(self, message: str, original_error: Optional[Exception] = None):
        self.message = message
        self.original_error = original_error
        super().__init__(self.message)
