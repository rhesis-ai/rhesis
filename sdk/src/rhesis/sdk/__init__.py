import importlib.metadata
from importlib.metadata import PackageNotFoundError, version

from rhesis.sdk.clients import DisabledClient, RhesisClient
from rhesis.sdk.config import api_key, base_url
from rhesis.sdk.decorators import (
    ObserverBuilder,
    bind_context,
    collaborate,
    create_observer,
    endpoint,
    metric,
    observe,
)
from rhesis.sdk.decorators._state import get_parameters
from rhesis.sdk.enums import ExecutionMode, TestType
from rhesis.sdk.errors import RhesisAPIError
from rhesis.sdk.parameters import Parameters

try:
    __version__ = version("rhesis-sdk")
except PackageNotFoundError:
    __version__ = "0.0.0"  # fallback for development

# Make these variables available at the module level
__all__ = [
    "api_key",
    "base_url",
    "__version__",
    "ExecutionMode",
    "TestType",
    "RhesisAPIError",
    "RhesisClient",
    "DisabledClient",
    "endpoint",
    "collaborate",  # Backwards compatibility
    "metric",
    "observe",
    "create_observer",
    "ObserverBuilder",
    "bind_context",
    "get_parameters",
    "Parameters",
]
