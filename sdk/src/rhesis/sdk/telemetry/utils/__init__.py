"""Telemetry utility functions."""

from rhesis.sdk.telemetry.utils.provider_detection import (
    identify_provider,
    identify_provider_from_class_name,
    identify_provider_from_model_name,
)

# Deliberately routed through the legacy submodule rather than ``rhesis.telemetry``: this package is
# itself the old public surface, and importing the shim keeps the whole compatibility layer in one
# place. New code should use ``rhesis.telemetry.token_extraction``.
from rhesis.sdk.telemetry.utils.token_extraction import extract_token_usage

__all__ = [
    "extract_token_usage",
    "identify_provider",
    "identify_provider_from_model_name",
    "identify_provider_from_class_name",
]
