"""In-process registry for backend-resident @endpoint functions.

Functions registered here are called directly by SdkEndpointInvoker
without a WebSocket round-trip.  Use ``register_local(func)`` after
each ``@endpoint`` definition; it reads the ``name`` from the
decorator metadata automatically.
"""

import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LocalInvocationContext:
    """Platform context injected by SdkEndpointInvoker into every registry call.

    Replaces the old ``organization_id``, ``user_id``, and ``db`` positional
    kwargs so each registry function receives a single well-typed object and
    avoids the ``_ = db`` placebo pattern.
    """

    organization_id: str
    user_id: Optional[str]
    db: Any  # sqlalchemy.orm.Session | None (typed as Any to avoid hard dep)
    endpoint_id: Optional[UUID] = None


registry: dict[str, Callable[..., Awaitable[Any]]] = {}

_local_functions_registered = False


def ensure_local_functions_registered() -> None:
    """Import modules that populate ``registry`` (safe to call repeatedly)."""
    global _local_functions_registered
    if _local_functions_registered:
        return

    # Side effect: endpoint_operations assigns into registry at import time.
    from rhesis.backend.app.services.architect import (  # noqa: F401
        endpoint_operations as _architect_endpoint_operations,
    )
    from rhesis.backend.app.services.mcp import (  # noqa: F401
        endpoint_operations as _mcp_endpoint_operations,
    )

    _local_functions_registered = True
    logger.debug(
        "Local function registry loaded: %s",
        ", ".join(sorted(registry)) or "(empty)",
    )


def register_local(func: Callable[..., Awaitable[Any]]) -> None:
    """Register a backend-local ``@endpoint`` function under its declared name.

    Reads the ``name`` from the function's ``__endpoint_name__`` attribute
    (set by the ``@endpoint`` decorator).  Falls back to ``func.__name__``
    if the attribute is absent so plain async functions can also be registered.

    Usage::

        @endpoint(name="my_func", ...)
        async def my_func(...) -> ...:
            ...

        register_local(my_func)
    """
    name = getattr(func, "__endpoint_name__", None) or func.__name__
    registry[name] = func
    logger.debug("Registered local function: %s", name)
