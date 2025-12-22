import importlib.metadata
from importlib.metadata import PackageNotFoundError, version

from rhesis.sdk.client import Client as RhesisClient
from rhesis.sdk.config import api_key, base_url
from rhesis.sdk.decorators import collaborate, endpoint, observe
from rhesis.sdk.enums import TestType

try:
    __version__ = version("rhesis-sdk")
except PackageNotFoundError:
    __version__ = "0.0.0"  # fallback for development

# Make these variables available at the module level
__all__ = [
    "api_key",
    "base_url",
    "__version__",
    "TestType",
    "RhesisClient",
    "endpoint",
    "collaborate",  # Backwards compatibility
    "observe",
]
