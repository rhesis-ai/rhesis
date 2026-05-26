"""In-process registry for backend-resident @endpoint functions.

Functions registered here are called directly by SdkEndpointInvoker
without a WebSocket round-trip. Add an entry after each @endpoint
definition in endpoint_operations.py (or equivalent).
"""

import logging

logger = logging.getLogger(__name__)

registry: dict[str, callable] = {}

_local_functions_registered = False


def ensure_local_functions_registered() -> None:
    """Import modules that populate ``registry`` (safe to call repeatedly)."""
    global _local_functions_registered
    if _local_functions_registered:
        return

    # Side effect: endpoint_operations assigns into registry at import time.
    from rhesis.backend.app.services.mcp import endpoint_operations  # noqa: F401

    _local_functions_registered = True
    logger.debug(
        "Local function registry loaded: %s",
        ", ".join(sorted(registry)) or "(empty)",
    )
