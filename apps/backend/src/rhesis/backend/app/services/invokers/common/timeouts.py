"""How long one endpoint call may take, for every connection type.

An endpoint's ``timeout_seconds`` wins. Without one, each connection type has a default,
defined only here. Every invoker enforces the result as a total deadline for the call, and a
call that hits it is never retried: the target may have done the work and we cannot assume an
arbitrary endpoint is idempotent.
"""

import os
from typing import Any

from rhesis.backend.app.models.enums import EndpointConnectionType

# Connector calls run user code, which tends to be slower than an HTTP API.
SDK_FUNCTION_TIMEOUT = float(os.environ.get("SDK_FUNCTION_TIMEOUT", "120.0"))

DEFAULT_CALL_TIMEOUTS: dict[str, float] = {
    EndpointConnectionType.REST.value: 30.0,
    EndpointConnectionType.WEBSOCKET.value: 30.0,
    EndpointConnectionType.SDK.value: SDK_FUNCTION_TIMEOUT,
}
FALLBACK_CALL_TIMEOUT = 30.0

# Error type for a REST or WebSocket call that ran out of time. Deliberately not transient.
CALL_TIMEOUT_ERROR_TYPE = "call_timeout"


def default_call_timeout(connection_type: Any) -> float:
    """The default for a connection type, when the endpoint sets no timeout."""
    key = getattr(connection_type, "value", connection_type)
    return DEFAULT_CALL_TIMEOUTS.get(key, FALLBACK_CALL_TIMEOUT)


def call_timeout(endpoint: Any) -> float:
    """Seconds one call to this endpoint may take, start to finish."""
    configured = getattr(endpoint, "timeout_seconds", None)
    if configured:
        return float(configured)
    return default_call_timeout(getattr(endpoint, "connection_type", None))


def call_timeout_message(target: str, seconds: float, suggest_sdk: bool = True) -> str:
    """Why a call stopped, and what to change. ``suggest_sdk`` is off for SDK calls."""
    unit = "second" if seconds == 1 else "seconds"
    message = (
        f"{target} did not finish within {seconds:g} {unit}. If it is just slow, raise "
        "the endpoint's Timeout (seconds)."
    )
    if suggest_sdk:
        message += (
            " Jobs that run longer than the proxies in front of your API allow can run "
            "through the Rhesis SDK instead."
        )
    return message
