from rhesis.sdk.clients import CONNECTOR_DISABLED, DisabledClient, RhesisClient
from rhesis.sdk.config import SDK_VERSION, api_key, base_url
from rhesis.sdk.context import EndpointContext
from rhesis.sdk.decorators import (
    ObserverBuilder,
    bind_context,
    collaborate,
    create_observer,
    endpoint,
    metric,
    observe,
)
from rhesis.sdk.decorators._state import (
    get_experiment_parameters,
    get_parameters,
    get_test_parameters,
)
from rhesis.sdk.enums import ExecutionMode, TestType
from rhesis.sdk.errors import RhesisAPIError
from rhesis.sdk.parameters import Parameters

__version__ = SDK_VERSION

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
    "CONNECTOR_DISABLED",
    "endpoint",
    "collaborate",  # Backwards compatibility
    "metric",
    "observe",
    "create_observer",
    "ObserverBuilder",
    "bind_context",
    "get_experiment_parameters",
    "get_parameters",
    "get_test_parameters",
    "Parameters",
    "EndpointContext",
]
